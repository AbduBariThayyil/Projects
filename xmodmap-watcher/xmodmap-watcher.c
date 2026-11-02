#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <time.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

#define PID_FILE "/tmp/.xmodmap_watcher.pid"

static int is_already_running(void) {
    FILE *f = fopen(PID_FILE, "r");
    if (f) {
        pid_t pid = 0;
        if (fscanf(f, "%d", &pid) == 1 && pid > 0) {
            if (kill(pid, 0) == 0 && pid != getpid()) {
                fclose(f);
                return 1;
            }
        }
        fclose(f);
    }
    f = fopen(PID_FILE, "w");
    if (f) {
        fprintf(f, "%d\n", getpid());
        fclose(f);
    }
    return 0;
}

static void cleanup_pid(void) {
    unlink(PID_FILE);
}

static void on_signal(int sig) {
    (void)sig;
    cleanup_pid();
    _exit(0);
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
    const char *home = getenv("HOME");
    if (!home) return;
    snprintf(path, sizeof(path), "%s/.Xmodmap", home);
    if (access(path, R_OK) != 0) return;

    pid_t pid = fork();
    if (pid == 0) {
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
    signal(SIGCHLD, SIG_IGN);

    if (is_already_running()) {
        return 0;
    }

    Display *dpy = NULL;
    while (!dpy) {
        dpy = XOpenDisplay(NULL);
        if (!dpy) sleep(1);
    }

    /* Initial check on launch */
    if (needs_remap(dpy)) {
        apply_xmodmap();
    }

    double last_check = 0.0;
    XEvent ev;

    while (1) {
        XNextEvent(dpy, &ev);
        if (ev.type == MappingNotify) {
            XRefreshKeyboardMapping(&ev.xmapping);
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
    cleanup_pid();
    return 0;
}
