#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <time.h>
#include <pwd.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

static int lock_fd = -1;

static void release_lock(void) {
    if (lock_fd >= 0) {
        flock(lock_fd, LOCK_UN);
        close(lock_fd);
        lock_fd = -1;
    }
}

static int acquire_lock(void) {
    char lock_path[512];
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (xdg && xdg[0] != '\0') {
        snprintf(lock_path, sizeof(lock_path), "%s/xmodmap_watcher.lock", xdg);
    } else {
        snprintf(lock_path, sizeof(lock_path), "/tmp/xmodmap_watcher-%u.lock", (unsigned)getuid());
    }

    lock_fd = open(lock_path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
    if (lock_fd < 0) {
        return -1;
    }

    if (flock(lock_fd, LOCK_EX | LOCK_NB) != 0) {
        close(lock_fd);
        lock_fd = -1;
        return 1; /* Locked by another running instance */
    }

    if (ftruncate(lock_fd, 0) == 0) {
        char buf[32];
        int len = snprintf(buf, sizeof(buf), "%d\n", (int)getpid());
        if (len > 0) {
            ssize_t ret = write(lock_fd, buf, (size_t)len);
            (void)ret;
        }
    }

    return 0;
}

static void on_signal(int sig) {
    (void)sig;
    release_lock();
    _exit(0);
}

static int on_io_error(Display *dpy) {
    (void)dpy;
    release_lock();
    _exit(0);
}

static const char *get_user_home(void) {
    const char *home = getenv("HOME");
    if (home && home[0] != '\0') {
        return home;
    }
    struct passwd *pw = getpwuid(getuid());
    if (pw && pw->pw_dir && pw->pw_dir[0] != '\0') {
        return pw->pw_dir;
    }
    return NULL;
}

static int needs_remap(Display *dpy) {
    XModifierKeymap *map = XGetModifierMapping(dpy);
    if (!map) return 1;

    int found_hyper = 0;
    for (int i = 0; i < map->max_keypermod; i++) {
        KeyCode kc = map->modifiermap[Mod3MapIndex * map->max_keypermod + i];
        if (kc != 0) {
            KeySym ks = XkbKeycodeToKeysym(dpy, kc, 0, 0);
            if (ks == XK_Hyper_L) {
                found_hyper = 1;
                break;
            }
        }
    }
    XFreeModifiermap(map);
    return !found_hyper;
}

static void apply_xmodmap(void) {
    char path[512];
    const char *home = get_user_home();
    if (!home) return;
    if (snprintf(path, sizeof(path), "%s/.Xmodmap", home) >= (int)sizeof(path)) return;
    if (access(path, R_OK) != 0) return;

    pid_t pid = fork();
    if (pid == 0) {
        if (lock_fd >= 0) close(lock_fd);
        close(STDIN_FILENO);
        close(STDOUT_FILENO);
        close(STDERR_FILENO);
        execlp("xmodmap", "xmodmap", path, (char *)NULL);
        _exit(0);
    }
}

static double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

int main(void) {
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    signal(SIGHUP, on_signal);
    signal(SIGCHLD, SIG_IGN);

    XSetIOErrorHandler(on_io_error);

    if (acquire_lock() != 0) {
        /* Another instance is running, exit cleanly with 0 */
        return 0;
    }

    Display *dpy = NULL;
    while (!dpy) {
        dpy = XOpenDisplay(NULL);
        if (!dpy) sleep(1);
    }

    int xkb_opcode = 0, xkb_event = 0, xkb_error = 0;
    int xkb_major = XkbMajorVersion, xkb_minor = XkbMinorVersion;
    int has_xkb = XkbQueryExtension(dpy, &xkb_opcode, &xkb_event, &xkb_error, &xkb_major, &xkb_minor);
    if (has_xkb) {
        XkbSelectEvents(dpy, XkbUseCoreKbd, XkbAllEventsMask, XkbAllEventsMask);
    }

    /* Initial check on launch */
    if (needs_remap(dpy)) {
        apply_xmodmap();
    }

    double last_check = 0.0;
    XEvent ev;

    while (1) {
        XNextEvent(dpy, &ev);
        int trigger = 0;

        if (ev.type == MappingNotify) {
            XRefreshKeyboardMapping(&ev.xmapping);
            trigger = 1;
        } else if (has_xkb && ev.type == xkb_event) {
            XkbEvent *xkb_ev = (XkbEvent *)&ev;
            if (xkb_ev->any.xkb_type == XkbNewKeyboardNotify ||
                xkb_ev->any.xkb_type == XkbMapNotify) {
                if (xkb_ev->any.xkb_type == XkbMapNotify) {
                    XkbRefreshKeyboardMapping(&xkb_ev->map);
                }
                trigger = 1;
            }
        }

        if (trigger) {
            double now = get_time_sec();
            /* Debounce 200ms */
            if (now - last_check > 0.2) {
                last_check = now;
                if (needs_remap(dpy)) {
                    apply_xmodmap();
                }
            }
        }
    }

    XCloseDisplay(dpy);
    release_lock();
    return 0;
}
