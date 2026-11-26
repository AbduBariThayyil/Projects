#define _GNU_SOURCE
#include "sys-input.h"
#include "sys-input-x11.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
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
#include <sys/stat.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

#define MAX_DEVICES 64
#define MAX_EPOLL_EVENTS 32

#define VENDOR_SYS_INPUT 0x4b49
#define PROD_SYS_KBD     0x0001
#define PROD_SYS_PTR     0x0002
#define VENDOR_KEYHOLDER 0x4b48
#define VENDOR_KEYD      0x0fac
#define VENDOR_CASUE     0x2a7a
#define PROD_CASUE       0x8927
#define VENDOR_GM320     0x30fa
#define PROD_GM320       0x1440

#define BIT_TEST(arr, bit) (((arr)[(bit) / 8] >> ((bit) % 8)) & 1)

typedef struct {
    int fd;
    DeviceKind kind;
    char path[300];
    char name[128];
    bool has_scroll_led;
} InputDev;

typedef struct {
    int uinput_kbd_fd;
    int uinput_ptr_fd;
    int epoll_fd;
    int inotify_fd;
    int tap_timer_fd;
    int x11_retry_timer_fd;
    int lock_fd;
    uint16_t pending_tap_code;
    InputDev devs[MAX_DEVICES];
    size_t dev_count;
    SysInputState state;
    SysInputX11 *x11;
    volatile sig_atomic_t stop_requested;
} DaemonCtx;

static DaemonCtx *g_ctx = NULL;

static void on_stop_signal(int sig) {
    (void)sig;
    if (g_ctx) {
        g_ctx->stop_requested = 1;
    }
}

static int acquire_lock(void) {
    char path[512];
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (xdg && *xdg) {
        snprintf(path, sizeof(path), "%s/sys-input.lock", xdg);
    } else {
        snprintf(path, sizeof(path), "/tmp/sys-input-%u.lock", (unsigned)getuid());
    }

    int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
    if (fd < 0) {
        return -1;
    }
    if (flock(fd, LOCK_EX | LOCK_NB) != 0) {
        close(fd);
        return -2;
    }
    if (ftruncate(fd, 0) == 0) {
        char buf[32];
        int len = snprintf(buf, sizeof(buf), "%d\n", (int)getpid());
        if (len > 0) {
            ssize_t w = write(fd, buf, (size_t)len);
            (void)w;
        }
    }
    return fd;
}

static void write_uinput_event(int fd, uint16_t type, uint16_t code, int32_t value) {
    if (fd < 0) {
        return;
    }
    struct input_event ev = {0};
    ev.type = type;
    ev.code = code;
    ev.value = value;
    ssize_t n = write(fd, &ev, sizeof(ev));
    (void)n;
}

static void cb_emit_kbd(void *ctx, uint16_t type, uint16_t code, int32_t value) {
    DaemonCtx *d = ctx;
    write_uinput_event(d->uinput_kbd_fd, type, code, value);
}

static void cb_emit_kbd_syn(void *ctx) {
    DaemonCtx *d = ctx;
    write_uinput_event(d->uinput_kbd_fd, EV_SYN, SYN_REPORT, 0);
}

static void cb_emit_ptr(void *ctx, uint16_t type, uint16_t code, int32_t value) {
    DaemonCtx *d = ctx;
    write_uinput_event(d->uinput_ptr_fd, type, code, value);
}

static void cb_emit_ptr_syn(void *ctx) {
    DaemonCtx *d = ctx;
    write_uinput_event(d->uinput_ptr_fd, EV_SYN, SYN_REPORT, 0);
}

