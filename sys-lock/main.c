#include "sys-lock.h"
#include "grab.h"
#include "blur.h"
#include "wallpaper.h"
#include "ui.h"
#include "auth_pam.h"
#include "auth_fprint.h"

typedef enum {
    MODE_BLUR = 0,
    MODE_RICE,
    MODE_WALLPAPER,
    MODE_DARK
} LockMode;

static volatile sig_atomic_t g_running = 1;

static void sig_handler(int sig) {
    (void)sig;
    g_running = 0;
}

static double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + (ts.tv_nsec / 1e9);
}

static void spawn_async(const char *cmd) {
    if (!cmd) return;
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        _exit(127);
    }
}

static void print_usage(const char *prog) {
    printf("sys-lock %s - Instant Native PAM Screen Locker\n", SYS_LOCK_VERSION);
    printf("Usage: %s [options]\n\n", prog);
    printf("Options:\n");
    printf("  --blur             In-memory 3-pass blurred desktop background (default)\n");
    printf("  --rice             Use current bspwm rice wallpaper\n");
    printf("  --wallpaper <path> Use custom image wallpaper\n");
    printf("  --dark             Solid Catppuccin Mocha (#1e1e2e) background\n");
    printf("  --test             Dry-run integration test (creates, renders, verifies, exits)\n");
    printf("  --version          Display version information\n");
    printf("  --help             Display this help message\n");
}

