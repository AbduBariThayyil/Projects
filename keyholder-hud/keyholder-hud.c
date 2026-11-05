/* =============================================================
 * keyholder-hud: Native High-Performance Overlay HUD for KeyHolder
 * Zero-latency Cairo X11 overlay window with Catppuccin Mocha styling
 * Replaces intrusive desktop notification spam with a sleek HUD
 * ============================================================= */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <limits.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <cairo/cairo.h>
#include <cairo/cairo-xlib.h>
#include <pango/pangocairo.h>
#include <glib.h>
#include <glib-unix.h>

#define LEGACY_FIFO_PATH "/tmp/keyholder-hud.fifo"
#define HUD_WIDTH  330
#define HUD_HEIGHT 56

static Display *dpy = NULL;
static int screen = 0;
static Window root = None;
static Window win = None;
static Visual *visual = NULL;
static Colormap colormap = None;
static int depth = 32;
static cairo_surface_t *surface = NULL;
static cairo_t *cr = NULL;
static GMainLoop *loop = NULL;

static char current_mode[32] = "idle";
static char current_title[128] = "KeyHolder";
static char current_sub[128] = "Idle";
static gboolean is_visible = FALSE;
static guint hide_timer_id = 0;
static guint idle_exit_timer_id = 0;

static int fifo_fd = -1;
static int dummy_fd = -1;
static GIOChannel *fifo_channel = NULL;
static GIOChannel *x_channel = NULL;
static guint fifo_watch_id = 0;
static guint x_watch_id = 0;
static guint sigterm_id = 0;
static guint sigint_id = 0;
static char fifo_path[512] = {0};

/* Cached Pango font descriptions */
static PangoFontDescription *f_icon = NULL;
static PangoFontDescription *f_title = NULL;
static PangoFontDescription *f_sub = NULL;
static PangoFontDescription *f_badge = NULL;

static void init_fonts(void) {
    if (!f_icon)
        f_icon = pango_font_description_from_string("JetBrains Mono Nerd Font 20");
    if (!f_title)
        f_title = pango_font_description_from_string("JetBrains Mono Nerd Font Bold 10.5");
    if (!f_sub)
        f_sub = pango_font_description_from_string("JetBrains Mono Nerd Font 9");
    if (!f_badge)
        f_badge = pango_font_description_from_string("JetBrains Mono Nerd Font Bold 8");
}

static void free_fonts(void) {
    if (f_icon) {
        pango_font_description_free(f_icon);
        f_icon = NULL;
    }
    if (f_title) {
        pango_font_description_free(f_title);
        f_title = NULL;
    }
    if (f_sub) {
        pango_font_description_free(f_sub);
        f_sub = NULL;
    }
    if (f_badge) {
        pango_font_description_free(f_badge);
        f_badge = NULL;
    }
}

/* Helper: Determine per-user runtime FIFO path */
static void get_fifo_path(char *out, size_t sz) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (xdg && *xdg != '\0') {
        snprintf(out, sz, "%s/keyholder-hud.fifo", xdg);
    } else {
        snprintf(out, sz, "/tmp/keyholder-hud-%u.fifo", (unsigned int)getuid());
    }
}

/* Helper: Draw smooth rounded rectangles */
static void draw_rounded_rect(cairo_t *c, double x, double y, double w, double h, double r) {
    cairo_new_sub_path(c);
    cairo_arc(c, x + w - r, y + r, r, -G_PI / 2.0, 0.0);
    cairo_arc(c, x + w - r, y + h - r, r, 0.0, G_PI / 2.0);
    cairo_arc(c, x + r, y + h - r, r, G_PI / 2.0, G_PI);
    cairo_arc(c, x + r, y + r, r, G_PI, 3.0 * G_PI / 2.0);
    cairo_close_path(c);
}