static void cb_schedule_tap_release(void *ctx, uint16_t code, int delay_ms) {
    DaemonCtx *d = ctx;
    if (d->tap_timer_fd < 0) {
        cb_emit_ptr(ctx, EV_KEY, code, 0);
        cb_emit_ptr_syn(ctx);
        return;
    }
    if (d->pending_tap_code != 0) {
        cb_emit_ptr(ctx, EV_KEY, d->pending_tap_code, 0);
        cb_emit_ptr_syn(ctx);
    }
    d->pending_tap_code = code;

    struct itimerspec its = {0};
    its.it_value.tv_sec = delay_ms / 1000;
    its.it_value.tv_nsec = (long)(delay_ms % 1000) * 1000000L;
    timerfd_settime(d->tap_timer_fd, 0, &its, NULL);
}

static void cb_set_casue_scroll_led(void *ctx, bool on) {
    DaemonCtx *d = ctx;
    for (size_t i = 0; i < d->dev_count; i++) {
        if (d->devs[i].kind == DEV_KBD_CASUE && d->devs[i].has_scroll_led) {
            struct input_event ev = {0};
            ev.type = EV_LED;
            ev.code = LED_SCROLLL;
            ev.value = on ? 1 : 0;
            ssize_t n = write(d->devs[i].fd, &ev, sizeof(ev));
            (void)n;
        }
    }
}

static void spawn_detached(const char *const argv[]) {
    pid_t pid = fork();
    if (pid != 0) {
        return;
    }

    setsid();
    struct sigaction sa = {0};
    sa.sa_handler = SIG_DFL;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGCHLD, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    int devnull = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (devnull >= 0) {
        dup2(devnull, STDIN_FILENO);
        dup2(devnull, STDOUT_FILENO);
        dup2(devnull, STDERR_FILENO);
        if (devnull > 2) {
            close(devnull);
        }
    }

    execvp(argv[0], (char *const *)argv);
    _exit(127);
}

static void cb_run_cmd(void *ctx, const char *cmd) {
    (void)ctx;
    if (!cmd || !*cmd) {
        return;
    }
    /* Split simple space-separated commands cleanly; fallback to /bin/sh if needed */
    if (!strpbrk(cmd, "|&;><$`'\"")) {
        char buf[512];
        snprintf(buf, sizeof(buf), "%s", cmd);
        const char *argv[16];
        size_t argc = 0;
        char *saveptr = NULL;
        for (char *tok = strtok_r(buf, " ", &saveptr); tok && argc < 15; tok = strtok_r(NULL, " ", &saveptr)) {
            argv[argc++] = tok;
        }
        argv[argc] = NULL;
        if (argc > 0) {
            spawn_detached(argv);
            return;
        }
    }
    const char *sh_argv[] = { "/bin/sh", "-c", cmd, NULL };
    spawn_detached(sh_argv);
}

static void cb_notify_toggle(void *ctx, const char *kind, bool active) {
    (void)ctx;
    const char *argv[] = {
        "/home/vibecoder/.local/bin/sys-notif",
        "--osd",
        kind ? kind : "gaming",
        active ? "100" : "0",
        NULL
    };
    spawn_detached(argv);
}

