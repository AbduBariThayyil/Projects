#define _GNU_SOURCE
#include "keyholder.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/file.h>
#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/timerfd.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define MAX_DEVS 64
#define MAX_EVENTS 32
#define VENDOR_KEYHOLDER 0x4b48
#define PROD_KH_KBD      0x0001
#define PROD_KH_PTR      0x0002
#define VENDOR_SYS_INPUT 0x4b49

#define BIT_TEST(arr, bit) (((arr)[(bit) / 8] >> ((bit) % 8)) & 1)

typedef struct {
    int fd;
    char path[300];
} InDev;

typedef struct {
    int kbd_fd;
    int ptr_fd;
    int epoll_fd;
    int inotify_fd;
    int timer_fd;
    int sock_fd;
    InDev devs[MAX_DEVS];
    size_t dev_count;
    KhState state;
    char sock_path[108];
    char cfg_path[512];
    char hud_fifo_path[512];
    int64_t idle_since_ns;
    volatile sig_atomic_t stop;
} Daemon;

static Daemon *g_d = NULL;

static void on_sig(int sig) {
    (void)sig;
    if (g_d) g_d->stop = 1;
}

static int64_t now_mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + (int64_t)ts.tv_nsec;
}

static void get_runtime_path(const char *name, char *out, size_t sz) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (xdg && *xdg) {
        snprintf(out, sz, "%s/%s", xdg, name);
    } else {
        snprintf(out, sz, "/tmp/%s-%u", name, (unsigned)getuid());
    }
}

static void get_cfg_path(char *out, size_t sz) {
    const char *home = getenv("HOME");
    if (!home || !*home) home = "/tmp";
    char dir[460];
    snprintf(dir, sizeof(dir), "%s/.config/keyholder", home);
    mkdir(dir, 0755);
    snprintf(out, sz, "%s/config", dir);
}

static void load_config(const char *path, int *delay_ms, int *hold_ms) {
    *delay_ms = KH_DEFAULT_DELAY;
    *hold_ms = KH_DEFAULT_HOLD;
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[128];
    while (fgets(line, sizeof(line), f)) {
        int val = 0;
        if (sscanf(line, "delay_ms=%d", &val) == 1) *delay_ms = val;
        else if (sscanf(line, "hold_ms=%d", &val) == 1) *hold_ms = val;
    }
    fclose(f);
}

static void cb_save_config(void *ctx, int delay_ms, int hold_ms) {
    Daemon *d = ctx;
    FILE *f = fopen(d->cfg_path, "w");
    if (!f) return;
    fprintf(f, "delay_ms=%d\nhold_ms=%d\n", delay_ms, hold_ms);
    fclose(f);
}

static void write_uinput(int fd, uint16_t type, uint16_t code, int32_t value) {
    if (fd < 0) return;
    struct input_event ev = { .type = type, .code = code, .value = value };
    ssize_t w = write(fd, &ev, sizeof(ev));
    (void)w;
}

static void cb_emit_key(void *ctx, uint16_t code, bool is_mouse, int32_t value) {
    Daemon *d = ctx;
    int fd = is_mouse ? d->ptr_fd : d->kbd_fd;
    write_uinput(fd, EV_KEY, code, value);
    write_uinput(fd, EV_SYN, SYN_REPORT, 0);
}

static void spawn_hud(void) {
    pid_t pid = fork();
    if (pid != 0) return;
    setsid();
    int devnull = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (devnull >= 0) {
        dup2(devnull, STDIN_FILENO);
        dup2(devnull, STDOUT_FILENO);
        dup2(devnull, STDERR_FILENO);
        if (devnull > 2) close(devnull);
    }
    char exe[512];
    ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (len > 0) {
        exe[len] = '\0';
        char sib[512];
        snprintf(sib, sizeof(sib), "%s/keyholder-hud", dirname(exe));
        if (access(sib, X_OK) == 0) {
            execl(sib, "keyholder-hud", (char *)NULL);
        }
    }
    execl("/home/vibecoder/.local/bin/keyholder-hud", "keyholder-hud", (char *)NULL);
    execlp("keyholder-hud", "keyholder-hud", (char *)NULL);
    _exit(127);
}