/* Render the HUD using Cairo and cached Pango font descriptions */
static void render_hud(void) {
    if (!cr || !surface) return;

    cairo_push_group(cr);

    /* Clear surface with true alpha transparency */
    cairo_set_operator(cr, CAIRO_OPERATOR_CLEAR);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    /* Main background card: Catppuccin Base (#1e1e2e) at 94% opacity */
    draw_rounded_rect(cr, 1.0, 1.0, HUD_WIDTH - 2.0, HUD_HEIGHT - 2.0, 12.0);
    cairo_set_source_rgba(cr, 30.0 / 255.0, 30.0 / 255.0, 46.0 / 255.0, 0.94);
    cairo_fill_preserve(cr);

    /* Subtle Border: Catppuccin Surface0 (#313244) */
    cairo_set_source_rgba(cr, 49.0 / 255.0, 50.0 / 255.0, 68.0 / 255.0, 0.90);
    cairo_set_line_width(cr, 1.5);
    cairo_stroke(cr);

    /* Accent color selection */
    double acc_r = 166.0 / 255.0, acc_g = 227.0 / 255.0, acc_b = 161.0 / 255.0; /* Green (#a6e3a1) for spam */
    const char *badge_text = "SPAM";
    const char *icon_glyph = "󰌌";

    if (strcmp(current_mode, "hold") == 0) {
        acc_r = 116.0 / 255.0; acc_g = 199.0 / 255.0; acc_b = 236.0 / 255.0; /* Sapphire (#74c7ec) */
        badge_text = "HOLD";
    } else if (strcmp(current_mode, "listen") == 0) {
        acc_r = 250.0 / 255.0; acc_g = 179.0 / 255.0; acc_b = 135.0 / 255.0; /* Peach (#fab387) */
        badge_text = "WAIT";
    } else if (strcmp(current_mode, "stop") == 0) {
        acc_r = 243.0 / 255.0; acc_g = 139.0 / 255.0; acc_b = 168.0 / 255.0; /* Red (#f38ba8) */
        badge_text = "STOP";
        icon_glyph = "󰅖";
    }

    /* Left accent vertical strip */
    draw_rounded_rect(cr, 5.0, 8.0, 4.0, HUD_HEIGHT - 16.0, 2.0);
    cairo_set_source_rgb(cr, acc_r, acc_g, acc_b);
    cairo_fill(cr);

    /* Icon glyph */
    PangoLayout *layout = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(layout, f_icon);
    pango_layout_set_text(layout, icon_glyph, -1);
    cairo_set_source_rgb(cr, acc_r, acc_g, acc_b);
    cairo_move_to(cr, 16.0, (HUD_HEIGHT - 28.0) / 2.0);
    pango_cairo_show_layout(cr, layout);

    /* Title text */
    pango_layout_set_font_description(layout, f_title);
    pango_layout_set_text(layout, current_title, -1);
    cairo_set_source_rgb(cr, 205.0 / 255.0, 214.0 / 255.0, 244.0 / 255.0); /* Catppuccin Text (#cdd6f4) */
    cairo_move_to(cr, 46.0, 9.0);
    pango_cairo_show_layout(cr, layout);

    /* Subtitle text */
    pango_layout_set_font_description(layout, f_sub);
    pango_layout_set_text(layout, current_sub, -1);
    cairo_set_source_rgb(cr, 166.0 / 255.0, 173.0 / 255.0, 200.0 / 255.0); /* Catppuccin Subtext0 (#a6adc8) */
    cairo_move_to(cr, 46.0, 29.0);
    pango_cairo_show_layout(cr, layout);

    /* Badge pill on the right */
    int badge_w = 48, badge_h = 20;
    int badge_x = HUD_WIDTH - badge_w - 12;
    int badge_y = (HUD_HEIGHT - badge_h) / 2;

    draw_rounded_rect(cr, badge_x, badge_y, badge_w, badge_h, 6.0);
    cairo_set_source_rgba(cr, acc_r, acc_g, acc_b, 0.18);
    cairo_fill_preserve(cr);
    cairo_set_source_rgba(cr, acc_r, acc_g, acc_b, 0.50);
    cairo_set_line_width(cr, 1.0);
    cairo_stroke(cr);

    pango_layout_set_font_description(layout, f_badge);
    pango_layout_set_text(layout, badge_text, -1);
    int text_w, text_h;
    pango_layout_get_pixel_size(layout, &text_w, &text_h);
    cairo_set_source_rgb(cr, acc_r, acc_g, acc_b);
    cairo_move_to(cr, badge_x + (badge_w - text_w) / 2.0, badge_y + (badge_h - text_h) / 2.0);
    pango_cairo_show_layout(cr, layout);

    g_object_unref(layout);

    /* Present */
    cairo_pop_group_to_source(cr);
    cairo_paint(cr);
    cairo_surface_flush(surface);
    XFlush(dpy);
}

/* Idle exit handlers */
static gboolean idle_exit_cb(gpointer data) {
    (void)data;
    idle_exit_timer_id = 0;
    if (loop && g_main_loop_is_running(loop)) {
        g_main_loop_quit(loop);
    }
    return G_SOURCE_REMOVE;
}

static void schedule_idle_exit(guint delay_ms) {
    if (idle_exit_timer_id) {
        g_source_remove(idle_exit_timer_id);
        idle_exit_timer_id = 0;
    }
    idle_exit_timer_id = g_timeout_add(delay_ms, idle_exit_cb, NULL);
}