static int create_uinput_kbd(void) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        return -1;
    }

    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_SYN);
    for (int code = 1; code < 256; code++) {
        ioctl(fd, UI_SET_KEYBIT, code);
    }
    ioctl(fd, UI_SET_KEYBIT, KEY_TOUCHPAD_TOGGLE);

    struct uinput_setup usetup = {0};
    usetup.id.bustype = BUS_USB;
    usetup.id.vendor = VENDOR_SYS_INPUT;
    usetup.id.product = PROD_SYS_KBD;
    usetup.id.version = 1;
    snprintf(usetup.name, sizeof(usetup.name), "sys-input virtual keyboard");

    if (ioctl(fd, UI_DEV_SETUP, &usetup) < 0 || ioctl(fd, UI_DEV_CREATE) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int create_uinput_ptr(void) {
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        return -1;
    }

    ioctl(fd, UI_SET_EVBIT, EV_KEY);
    ioctl(fd, UI_SET_EVBIT, EV_REL);
    ioctl(fd, UI_SET_EVBIT, EV_SYN);

    ioctl(fd, UI_SET_KEYBIT, BTN_LEFT);
    ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT);
    ioctl(fd, UI_SET_KEYBIT, BTN_MIDDLE);
    ioctl(fd, UI_SET_KEYBIT, BTN_SIDE);
    ioctl(fd, UI_SET_KEYBIT, BTN_EXTRA);

    ioctl(fd, UI_SET_RELBIT, REL_X);
    ioctl(fd, UI_SET_RELBIT, REL_Y);
    ioctl(fd, UI_SET_RELBIT, REL_WHEEL);
    ioctl(fd, UI_SET_RELBIT, REL_HWHEEL);
    ioctl(fd, UI_SET_RELBIT, REL_WHEEL_HI_RES);
    ioctl(fd, UI_SET_RELBIT, REL_HWHEEL_HI_RES);

    struct uinput_setup usetup = {0};
    usetup.id.bustype = BUS_USB;
    usetup.id.vendor = VENDOR_SYS_INPUT;
    usetup.id.product = PROD_SYS_PTR;
    usetup.id.version = 1;
    snprintf(usetup.name, sizeof(usetup.name), "sys-input virtual pointer");

    if (ioctl(fd, UI_DEV_SETUP, &usetup) < 0 || ioctl(fd, UI_DEV_CREATE) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static bool is_device_already_open(const DaemonCtx *d, const char *path) {
    for (size_t i = 0; i < d->dev_count; i++) {
        if (strcmp(d->devs[i].path, path) == 0) {
            return true;
        }
    }
    return false;
}

static bool classify_device(int fd, const struct input_id *id, const char *name, DeviceKind *out_kind, bool *out_scroll_led) {
    *out_scroll_led = false;

    if (id->vendor == VENDOR_SYS_INPUT || id->vendor == VENDOR_KEYHOLDER || id->vendor == VENDOR_KEYD) {
        return false;
    }
    if (strncmp(name, "sys-input", 9) == 0 || strncmp(name, "Virtual-KeyHolder", 17) == 0 || strncmp(name, "keyd virtual", 12) == 0) {
        return false;
    }

    uint8_t ev_bits[(EV_MAX + 7) / 8] = {0};
    uint8_t key_bits[(KEY_MAX + 7) / 8] = {0};
    uint8_t rel_bits[(REL_MAX + 7) / 8] = {0};
    uint8_t abs_bits[(ABS_MAX + 7) / 8] = {0};
    uint8_t led_bits[(LED_MAX + 7) / 8] = {0};

    if (ioctl(fd, EVIOCGBIT(0, sizeof(ev_bits)), ev_bits) < 0) {
        return false;
    }
    if (BIT_TEST(ev_bits, EV_KEY)) {
        ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)), key_bits);
    }
    if (BIT_TEST(ev_bits, EV_REL)) {
        ioctl(fd, EVIOCGBIT(EV_REL, sizeof(rel_bits)), rel_bits);
    }
    if (BIT_TEST(ev_bits, EV_ABS)) {
        ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(abs_bits)), abs_bits);
    }
    if (BIT_TEST(ev_bits, EV_LED)) {
        ioctl(fd, EVIOCGBIT(EV_LED, sizeof(led_bits)), led_bits);
    }

    /* Never grab touchpads or pure tablets/joysticks */
    if (BIT_TEST(key_bits, BTN_TOOL_FINGER) || BIT_TEST(key_bits, BTN_TOUCH)) {
        return false;
    }
    if (BIT_TEST(ev_bits, EV_ABS) && !BIT_TEST(key_bits, KEY_A) && !BIT_TEST(rel_bits, REL_X)) {
        return false;
    }

    bool is_mouse = BIT_TEST(rel_bits, REL_X) && BIT_TEST(rel_bits, REL_Y) && BIT_TEST(key_bits, BTN_LEFT);
    bool is_gm320 = (id->vendor == VENDOR_GM320 && id->product == PROD_GM320);
    bool is_casue = (id->vendor == VENDOR_CASUE && id->product == PROD_CASUE);

    if (is_gm320) {
        *out_kind = DEV_MOUSE_GM320;
        return is_mouse || BIT_TEST(key_bits, KEY_CALC) || BIT_TEST(key_bits, KEY_MAIL) || BIT_TEST(key_bits, KEY_HOMEPAGE);
    }

    if (is_casue) {
        *out_kind = DEV_KBD_CASUE;
        *out_scroll_led = BIT_TEST(led_bits, LED_SCROLLL);
        return BIT_TEST(key_bits, KEY_A) || BIT_TEST(key_bits, KEY_MUTE) || BIT_TEST(key_bits, KEY_VOLUMEUP) || BIT_TEST(key_bits, KEY_CALC);
    }

    if (strstr(name, "Toshiba") || strstr(name, "Quickstart")) {
        *out_kind = DEV_KBD_ACPI;
        return BIT_TEST(key_bits, KEY_TOUCHPAD_TOGGLE) || BIT_TEST(key_bits, KEY_UNKNOWN) || BIT_TEST(key_bits, KEY_BRIGHTNESSUP);
    }

    if (is_mouse) {
        *out_kind = DEV_GENERIC_MOUSE;
        return true;
    }

    if (BIT_TEST(key_bits, KEY_A) || BIT_TEST(key_bits, KEY_VOLUMEUP) || BIT_TEST(key_bits, KEY_MUTE)) {
        *out_kind = (strstr(name, "AT Translated") != NULL) ? DEV_KBD_LAPTOP : DEV_GENERIC_KBD;
        return true;
    }

    return false;
}