static void send_hud_raw(const char *fifo_path, const char *msg) {
    int fd = open(fifo_path, O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        spawn_hud();
        struct timespec ts = { .tv_sec = 0, .tv_nsec = 10000000L };
        for (int i = 0; i < 20; i++) {
            nanosleep(&ts, NULL);
            fd = open(fifo_path, O_WRONLY | O_NONBLOCK | O_CLOEXEC);
            if (fd >= 0) break;
        }
    }
    if (fd >= 0) {
        size_t len = strlen(msg);
        ssize_t w = write(fd, msg, len);
        (void)w;
        close(fd);
    }
}

static void cb_hud_update(void *ctx) {
    Daemon *d = ctx;
    char msg[512];
    kh_format_hud_message(&d->state, now_mono_ns(), msg, sizeof(msg));
    send_hud_raw(d->hud_fifo_path, msg);
}

static int create_uinput_kbd(void) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return -1;
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    for (int c = 1; c < 256; c++) ioctl(fd, UI_SET_KEYBIT, c);

    struct uinput_setup us = {0};
    us.id.bustype = BUS_USB;
    us.id.vendor = VENDOR_KEYHOLDER;
    us.id.product = PROD_KH_KBD;
    us.id.version = 2;
    snprintf(us.name, sizeof(us.name), "Virtual-KeyHolder-Kbd");
    if (ioctl(fd, UI_DEV_SETUP, &us) < 0 || ioctl(fd, UI_DEV_CREATE) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int create_uinput_ptr(void) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return -1;
    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    ioctl(fd, UI_SET_KEYBIT, BTN_LEFT);
    ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT);
    ioctl(fd, UI_SET_KEYBIT, BTN_MIDDLE);
    ioctl(fd, UI_SET_KEYBIT, BTN_SIDE);
    ioctl(fd, UI_SET_KEYBIT, BTN_EXTRA);

    struct uinput_setup us = {0};
    us.id.bustype = BUS_USB;
    us.id.vendor = VENDOR_KEYHOLDER;
    us.id.product = PROD_KH_PTR;
    us.id.version = 2;
    snprintf(us.name, sizeof(us.name), "Virtual-KeyHolder-Ptr");
    if (ioctl(fd, UI_DEV_SETUP, &us) < 0 || ioctl(fd, UI_DEV_CREATE) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static bool dev_already_open(const Daemon *d, const char *path) {
    for (size_t i = 0; i < d->dev_count; i++) {
        if (strcmp(d->devs[i].path, path) == 0) return true;
    }
    return false;
}

static void seed_initially_down(Daemon *d, int fd) {
    uint8_t key_bits[(KEY_MAX + 7) / 8] = {0};
    if (ioctl(fd, EVIOCGKEY(sizeof(key_bits)), key_bits) < 0) return;
    for (uint16_t c = 0; c < 512; c++) {
        if (BIT_TEST(key_bits, c)) {
            kh_set_initially_down(&d->state, c, true);
        }
    }
}

static void try_open_dev(Daemon *d, const char *path) {
    if (d->dev_count >= MAX_DEVS || dev_already_open(d, path)) return;

    int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return;

    struct input_id id = {0};
    char name[128] = {0};
    if (ioctl(fd, EVIOCGID, &id) < 0) { close(fd); return; }
    ioctl(fd, EVIOCGNAME(sizeof(name)), name);

    /* Never read our own virtual output devices */
    if (id.vendor == VENDOR_KEYHOLDER || strncmp(name, "Virtual-KeyHolder", 17) == 0) {
        close(fd);
        return;
    }

    uint8_t ev_bits[(EV_MAX + 7) / 8] = {0};
    uint8_t key_bits[(KEY_MAX + 7) / 8] = {0};
    if (ioctl(fd, EVIOCGBIT(0, sizeof(ev_bits)), ev_bits) < 0 || !BIT_TEST(ev_bits, EV_KEY)) {
        close(fd);
        return;
    }
    ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)), key_bits);

    bool useful = BIT_TEST(key_bits, KEY_A) || BIT_TEST(key_bits, BTN_LEFT) || (id.vendor == VENDOR_SYS_INPUT);
    if (!useful) {
        close(fd);
        return;
    }

    /* Drain stale unread events */
    struct input_event ev;
    while (read(fd, &ev, sizeof(ev)) > 0) {}

    struct epoll_event epev = { .events = EPOLLIN, .data = { .fd = fd } };
    if (epoll_ctl(d->epoll_fd, EPOLL_CTL_ADD, fd, &epev) < 0) {
        close(fd);
        return;
    }

    InDev *slot = &d->devs[d->dev_count++];
    slot->fd = fd;
    snprintf(slot->path, sizeof(slot->path), "%s", path);
    seed_initially_down(d, fd);
}