static void cancel_idle_exit(void) {
    if (idle_exit_timer_id) {
        g_source_remove(idle_exit_timer_id);
        idle_exit_timer_id = 0;
    }
}

/* Clean shutdown signal handler callback */
static gboolean sig_handler_cb(gpointer data) {
    (void)data;
    if (loop && g_main_loop_is_running(loop)) {
        g_main_loop_quit(loop);
    }
    return G_SOURCE_CONTINUE;
}

/* Hide callback */
static gboolean hide_timer_cb(gpointer data) {
    (void)data;
    if (is_visible && dpy && win != None) {
        XUnmapWindow(dpy, win);
        XFlush(dpy);
        is_visible = FALSE;
    }
    hide_timer_id = 0;
    /* Auto-exit after being hidden if no new command arrives */
    schedule_idle_exit(2500);
    return G_SOURCE_REMOVE;
}

/* Complete resource deallocation */
static void cleanup(void) {
    if (hide_timer_id) {
        g_source_remove(hide_timer_id);
        hide_timer_id = 0;
    }
    if (idle_exit_timer_id) {
        g_source_remove(idle_exit_timer_id);
        idle_exit_timer_id = 0;
    }
    if (sigterm_id) {
        g_source_remove(sigterm_id);
        sigterm_id = 0;
    }
    if (sigint_id) {
        g_source_remove(sigint_id);
        sigint_id = 0;
    }
    if (fifo_watch_id) {
        g_source_remove(fifo_watch_id);
        fifo_watch_id = 0;
    }
    if (x_watch_id) {
        g_source_remove(x_watch_id);
        x_watch_id = 0;
    }
    if (fifo_channel) {
        g_io_channel_unref(fifo_channel);
        fifo_channel = NULL;
    }
    if (x_channel) {
        g_io_channel_unref(x_channel);
        x_channel = NULL;
    }
    if (dummy_fd >= 0) {
        close(dummy_fd);
        dummy_fd = -1;
    }
    if (fifo_fd >= 0) {
        close(fifo_fd);
        fifo_fd = -1;
    }
    free_fonts();
    if (cr) {
        cairo_destroy(cr);
        cr = NULL;
    }
    if (surface) {
        cairo_surface_destroy(surface);
        surface = NULL;
    }
    if (dpy) {
        if (win != None) {
            XDestroyWindow(dpy, win);
            win = None;
        }
        if (colormap != None && colormap != DefaultColormap(dpy, screen)) {
            XFreeColormap(dpy, colormap);
            colormap = None;
        }
        XCloseDisplay(dpy);
        dpy = NULL;
    }
    if (fifo_path[0] != '\0') {
        unlink(fifo_path);
    }
    if (strcmp(fifo_path, LEGACY_FIFO_PATH) != 0) {
        unlink(LEGACY_FIFO_PATH);
    }
}

/* Update HUD state from incoming message */
static void update_hud_state(const char *mode, const char *title, const char *sub) {
    if (hide_timer_id) {
        g_source_remove(hide_timer_id);
        hide_timer_id = 0;
    }

    g_strlcpy(current_mode, mode ? mode : "idle", sizeof(current_mode));
    g_strlcpy(current_title, title ? title : "", sizeof(current_title));
    g_strlcpy(current_sub, sub ? sub : "", sizeof(current_sub));

    if (strcmp(current_mode, "hide") == 0) {
        if (is_visible && dpy && win != None) {
            XUnmapWindow(dpy, win);
            XFlush(dpy);
            is_visible = FALSE;
        }
        schedule_idle_exit(2000);
        return;
    }

    /* Active activity: cancel idle exit */
    cancel_idle_exit();

    render_hud();

    if (!is_visible) {
        XMapRaised(dpy, win);
        XFlush(dpy);
        is_visible = TRUE;
    } else {
        XRaiseWindow(dpy, win);
        XFlush(dpy);
    }

    if (strcmp(current_mode, "stop") == 0) {
        hide_timer_id = g_timeout_add(800, hide_timer_cb, NULL);
    } else if (strstr(current_title, "SPAMMING") || strstr(current_title, "HOLDING") || strcmp(current_mode, "hold") == 0) {
        /* Stays visible continuously while active */
    } else if (strstr(current_sub, "Delay:") || strstr(current_title, "KeyHolder [Spam]")) {
        hide_timer_id = g_timeout_add(2000, hide_timer_cb, NULL);
    } else {
        hide_timer_id = g_timeout_add(2500, hide_timer_cb, NULL);
    }
}