static bool wait_keys_released(int fd) {
    uint8_t key_state[(KEY_MAX + 7) / 8] = {0};
    for (int attempt = 0; attempt < 15; attempt++) {
        memset(key_state, 0, sizeof(key_state));
        if (ioctl(fd, EVIOCGKEY(sizeof(key_state)), key_state) < 0) {
            return true;
        }
        bool any = false;
        for (size_t i = 0; i < sizeof(key_state); i++) {
            if (key_state[i] != 0) {
                any = true;
                break;
            }
        }
        if (!any) {
            return true;
        }
        struct timespec ts = { .tv_sec = 0, .tv_nsec = 10000000L };
        nanosleep(&ts, NULL);
    }
    return false;
}

static void try_add_device(DaemonCtx *d, const char *path) {
    if (d->dev_count >= MAX_DEVICES || is_device_already_open(d, path)) {
        return;
    }

    int fd = open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    }
    if (fd < 0) {
        return;
    }

    struct input_id id = {0};
    char name[128] = {0};
    if (ioctl(fd, EVIOCGID, &id) < 0) {
        close(fd);
        return;
    }
    if (ioctl(fd, EVIOCGNAME(sizeof(name)), name) < 0) {
        snprintf(name, sizeof(name), "unknown");
    }

    DeviceKind kind = DEV_GENERIC_KBD;
    bool has_scroll_led = false;
    if (!classify_device(fd, &id, name, &kind, &has_scroll_led)) {
        close(fd);
        return;
    }

    wait_keys_released(fd);
    if (ioctl(fd, EVIOCGRAB, 1) < 0) {
        fprintf(stderr, "sys-input: failed to grab %s (%s): %s\n", path, name, strerror(errno));
        close(fd);
        return;
    }

    struct epoll_event ev = {0};
    ev.events = EPOLLIN;
    ev.data.fd = fd;
    if (epoll_ctl(d->epoll_fd, EPOLL_CTL_ADD, fd, &ev) < 0) {
        ioctl(fd, EVIOCGRAB, 0);
        close(fd);
        return;
    }

    InputDev *slot = &d->devs[d->dev_count++];
    slot->fd = fd;
    slot->kind = kind;
    slot->has_scroll_led = has_scroll_led;
    snprintf(slot->path, sizeof(slot->path), "%s", path);
    snprintf(slot->name, sizeof(slot->name), "%s", name);

    if (kind == DEV_KBD_CASUE && has_scroll_led) {
        struct input_event led_ev = { .type = EV_LED, .code = LED_SCROLLL, .value = d->state.fn_lock ? 1 : 0 };
        ssize_t w = write(fd, &led_ev, sizeof(led_ev));
        (void)w;
    }
}