int main(int argc, char **argv) {
    LockMode mode = MODE_BLUR;
    const char *custom_wallpaper = NULL;
    bool test_mode = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--blur") == 0) {
            mode = MODE_BLUR;
        } else if (strcmp(argv[i], "--rice") == 0) {
            mode = MODE_RICE;
        } else if (strcmp(argv[i], "--wallpaper") == 0) {
            if (i + 1 < argc) {
                custom_wallpaper = argv[++i];
                mode = MODE_WALLPAPER;
            } else {
                fprintf(stderr, "Error: --wallpaper requires an image path argument.\n");
                return 1;
            }
        } else if (strcmp(argv[i], "--dark") == 0) {
            mode = MODE_DARK;
        } else if (strcmp(argv[i], "--test") == 0) {
            test_mode = true;
        } else if (strcmp(argv[i], "--version") == 0 || strcmp(argv[i], "-v") == 0) {
            printf("sys-lock %s\n", SYS_LOCK_VERSION);
            return 0;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    /* Signal Handlers */
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);
    signal(SIGPIPE, SIG_IGN);
    signal(SIGCHLD, SIG_IGN);

    /* Determine user */
    const char *username = getenv("USER");
    if (!username || username[0] == '\0') {
        username = "vibecoder";
    }

    /* Setup non-blocking IPC pipe */
    int pipe_fds[2];
    if (pipe2(pipe_fds, O_CLOEXEC | O_NONBLOCK) != 0) {
        perror("pipe2 failed");
        return 1;
    }

    /* Open X11 Display */
    Display *dpy = XOpenDisplay(NULL);
    if (!dpy) {
        fprintf(stderr, "Error: Cannot open X display.\n");
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        return 1;
    }

    int screen = DefaultScreen(dpy);
    ScreenGeometry geom;
    if (grab_get_screen_geometry(dpy, &geom) != 0) {
        fprintf(stderr, "Error: Failed to obtain screen geometry.\n");
        XCloseDisplay(dpy);
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        return 1;
    }

    /* Pre-capture root window BEFORE window is mapped if in blur mode */
    cairo_surface_t *bg_surface = NULL;
    if (mode == MODE_BLUR) {
        bg_surface = capture_and_blur_root(dpy, screen, geom.width, geom.height);
    } else if (mode == MODE_RICE) {
        bg_surface = load_wallpaper_surface(geom.width, geom.height, NULL, true, false);
    } else if (mode == MODE_WALLPAPER) {
        bg_surface = load_wallpaper_surface(geom.width, geom.height, custom_wallpaper, false, false);
    } else if (mode == MODE_DARK) {
        bg_surface = load_wallpaper_surface(geom.width, geom.height, NULL, false, true);
    }

    /* Fallback if background generation failed */
    if (!bg_surface) {
        bg_surface = load_wallpaper_surface(geom.width, geom.height, NULL, false, true);
    }

    /* Create Fullscreen Lock Window */
    Window win = grab_create_lock_window(dpy, screen, &geom);
    if (win == None) {
        fprintf(stderr, "Error: Failed to create lock window.\n");
        if (bg_surface) cairo_surface_destroy(bg_surface);
        XCloseDisplay(dpy);
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        return 1;
    }

    /* Create subtle blank cursor */
    Cursor blank_cursor = grab_create_blank_cursor(dpy, win);
    if (blank_cursor != None) {
        XDefineCursor(dpy, win, blank_cursor);
    }

    /* Securely Grab Keyboard and Mouse Pointer */
    if (grab_inputs(dpy, win, 100, 10000) != 0) {
        fprintf(stderr, "Error: Failed to acquire exclusive keyboard/pointer grabs.\n");
        grab_release(dpy, win, blank_cursor);
        if (bg_surface) cairo_surface_destroy(bg_surface);
        XCloseDisplay(dpy);
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        return 1;
    }

    /* Setup Cairo X11 and Double-Buffer Surfaces */
    cairo_surface_t *x11_surface = cairo_xlib_surface_create(
        dpy, win, DefaultVisual(dpy, screen), geom.width, geom.height
    );
    cairo_t *x11_cr = cairo_create(x11_surface);

    cairo_surface_t *back_buffer = cairo_image_surface_create(
        CAIRO_FORMAT_RGB24, geom.width, geom.height
    );
    cairo_t *back_cr = cairo_create(back_buffer);

    /* Initialize UI */
    UiContext ui;
    ui_init(&ui, &geom, false);

    /* Initialize Concurrent Biometric Fingerprint (fprintd D-Bus) */
    FprintContext *fprint_ctx = auth_fprint_init(username, pipe_fds[1]);
    if (fprint_ctx) {
        ui.fprint_available = true;
        ui_set_state(&ui, UI_STATE_IDLE, NULL);
    }

    /* If --test mode, verify drawing once and exit cleanly */
    if (test_mode) {
        double now = get_time_sec();
        ui_render(&ui, back_cr, bg_surface, geom.width, geom.height, now);
        cairo_set_source_surface(x11_cr, back_buffer, 0, 0);
        cairo_paint(x11_cr);
        XFlush(dpy);

        /* Cleanup and exit */
        if (fprint_ctx) auth_fprint_cleanup(fprint_ctx);
        cairo_destroy(back_cr);
        cairo_surface_destroy(back_buffer);
        cairo_destroy(x11_cr);
        cairo_surface_destroy(x11_surface);
        grab_release(dpy, win, blank_cursor);
        if (bg_surface) cairo_surface_destroy(bg_surface);
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        XCloseDisplay(dpy);
        return 0;
    }

    /* Initial Render */
    double now = get_time_sec();
    ui_render(&ui, back_cr, bg_surface, geom.width, geom.height, now);
    cairo_set_source_surface(x11_cr, back_buffer, 0, 0);
    cairo_paint(x11_cr);
    XFlush(dpy);

    /* State variables */
    char password_buffer[MAX_PASSWORD_LEN] = {0};
    int pw_length = 0;
    bool is_verifying = false;
    double reset_status_time = 0.0;
    time_t last_clock_sec = time(NULL);

    struct pollfd pfd[2];
    pfd[0].fd = ConnectionNumber(dpy);
    pfd[0].events = POLLIN;
    pfd[1].fd = pipe_fds[0];
    pfd[1].events = POLLIN;

    while (g_running) {
        int timeout_ms = 1000;
        if (ui.is_shaking) {
            timeout_ms = 16; /* 60 FPS animation loop */
        }

        int pret = poll(pfd, 2, timeout_ms);
        if (pret < 0 && errno == EINTR) {
            continue;
        }

        bool need_redraw = false;
        now = get_time_sec();

        /* Process IPC messages from PAM and fprint worker threads */
        if (pfd[1].revents & POLLIN) {
            IpcMessage msg;
            while (read(pipe_fds[0], &msg, sizeof(msg)) > 0) {
                if (msg.code == MSG_PAM_SUCCESS || msg.code == MSG_FPRINT_SUCCESS) {
                    ui_set_state(&ui, UI_STATE_FPRINT_MATCH, "Unlocked");
                    ui_render(&ui, back_cr, bg_surface, geom.width, geom.height, now);
                    cairo_set_source_surface(x11_cr, back_buffer, 0, 0);
                    cairo_paint(x11_cr);
                    XFlush(dpy);
                    g_running = 0;
                    break;
                } else if (msg.code == MSG_PAM_FAILURE) {
                    is_verifying = false;
                    ui_trigger_shake(&ui);
                    ui_set_state(&ui, UI_STATE_AUTH_FAILED, "󰅙 Authentication Failed");
                    reset_status_time = now + 2.5;
                    need_redraw = true;
                } else if (msg.code == MSG_FPRINT_FAILURE) {
                    ui_trigger_shake(&ui);
                    ui_set_state(&ui, UI_STATE_AUTH_FAILED, "󰅙 Fingerprint Not Recognized");
                    reset_status_time = now + 2.5;
                    need_redraw = true;
                } else if (msg.code == MSG_FPRINT_ACTIVE) {
                    ui.fprint_available = true;
                    ui_set_state(&ui, UI_STATE_IDLE, NULL);
                    need_redraw = true;
                } else if (msg.code == MSG_FPRINT_SWIPE_SHORT ||
                           msg.code == MSG_FPRINT_NOT_CENTERED ||
                           msg.code == MSG_FPRINT_RETRY) {
                    ui_set_state(&ui, UI_STATE_FPRINT_WARNING, msg.text);
                    reset_status_time = now + 3.0;
                    need_redraw = true;
                }
            }
        }

        if (!g_running) break;

        /* Process X11 Events */
        while (XPending(dpy)) {
            XEvent ev;
            XNextEvent(dpy, &ev);

            if (ev.type == Expose) {
                need_redraw = true;
            } else if (ev.type == KeyPress) {
                char str[32] = {0};
                KeySym ksym = NoSymbol;
                int len = XLookupString(&ev.xkey, str, sizeof(str) - 1, &ksym, NULL);

                /* Handle media & brightness hotkeys without unlocking */
                switch (ksym) {
                    case XF86XK_AudioRaiseVolume:
                        spawn_async("sys-control --vol-inc");
                        continue;
                    case XF86XK_AudioLowerVolume:
                        spawn_async("sys-control --vol-dec");
                        continue;
                    case XF86XK_AudioMute:
                        spawn_async("sys-control --vol-toggle");
                        continue;
                    case XF86XK_AudioPlay:
                    case XF86XK_AudioPause:
                        spawn_async("playerctl play-pause 2>/dev/null || mpc toggle 2>/dev/null");
                        continue;
                    case XF86XK_AudioNext:
                        spawn_async("playerctl next 2>/dev/null");
                        continue;
                    case XF86XK_AudioPrev:
                        spawn_async("playerctl previous 2>/dev/null");
                        continue;
                    case XF86XK_MonBrightnessUp:
                        spawn_async("sys-control --bri-inc");
                        continue;
                    case XF86XK_MonBrightnessDown:
                        spawn_async("sys-control --bri-dec");
                        continue;
                    default:
                        break;
                }

                if (is_verifying) {
                    continue; /* Block input while PAM is verifying */
                }

                if (ksym == XK_Escape) {
                    explicit_bzero(password_buffer, sizeof(password_buffer));
                    pw_length = 0;
                    ui_set_pw_length(&ui, 0);
                    ui_set_state(&ui, UI_STATE_IDLE, NULL);
                    need_redraw = true;
                } else if (ksym == XK_BackSpace || ksym == XK_Delete) {
                    if (pw_length > 0) {
                        password_buffer[--pw_length] = '\0';
                        ui_set_pw_length(&ui, pw_length);
                        need_redraw = true;
                    }
                } else if (ksym == XK_Return || ksym == XK_KP_Enter) {
                    if (pw_length > 0) {
                        is_verifying = true;
                        ui_set_state(&ui, UI_STATE_VERIFYING, NULL);
                        auth_pam_verify_async(username, password_buffer, pipe_fds[1]);
                        explicit_bzero(password_buffer, sizeof(password_buffer));
                        pw_length = 0;
                        ui_set_pw_length(&ui, 0);
                        need_redraw = true;
                    }
                } else if (len > 0) {
                    for (int c = 0; c < len; c++) {
                        unsigned char ch = (unsigned char)str[c];
                        if (ch >= 32 && ch < 127 && pw_length < MAX_PASSWORD_LEN - 1) {
                            password_buffer[pw_length++] = (char)ch;
                            password_buffer[pw_length] = '\0';
                        }
                    }
                    ui_set_pw_length(&ui, pw_length);
                    need_redraw = true;
                }
            }
        }

        /* Check Status Reset Timer */
        if (reset_status_time > 0.0 && now >= reset_status_time) {
            reset_status_time = 0.0;
            if (!is_verifying && pw_length == 0) {
                ui_set_state(&ui, UI_STATE_IDLE, NULL);
                need_redraw = true;
            }
        }

        /* Check Clock Update */
        time_t cur_sec = time(NULL);
        if (cur_sec != last_clock_sec) {
            last_clock_sec = cur_sec;
            need_redraw = true;
        }

        /* Check Shake Animation */
        if (ui.is_shaking) {
            need_redraw = true;
        }

        /* Render Frame */
        if (need_redraw) {
            ui_render(&ui, back_cr, bg_surface, geom.width, geom.height, now);
            cairo_set_source_surface(x11_cr, back_buffer, 0, 0);
            cairo_paint(x11_cr);
            XFlush(dpy);
        }
    }

    /* Securely clear password */
    explicit_bzero(password_buffer, sizeof(password_buffer));

    /* Cleanup Resources */
    if (fprint_ctx) {
        auth_fprint_cleanup(fprint_ctx);
    }

    cairo_destroy(back_cr);
    cairo_surface_destroy(back_buffer);
    cairo_destroy(x11_cr);
    cairo_surface_destroy(x11_surface);

    grab_release(dpy, win, blank_cursor);

    if (bg_surface) {
        cairo_surface_destroy(bg_surface);
    }

    close(pipe_fds[0]);
    close(pipe_fds[1]);
    XCloseDisplay(dpy);

    return 0;
}