/* X11 Expose / Event Handler */
static gboolean x11_event_cb(GIOChannel *source, GIOCondition cond, gpointer data) {
    (void)source; (void)cond; (void)data;
    if (!dpy) return G_SOURCE_CONTINUE;
    while (XPending(dpy)) {
        XEvent ev;
        XNextEvent(dpy, &ev);
        if (ev.type == Expose && is_visible) {
            render_hud();
        }
    }
    return G_SOURCE_CONTINUE;
}

/* FIFO reader callback */
static gboolean fifo_read_cb(GIOChannel *source, GIOCondition cond, gpointer data) {
    (void)data;
    if (cond & (G_IO_IN | G_IO_PRI)) {
        int fd = g_io_channel_unix_get_fd(source);
        char buf[1024];
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        if (n > 0) {
            buf[n] = '\0';
            char *saveptr = NULL;
            char *line = strtok_r(buf, "\r\n", &saveptr);
            while (line) {
                g_strstrip(line);
                if (strlen(line) > 0) {
                    char *pipe1 = strchr(line, '|');
                    if (pipe1) {
                        *pipe1 = '\0';
                        char *pipe2 = strchr(pipe1 + 1, '|');
                        if (pipe2) {
                            *pipe2 = '\0';
                            update_hud_state(line, pipe1 + 1, pipe2 + 1);
                        } else {
                            update_hud_state(line, pipe1 + 1, "");
                        }
                    } else {
                        update_hud_state(line, "", "");
                    }
                }
                line = strtok_r(NULL, "\r\n", &saveptr);
            }
        }
    }
    return G_SOURCE_CONTINUE;
}

/* Initialize 32-bit ARGB X11 Window */
static void init_window(void) {
    dpy = XOpenDisplay(NULL);
    if (!dpy) {
        fprintf(stderr, "keyholder-hud: Cannot open X display\n");
        cleanup();
        exit(1);
    }

    screen = DefaultScreen(dpy);
    root = RootWindow(dpy, screen);

    /* Locate 32-bit visual for true ARGB alpha transparency */
    XVisualInfo vinfo;
    if (!XMatchVisualInfo(dpy, screen, 32, TrueColor, &vinfo)) {
        fprintf(stderr, "keyholder-hud: No 32-bit visual available, falling back\n");
        visual = DefaultVisual(dpy, screen);
        depth = DefaultDepth(dpy, screen);
        colormap = DefaultColormap(dpy, screen);
    } else {
        visual = vinfo.visual;
        depth = vinfo.depth;
        colormap = XCreateColormap(dpy, root, visual, AllocNone);
    }

    int screen_w = DisplayWidth(dpy, screen);
    int screen_h = DisplayHeight(dpy, screen);
    int x = (screen_w - HUD_WIDTH) / 2;
    int y = screen_h - HUD_HEIGHT - 45;

    XSetWindowAttributes attrs;
    attrs.override_redirect = True;
    attrs.colormap = colormap;
    attrs.border_pixel = 0;
    attrs.background_pixmap = None;
    attrs.event_mask = ExposureMask;

    win = XCreateWindow(
        dpy, root, x, y, HUD_WIDTH, HUD_HEIGHT, 0,
        depth, InputOutput, visual,
        CWOverrideRedirect | CWColormap | CWBorderPixel | CWBackPixmap | CWEventMask,
        &attrs
    );

    /* EWMH atoms to keep window above fullscreen */
    Atom net_wm_type = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
    Atom net_wm_type_dock = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_DOCK", False);
    XChangeProperty(dpy, win, net_wm_type, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)&net_wm_type_dock, 1);

    Atom net_wm_state = XInternAtom(dpy, "_NET_WM_STATE", False);
    Atom net_wm_state_above = XInternAtom(dpy, "_NET_WM_STATE_ABOVE", False);
    Atom net_wm_state_stays_on_top = XInternAtom(dpy, "_NET_WM_STATE_STAYS_ON_TOP", False);
    Atom state_atoms[2] = { net_wm_state_above, net_wm_state_stays_on_top };
    XChangeProperty(dpy, win, net_wm_state, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)state_atoms, 2);

    XClassHint class_hint = { "keyholder-hud", "keyholder-hud" };
    XSetClassHint(dpy, win, &class_hint);

    surface = cairo_xlib_surface_create(dpy, win, visual, HUD_WIDTH, HUD_HEIGHT);
    cr = cairo_create(surface);
}