static void scan_input_dir(DaemonCtx *d) {
    DIR *dir = opendir("/dev/input");
    if (!dir) {
        return;
    }
    struct dirent *de;
    while ((de = readdir(dir))) {
        if (strncmp(de->d_name, "event", 5) == 0) {
            char path[300];
            int n = snprintf(path, sizeof(path), "/dev/input/%s", de->d_name);
            if (n > 0 && (size_t)n < sizeof(path)) {
                try_add_device(d, path);
            }
        }
    }
    closedir(dir);
}

static void remove_device_idx(DaemonCtx *d, size_t idx) {
    if (idx >= d->dev_count) {
        return;
    }
    InputDev dev = d->devs[idx];
    epoll_ctl(d->epoll_fd, EPOLL_CTL_DEL, dev.fd, NULL);
    ioctl(dev.fd, EVIOCGRAB, 0);
    close(dev.fd);

    d->devs[idx] = d->devs[d->dev_count - 1];
    d->dev_count--;

    sys_input_on_device_removed(&d->state, dev.kind);
}

static ssize_t find_dev_by_fd(const DaemonCtx *d, int fd) {
    for (size_t i = 0; i < d->dev_count; i++) {
        if (d->devs[i].fd == fd) {
            return (ssize_t)i;
        }
    }
    return -1;
}

static void handle_inotify(DaemonCtx *d) {
    char buf[4096] __attribute__((aligned(__alignof__(struct inotify_event))));
    bool rescanned = false;
    while (1) {
        ssize_t len = read(d->inotify_fd, buf, sizeof(buf));
        if (len <= 0) {
            break;
        }
        const char *ptr = buf;
        while (ptr < buf + len) {
            const struct inotify_event *ev = (const struct inotify_event *)ptr;
            if (ev->len > 0 && strncmp(ev->name, "event", 5) == 0) {
                char path[300];
                int n = snprintf(path, sizeof(path), "/dev/input/%s", ev->name);
                if (n > 0 && (size_t)n < sizeof(path)) {
                    try_add_device(d, path);
                    rescanned = true;
                }
            }
            ptr += sizeof(*ev) + ev->len;
        }
    }
    if (!rescanned) {
        scan_input_dir(d);
    }
}

static void handle_tap_timer(DaemonCtx *d) {
    uint64_t expirations = 0;
    ssize_t r = read(d->tap_timer_fd, &expirations, sizeof(expirations));
    (void)r;
    if (d->pending_tap_code != 0) {
        cb_emit_ptr(d, EV_KEY, d->pending_tap_code, 0);
        cb_emit_ptr_syn(d);
        d->pending_tap_code = 0;
    }
}

static void attach_x11_to_epoll(DaemonCtx *d) {
    if (!d->x11 || !sys_input_x11_connect(d->x11)) {
        return;
    }
    int xfd = sys_input_x11_fd(d->x11);
    if (xfd >= 0) {
        struct epoll_event ev = { .events = EPOLLIN, .data = { .fd = xfd } };
        epoll_ctl(d->epoll_fd, EPOLL_CTL_ADD, xfd, &ev);
        if (d->x11_retry_timer_fd >= 0) {
            struct itimerspec stop = {0};
            timerfd_settime(d->x11_retry_timer_fd, 0, &stop, NULL);
        }
    }
}