static void scan_devs(Daemon *d) {
    DIR *dir = opendir("/dev/input");
    if (!dir) return;
    struct dirent *de;
    while ((de = readdir(dir))) {
        if (strncmp(de->d_name, "event", 5) == 0) {
            char p[300];
            int n = snprintf(p, sizeof(p), "/dev/input/%s", de->d_name);
            if (n > 0 && (size_t)n < sizeof(p)) try_open_dev(d, p);
        }
    }
    closedir(dir);
}

static void remove_dev_idx(Daemon *d, size_t idx) {
    if (idx >= d->dev_count) return;
    epoll_ctl(d->epoll_fd, EPOLL_CTL_DEL, d->devs[idx].fd, NULL);
    close(d->devs[idx].fd);
    d->devs[idx] = d->devs[d->dev_count - 1];
    d->dev_count--;
}

static void reseed_all_devices(Daemon *d) {
    kh_clear_initially_down(&d->state);
    for (size_t i = 0; i < d->dev_count; i++) {
        seed_initially_down(d, d->devs[i].fd);
    }
}

static void arm_timer(Daemon *d) {
    int64_t now = now_mono_ns();
    int64_t dt = kh_next_timeout_ns(&d->state, now);
    if (dt < 0 && !kh_has_activity(&d->state)) {
        if (d->idle_since_ns == 0) d->idle_since_ns = now;
        int64_t rem = (d->idle_since_ns + 2500000000LL) - now;
        dt = rem > 0 ? rem : 0;
    } else if (kh_has_activity(&d->state)) {
        d->idle_since_ns = 0;
    }

    struct itimerspec its = {0};
    if (dt >= 0) {
        if (dt == 0) dt = 100000LL; /* 0.1ms immediate wakeup */
        its.it_value.tv_sec = dt / 1000000000LL;
        its.it_value.tv_nsec = dt % 1000000000LL;
    }
    timerfd_settime(d->timer_fd, 0, &its, NULL);
}