/* Spawn daemon in background */
static void spawn_daemon(void) {
    char exe[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (len > 0) {
        exe[len] = '\0';
    }

    pid_t pid = fork();
    if (pid < 0) {
        perror("keyholder-hud: fork");
        return;
    }
    if (pid == 0) {
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            close(devnull);
        }
        setsid();
        if (len > 0) {
            execl(exe, "keyholder-hud", (char *)NULL);
        } else {
            execlp("keyholder-hud", "keyholder-hud", (char *)NULL);
        }
        _exit(127);
    }
}

/* CLI message delivery with on-demand daemon autospawn */
static int send_cli_message(const char *msg) {
    char path[512];
    get_fifo_path(path, sizeof(path));

    int fd = open(path, O_WRONLY | O_NONBLOCK);
    if (fd < 0 && strcmp(path, LEGACY_FIFO_PATH) != 0) {
        fd = open(LEGACY_FIFO_PATH, O_WRONLY | O_NONBLOCK);
    }

    if (fd < 0) {
        spawn_daemon();
        struct timespec ts = { .tv_sec = 0, .tv_nsec = 10 * 1000 * 1000 }; /* 10ms */
        for (int i = 0; i < 15; i++) {
            nanosleep(&ts, NULL);
            fd = open(path, O_WRONLY | O_NONBLOCK);
            if (fd >= 0) {
                break;
            }
        }
    }

    if (fd < 0) {
        fprintf(stderr, "keyholder-hud: failed to connect to daemon FIFO (%s)\n", path);
        return 1;
    }

    size_t total = strlen(msg);
    size_t sent = 0;
    while (sent < total) {
        ssize_t n = write(fd, msg + sent, total - sent);
        if (n > 0) {
            sent += (size_t)n;
        } else if (n < 0) {
            if (errno == EINTR) continue;
            break;
        }
    }

    close(fd);
    return 0;
}

int main(int argc, char **argv) {
    /* Prevent premature SIGPIPE aborts */
    signal(SIGPIPE, SIG_IGN);

    /* If invoked with arguments as a sender CLI */
    if (argc >= 2) {
        if (strcmp(argv[1], "--hide") == 0) {
            return send_cli_message("hide||\n");
        } else if (strcmp(argv[1], "--update") == 0) {
            const char *mode = argc >= 3 ? argv[2] : "";
            const char *title = argc >= 4 ? argv[3] : "";
            const char *sub = argc >= 5 ? argv[4] : "";
            char msg[512];
            snprintf(msg, sizeof(msg), "%s|%s|%s\n", mode, title, sub);
            return send_cli_message(msg);
        } else if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
            printf("Usage: %s [--update <mode> <title> [subtitle] | --hide]\n", argv[0]);
            return 0;
        }
    }

    /* Daemon Mode: Determine FIFO path */
    get_fifo_path(fifo_path, sizeof(fifo_path));

    /* Check if an active daemon is already listening */
    int test_fd = open(fifo_path, O_WRONLY | O_NONBLOCK);
    if (test_fd >= 0) {
        close(test_fd);
        /* Active daemon already running */
        return 0;
    }

    unlink(fifo_path);
    if (mkfifo(fifo_path, 0600) == -1) {
        perror("mkfifo");
    }

    if (strcmp(fifo_path, LEGACY_FIFO_PATH) != 0) {
        unlink(LEGACY_FIFO_PATH);
        if (symlink(fifo_path, LEGACY_FIFO_PATH) == -1) {
            perror("symlink legacy fifo");
        }
    }

    init_fonts();
    init_window();

    /* Open FIFO non-blocking */
    fifo_fd = open(fifo_path, O_RDONLY | O_NONBLOCK);
    if (fifo_fd < 0) {
        perror("open fifo");
        cleanup();
        exit(1);
    }

    /* Open dummy writer so read doesn't hit EOF when client closes */
    dummy_fd = open(fifo_path, O_WRONLY | O_NONBLOCK);

    fifo_channel = g_io_channel_unix_new(fifo_fd);
    g_io_channel_set_flags(fifo_channel, G_IO_FLAG_NONBLOCK, NULL);
    fifo_watch_id = g_io_add_watch(fifo_channel, G_IO_IN | G_IO_PRI, fifo_read_cb, NULL);

    x_channel = g_io_channel_unix_new(ConnectionNumber(dpy));
    x_watch_id = g_io_add_watch(x_channel, G_IO_IN | G_IO_PRI, x11_event_cb, NULL);

    loop = g_main_loop_new(NULL, FALSE);
    sigterm_id = g_unix_signal_add(SIGTERM, sig_handler_cb, loop);
    sigint_id = g_unix_signal_add(SIGINT, sig_handler_cb, loop);

    schedule_idle_exit(10000);

    g_main_loop_run(loop);

    g_main_loop_unref(loop);
    loop = NULL;

    cleanup();

    return 0;
}