static void handle_dev_events(DaemonCtx *d, size_t idx) {
    InputDev *dev = &d->devs[idx];
    struct input_event evs[64];

    while (1) {
        ssize_t n = read(dev->fd, evs, sizeof(evs));
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                break;
            }
            remove_device_idx(d, idx);
            return;
        }
        if (n == 0) {
            remove_device_idx(d, idx);
            return;
        }
        size_t count = (size_t)n / sizeof(struct input_event);
        for (size_t i = 0; i < count; i++) {
            sys_input_handle_event(&d->state, dev->kind, evs[i].type, evs[i].code, evs[i].value);
        }
    }
}

static void cleanup_daemon(DaemonCtx *d) {
    while (d->dev_count > 0) {
        remove_device_idx(d, d->dev_count - 1);
    }
    if (d->pending_tap_code != 0) {
        cb_emit_ptr(d, EV_KEY, d->pending_tap_code, 0);
        cb_emit_ptr_syn(d);
    }
    if (d->x11) {
        sys_input_x11_destroy(d->x11);
        d->x11 = NULL;
    }
    if (d->uinput_kbd_fd >= 0) {
        ioctl(d->uinput_kbd_fd, UI_DEV_DESTROY);
        close(d->uinput_kbd_fd);
    }
    if (d->uinput_ptr_fd >= 0) {
        ioctl(d->uinput_ptr_fd, UI_DEV_DESTROY);
        close(d->uinput_ptr_fd);
    }
    if (d->tap_timer_fd >= 0) close(d->tap_timer_fd);
    if (d->x11_retry_timer_fd >= 0) close(d->x11_retry_timer_fd);
    if (d->inotify_fd >= 0) close(d->inotify_fd);
    if (d->epoll_fd >= 0) close(d->epoll_fd);
    if (d->lock_fd >= 0) {
        flock(d->lock_fd, LOCK_UN);
        close(d->lock_fd);
    }
}

static int run_x11_smoke_test(void) {
    SysInputX11 *x11 = sys_input_x11_create();
    if (!x11) {
        return 1;
    }
    if (sys_input_x11_connect(x11)) {
        sys_input_x11_process(x11);
    }
    sys_input_x11_destroy(x11);
    return 0;
}