static void handle_socket_cmd(Daemon *d) {
    int cfd = accept4(d->sock_fd, NULL, NULL, SOCK_CLOEXEC);
    if (cfd < 0) return;

    char buf[256] = {0};
    ssize_t n = read(cfd, buf, sizeof(buf) - 1);
    if (n > 0) {
        buf[n] = '\0';
        int64_t now = now_mono_ns();
        int val = 0;
        if (strncmp(buf, "HOLD_MULTI", 10) == 0) {
            reseed_all_devices(d);
            kh_cmd_hold(&d->state, true, now);
        } else if (strncmp(buf, "HOLD_MS ", 8) == 0 && sscanf(buf + 8, "%d", &val) == 1) {
            kh_cmd_set_hold_ms(&d->state, val);
        } else if (strncmp(buf, "HOLD", 4) == 0) {
            reseed_all_devices(d);
            kh_cmd_hold(&d->state, false, now);
        } else if (strncmp(buf, "SPAM", 4) == 0) {
            int dms = 0, hms = 0;
            sscanf(buf + 4, "%d %d", &dms, &hms);
            reseed_all_devices(d);
            kh_cmd_spam(&d->state, dms, hms, now);
        } else if (strncmp(buf, "STOP", 4) == 0) {
            kh_cmd_terminate(&d->state, now);
        } else if (strncmp(buf, "INC", 3) == 0) {
            kh_cmd_adjust_delay(&d->state, 1.25, 0, 0);
        } else if (strncmp(buf, "DEC", 3) == 0) {
            kh_cmd_adjust_delay(&d->state, 0.8, 0, 0);
        } else if (strncmp(buf, "DELAY ", 6) == 0 && sscanf(buf + 6, "%d", &val) == 1) {
            kh_cmd_adjust_delay(&d->state, 0.0, 0, val);
        } else if (strncmp(buf, "DELTA ", 6) == 0 && sscanf(buf + 6, "%d", &val) == 1) {
            kh_cmd_adjust_delay(&d->state, 0.0, val, 0);
        } else if (strncmp(buf, "CPS ", 4) == 0 && sscanf(buf + 4, "%d", &val) == 1 && val > 0) {
            int ms = 1000 / val;
            if (ms < KH_MIN_DELAY) ms = KH_MIN_DELAY;
            kh_cmd_adjust_delay(&d->state, 0.0, 0, ms);
        } else if (strncmp(buf, "STATUS", 6) == 0) {
            char msg[512];
            kh_format_hud_message(&d->state, now, msg, sizeof(msg));
            ssize_t w = write(cfd, msg, strlen(msg));
            (void)w;
        }
    }
    close(cfd);
    arm_timer(d);
}

static int run_daemon(const char *init_cmd) {
    char lock_path[256];
    get_runtime_path("keyholder.lock", lock_path, sizeof(lock_path));
    int lock_fd = open(lock_path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
    if (lock_fd < 0 || flock(lock_fd, LOCK_EX | LOCK_NB) != 0) {
        if (lock_fd >= 0) close(lock_fd);
        return 0;
    }

    Daemon d = { .kbd_fd = -1, .ptr_fd = -1, .epoll_fd = -1, .inotify_fd = -1, .timer_fd = -1, .sock_fd = -1 };
    g_d = &d;

    get_runtime_path("keyholder.sock", d.sock_path, sizeof(d.sock_path));
    get_runtime_path("keyholder-hud.fifo", d.hud_fifo_path, sizeof(d.hud_fifo_path));
    get_cfg_path(d.cfg_path, sizeof(d.cfg_path));

    struct sigaction sa_chld = { .sa_handler = SIG_IGN, .sa_flags = SA_NOCLDWAIT | SA_RESTART };
    sigemptyset(&sa_chld.sa_mask);
    sigaction(SIGCHLD, &sa_chld, NULL);

    struct sigaction sa_stop = { .sa_handler = on_sig };
    sigemptyset(&sa_stop.sa_mask);
    sigaction(SIGINT, &sa_stop, NULL);
    sigaction(SIGTERM, &sa_stop, NULL);
    sigaction(SIGHUP, &sa_stop, NULL);

    d.sock_fd = socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (d.sock_fd < 0) return 1;
    unlink(d.sock_path);

    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", d.sock_path);
    if (bind(d.sock_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0 || listen(d.sock_fd, 8) < 0) {
        close(d.sock_fd);
        return 1;
    }

    d.kbd_fd = create_uinput_kbd();
    d.ptr_fd = create_uinput_ptr();
    d.epoll_fd = epoll_create1(EPOLL_CLOEXEC);
    d.inotify_fd = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
    d.timer_fd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    if (d.kbd_fd < 0 || d.ptr_fd < 0 || d.epoll_fd < 0 || d.inotify_fd < 0 || d.timer_fd < 0) {
        goto cleanup;
    }

    inotify_add_watch(d.inotify_fd, "/dev/input", IN_CREATE | IN_ATTRIB);
    struct epoll_event evs_add[3] = {
        { .events = EPOLLIN, .data = { .fd = d.sock_fd } },
        { .events = EPOLLIN, .data = { .fd = d.inotify_fd } },
        { .events = EPOLLIN, .data = { .fd = d.timer_fd } },
    };
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.sock_fd, &evs_add[0]);
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.inotify_fd, &evs_add[1]);
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.timer_fd, &evs_add[2]);

    int delay_ms = KH_DEFAULT_DELAY, hold_ms = KH_DEFAULT_HOLD;
    load_config(d.cfg_path, &delay_ms, &hold_ms);

    KhOps ops = {
        .emit_key = cb_emit_key,
        .hud_update = cb_hud_update,
        .save_config = cb_save_config,
    };
    kh_init(&d.state, ops, &d, delay_ms, hold_ms);
    scan_devs(&d);

    if (init_cmd && *init_cmd) {
        int64_t now = now_mono_ns();
        int val = 0;
        if (strncmp(init_cmd, "HOLD_MULTI", 10) == 0) kh_cmd_hold(&d.state, true, now);
        else if (strncmp(init_cmd, "HOLD", 4) == 0) kh_cmd_hold(&d.state, false, now);
        else if (strncmp(init_cmd, "SPAM", 4) == 0) {
            int dms = 0, hms = 0;
            sscanf(init_cmd + 4, "%d %d", &dms, &hms);
            kh_cmd_spam(&d.state, dms, hms, now);
        } else if (strncmp(init_cmd, "DELAY ", 6) == 0 && sscanf(init_cmd + 6, "%d", &val) == 1) {
            kh_cmd_adjust_delay(&d.state, 0.0, 0, val);
        }
    }
    arm_timer(&d);

    struct epoll_event events[MAX_EVENTS];
    while (!d.stop) {
        int n = epoll_wait(d.epoll_fd, events, MAX_EVENTS, -1);
        if (n < 0) {
            if (errno == EINTR) continue;
            break;
        }
        for (int i = 0; i < n; i++) {
            int fd = events[i].data.fd;
            if (fd == d.sock_fd) {
                handle_socket_cmd(&d);
            } else if (fd == d.timer_fd) {
                uint64_t exp = 0;
                ssize_t r = read(d.timer_fd, &exp, sizeof(exp));
                (void)r;
                int64_t now = now_mono_ns();
                kh_tick(&d.state, now);
                if (!kh_has_activity(&d.state) && d.idle_since_ns > 0 && (now - d.idle_since_ns) >= 2500000000LL) {
                    d.stop = 1;
                    break;
                }
                arm_timer(&d);
            } else if (fd == d.inotify_fd) {
                char buf[2048];
                while (read(d.inotify_fd, buf, sizeof(buf)) > 0) {}
                scan_devs(&d);
            } else {
                for (size_t idx = 0; idx < d.dev_count; idx++) {
                    if (d.devs[idx].fd == fd) {
                        struct input_event evbuf[64];
                        ssize_t nr;
                        while ((nr = read(fd, evbuf, sizeof(evbuf))) > 0) {
                            size_t cnt = (size_t)nr / sizeof(struct input_event);
                            int64_t now = now_mono_ns();
                            for (size_t j = 0; j < cnt; j++) {
                                if (evbuf[j].type == EV_KEY) {
                                    kh_on_key_event(&d.state, evbuf[j].code, evbuf[j].value, now);
                                } else if (evbuf[j].type == EV_REL && evbuf[j].code == REL_WHEEL) {
                                    kh_on_wheel_event(&d.state, evbuf[j].value, now);
                                }
                            }
                        }
                        if (nr == 0 || (nr < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) {
                            remove_dev_idx(&d, idx);
                        }
                        arm_timer(&d);
                        break;
                    }
                }
            }
        }
    }

cleanup:
    kh_cmd_terminate(&d.state, now_mono_ns());
    while (d.dev_count > 0) remove_dev_idx(&d, d.dev_count - 1);
    if (d.kbd_fd >= 0) { ioctl(d.kbd_fd, UI_DEV_DESTROY); close(d.kbd_fd); }
    if (d.ptr_fd >= 0) { ioctl(d.ptr_fd, UI_DEV_DESTROY); close(d.ptr_fd); }
    if (d.timer_fd >= 0) close(d.timer_fd);
    if (d.inotify_fd >= 0) close(d.inotify_fd);
    if (d.epoll_fd >= 0) close(d.epoll_fd);
    if (d.sock_fd >= 0) close(d.sock_fd);
    unlink(d.sock_path);
    flock(lock_fd, LOCK_UN);
    close(lock_fd);
    return 0;
}