int main(int argc, char **argv) {
    if (argc >= 2) {
        if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
            printf("sys-input: Unified evdev/uinput remapper, Wine-bypass hotkey daemon & X11 mod3 sync\n");
            printf("Usage: %s [--help | --test-x11]\n", argv[0]);
            return 0;
        }
        if (strcmp(argv[1], "--test-x11") == 0) {
            return run_x11_smoke_test();
        }
    }

    int lock_fd = acquire_lock();
    if (lock_fd == -2) {
        return 0;
    }
    if (lock_fd < 0) {
        perror("sys-input: lock");
        return 1;
    }

    struct sigaction sa_chld = {0};
    sa_chld.sa_handler = SIG_IGN;
    sa_chld.sa_flags = SA_NOCLDWAIT | SA_RESTART;
    sigemptyset(&sa_chld.sa_mask);
    sigaction(SIGCHLD, &sa_chld, NULL);

    DaemonCtx d = {
        .uinput_kbd_fd = -1,
        .uinput_ptr_fd = -1,
        .epoll_fd = -1,
        .inotify_fd = -1,
        .tap_timer_fd = -1,
        .x11_retry_timer_fd = -1,
        .lock_fd = lock_fd,
    };
    g_ctx = &d;

    struct sigaction sa_stop = {0};
    sa_stop.sa_handler = on_stop_signal;
    sigemptyset(&sa_stop.sa_mask);
    sigaction(SIGINT, &sa_stop, NULL);
    sigaction(SIGTERM, &sa_stop, NULL);
    sigaction(SIGHUP, &sa_stop, NULL);

    d.uinput_kbd_fd = create_uinput_kbd();
    d.uinput_ptr_fd = create_uinput_ptr();
    if (d.uinput_kbd_fd < 0 || d.uinput_ptr_fd < 0) {
        fprintf(stderr, "sys-input: failed to open /dev/uinput: %s\n", strerror(errno));
        cleanup_daemon(&d);
        return 1;
    }

    d.epoll_fd = epoll_create1(EPOLL_CLOEXEC);
    d.inotify_fd = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
    d.tap_timer_fd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);
    d.x11_retry_timer_fd = timerfd_create(CLOCK_MONOTONIC, TFD_NONBLOCK | TFD_CLOEXEC);

    if (d.epoll_fd < 0 || d.inotify_fd < 0 || d.tap_timer_fd < 0 || d.x11_retry_timer_fd < 0) {
        perror("sys-input: fd init");
        cleanup_daemon(&d);
        return 1;
    }

    inotify_add_watch(d.inotify_fd, "/dev/input", IN_CREATE | IN_ATTRIB);

    struct epoll_event ev_in = { .events = EPOLLIN, .data = { .fd = d.inotify_fd } };
    struct epoll_event ev_tap = { .events = EPOLLIN, .data = { .fd = d.tap_timer_fd } };
    struct epoll_event ev_xretry = { .events = EPOLLIN, .data = { .fd = d.x11_retry_timer_fd } };
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.inotify_fd, &ev_in);
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.tap_timer_fd, &ev_tap);
    epoll_ctl(d.epoll_fd, EPOLL_CTL_ADD, d.x11_retry_timer_fd, &ev_xretry);

    SysInputOps ops = {
        .emit_kbd = cb_emit_kbd,
        .emit_kbd_syn = cb_emit_kbd_syn,
        .emit_ptr = cb_emit_ptr,
        .emit_ptr_syn = cb_emit_ptr_syn,
        .schedule_ptr_tap_release = cb_schedule_tap_release,
        .set_casue_scroll_led = cb_set_casue_scroll_led,
        .run_cmd = cb_run_cmd,
        .notify_toggle = cb_notify_toggle,
    };
    sys_input_init(&d.state, ops, &d);

    d.x11 = sys_input_x11_create();
    attach_x11_to_epoll(&d);
    if (sys_input_x11_fd(d.x11) < 0) {
        struct itimerspec retry = { .it_interval = { .tv_sec = 1 }, .it_value = { .tv_sec = 1 } };
        timerfd_settime(d.x11_retry_timer_fd, 0, &retry, NULL);
    }

    scan_input_dir(&d);

    struct epoll_event events[MAX_EPOLL_EVENTS];
    while (!d.stop_requested) {
        int nfds = epoll_wait(d.epoll_fd, events, MAX_EPOLL_EVENTS, -1);
        if (nfds < 0) {
            if (errno == EINTR) {
                continue;
            }
            break;
        }
        int xfd = sys_input_x11_fd(d.x11);
        for (int i = 0; i < nfds; i++) {
            int fd = events[i].data.fd;
            if (fd == d.inotify_fd) {
                handle_inotify(&d);
            } else if (fd == d.tap_timer_fd) {
                handle_tap_timer(&d);
            } else if (fd == d.x11_retry_timer_fd) {
                uint64_t exp = 0;
                ssize_t r = read(d.x11_retry_timer_fd, &exp, sizeof(exp));
                (void)r;
                attach_x11_to_epoll(&d);
            } else if (xfd >= 0 && fd == xfd) {
                if (events[i].events & (EPOLLERR | EPOLLHUP)) {
                    epoll_ctl(d.epoll_fd, EPOLL_CTL_DEL, xfd, NULL);
                    sys_input_x11_destroy(d.x11);
                    d.x11 = sys_input_x11_create();
                    struct itimerspec retry = { .it_interval = { .tv_sec = 1 }, .it_value = { .tv_sec = 1 } };
                    timerfd_settime(d.x11_retry_timer_fd, 0, &retry, NULL);
                } else {
                    sys_input_x11_process(d.x11);
                }
            } else {
                ssize_t idx = find_dev_by_fd(&d, fd);
                if (idx >= 0) {
                    handle_dev_events(&d, (size_t)idx);
                }
            }
        }
    }

    cleanup_daemon(&d);
    return 0;
}