static int send_sock_cmd(const char *sock_path, const char *cmd, char *reply, size_t reply_sz) {
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) return -1;

    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    snprintf(addr.sun_path, sizeof(addr.sun_path), "%s", sock_path);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }
    ssize_t w = write(fd, cmd, strlen(cmd));
    (void)w;
    if (reply && reply_sz > 0) {
        ssize_t r = read(fd, reply, reply_sz - 1);
        reply[r > 0 ? r : 0] = '\0';
    }
    close(fd);
    return 0;
}

static void print_help(const char *prog) {
    printf("KeyHolder - Native C Key/Mouse Hold & Spam Automation\n");
    printf("Usage: %s [OPTIONS] [DELAY_MS | +DELTA | -DELTA]\n", prog);
    printf("  --hold, -H        Toggle or latch key/button hold mode\n");
    printf("  --multi, -m       Add another simultaneous hold slot\n");
    printf("  --spam, -s        Toggle or latch high-speed spam mode\n");
    printf("  --terminate, -k   Stop all active holds & spams\n");
    printf("  --inc / --dec     Increase (slower) or decrease (faster) spam delay\n");
    printf("  --delay, -d MS    Set spam cycle delay (%d-%d ms)\n", KH_MIN_DELAY, KH_MAX_DELAY);
    printf("  --cps N           Set spam speed in clicks per second\n");
    printf("  --hold-ms MS      Set per-tap key-down duration (1-500 ms)\n");
    printf("  --status          Print active state\n");
}

int main(int argc, char **argv) {
    bool want_hold = false, want_spam = false, want_multi = false;
    bool want_stop = false, want_inc = false, want_dec = false, want_status = false;
    int delay_val = 0, delta_val = 0, cps_val = 0, hold_ms_val = 0;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0) {
            print_help(argv[0]);
            return 0;
        } else if (strcmp(a, "--daemon") == 0) {
            return run_daemon(i + 1 < argc ? argv[i + 1] : NULL);
        } else if (strcmp(a, "--hold") == 0 || strcmp(a, "-H") == 0) {
            want_hold = true;
        } else if (strcmp(a, "--multi") == 0 || strcmp(a, "-m") == 0) {
            want_multi = true;
        } else if (strcmp(a, "--spam") == 0 || strcmp(a, "-s") == 0) {
            want_spam = true;
        } else if (strcmp(a, "--terminate") == 0 || strcmp(a, "-k") == 0) {
            want_stop = true;
        } else if (strcmp(a, "--inc") == 0) {
            want_inc = true;
        } else if (strcmp(a, "--dec") == 0) {
            want_dec = true;
        } else if (strcmp(a, "--status") == 0) {
            want_status = true;
        } else if ((strcmp(a, "--delay") == 0 || strcmp(a, "-d") == 0 || strcmp(a, "--set-delay") == 0) && i + 1 < argc) {
            delay_val = atoi(argv[++i]);
        } else if (strcmp(a, "--cps") == 0 && i + 1 < argc) {
            cps_val = atoi(argv[++i]);
        } else if (strcmp(a, "--hold-ms") == 0 && i + 1 < argc) {
            hold_ms_val = atoi(argv[++i]);
        } else if (a[0] == '+' || a[0] == '-') {
            delta_val = atoi(a);
        } else if (a[0] >= '0' && a[0] <= '9') {
            delay_val = atoi(a);
        }
    }

    char sock_path[108];
    get_runtime_path("keyholder.sock", sock_path, sizeof(sock_path));

    if (want_status) {
        char reply[512] = {0};
        if (send_sock_cmd(sock_path, "STATUS\n", reply, sizeof(reply)) == 0) {
            printf("%s", reply);
        } else {
            printf("idle\n");
        }
        return 0;
    }

    if (want_stop) {
        if (send_sock_cmd(sock_path, "STOP\n", NULL, 0) != 0) {
            char fifo[512];
            get_runtime_path("keyholder-hud.fifo", fifo, sizeof(fifo));
            send_hud_raw(fifo, "stop|All released|cps=25.0|ms=40\n");
        }
        return 0;
    }

    if (cps_val > 0) {
        delay_val = 1000 / cps_val;
        if (delay_val < KH_MIN_DELAY) delay_val = KH_MIN_DELAY;
    }

    /* Offline config updates work even if daemon isn't running */
    if (!want_hold && !want_spam && (want_inc || want_dec || delay_val > 0 || delta_val != 0 || hold_ms_val > 0)) {
        char cmd[128] = {0};
        if (want_inc) snprintf(cmd, sizeof(cmd), "INC\n");
        else if (want_dec) snprintf(cmd, sizeof(cmd), "DEC\n");
        else if (hold_ms_val > 0) snprintf(cmd, sizeof(cmd), "HOLD_MS %d\n", hold_ms_val);
        else if (delta_val != 0) snprintf(cmd, sizeof(cmd), "DELTA %d\n", delta_val);
        else snprintf(cmd, sizeof(cmd), "DELAY %d\n", delay_val);

        if (send_sock_cmd(sock_path, cmd, NULL, 0) != 0) {
            char cfg[512];
            get_cfg_path(cfg, sizeof(cfg));
            int dms = KH_DEFAULT_DELAY, hms = KH_DEFAULT_HOLD;
            load_config(cfg, &dms, &hms);
            if (want_inc) dms = (int)(dms * 1.25 + 0.5);
            else if (want_dec) dms = (int)(dms * 0.8 + 0.5);
            else if (hold_ms_val > 0) hms = hold_ms_val;
            else if (delta_val != 0) dms += delta_val;
            else if (delay_val > 0) dms = delay_val;
            if (dms < KH_MIN_DELAY) dms = KH_MIN_DELAY;
            if (dms > KH_MAX_DELAY) dms = KH_MAX_DELAY;
            if (hms < 1) hms = 1;
            if (hms > 500) hms = 500;
            FILE *f = fopen(cfg, "w");
            if (f) { fprintf(f, "delay_ms=%d\nhold_ms=%d\n", dms, hms); fclose(f); }
            char fifo[512], hud_msg[256];
            get_runtime_path("keyholder-hud.fifo", fifo, sizeof(fifo));
            snprintf(hud_msg, sizeof(hud_msg), "stop|Delay %dms (%.1f/s)|cps=%.1f|ms=%d\n", dms, 1000.0 / dms, 1000.0 / dms, dms);
            send_hud_raw(fifo, hud_msg);
        }
        return 0;
    }

    char cmd[128] = {0};
    if (want_hold) {
        snprintf(cmd, sizeof(cmd), "%s\n", want_multi ? "HOLD_MULTI" : "HOLD");
    } else {
        snprintf(cmd, sizeof(cmd), "SPAM %d %d\n", delay_val, hold_ms_val);
    }

    if (send_sock_cmd(sock_path, cmd, NULL, 0) == 0) {
        return 0;
    }

    /* Autospawn daemon cleanly */
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR | O_CLOEXEC);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }
        char exe[512];
        ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
        if (len > 0) {
            exe[len] = '\0';
            execl(exe, "KeyHolder", "--daemon", cmd, (char *)NULL);
        }
        execl("/home/vibecoder/.local/bin/KeyHolder", "KeyHolder", "--daemon", cmd, (char *)NULL);
        execlp("KeyHolder", "KeyHolder", "--daemon", cmd, (char *)NULL);
        _exit(127);
    }
    struct timespec ts = { .tv_sec = 0, .tv_nsec = 1000000L };
    for (int i = 0; i < 60; i++) {
        if (access(sock_path, F_OK) == 0) break;
        nanosleep(&ts, NULL);
    }
    return 0;
}
