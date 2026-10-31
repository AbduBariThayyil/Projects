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
#include <sys/stat.h>
#include <sys/types.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <cairo/cairo.h>
#include <cairo/cairo-xlib.h>
#include <pango/pangocairo.h>
#include <glib.h>

#define FIFO_PATH "/tmp/keyholder-hud.fifo"
#define HUD_WIDTH  330
#define HUD_HEIGHT 56

static Display *dpy = NULL;
static int screen = 0;
static Window root = None;
static Window win = None;
static Visual *visual = NULL;
static Colormap colormap;
static int depth = 32;
static cairo_surface_t *surface = NULL;
static cairo_t *cr = NULL;
static GMainLoop *loop = NULL;

static char current_mode[32] = "idle";
static char current_title[128] = "KeyHolder";
static char current_sub[128] = "Idle";
static gboolean is_visible = FALSE;
static guint hide_timer_id = 0;

/* Helper: Draw smooth rounded rectangles */
static void draw_rounded_rect(cairo_t *c, double x, double y, double w, double h, double r) {
    cairo_new_sub_path(c);
    cairo_arc(c, x + w - r, y + r, r, -G_PI / 2.0, 0.0);
    cairo_arc(c, x + w - r, y + h - r, r, 0.0, G_PI / 2.0);
    cairo_arc(c, x + r, y + h - r, r, G_PI / 2.0, G_PI);
    cairo_arc(c, x + r, y + r, r, G_PI, 3.0 * G_PI / 2.0);
    cairo_close_path(c);
}

/* Render the HUD using Cairo and Pango */
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
    PangoFontDescription *font_desc = pango_font_description_from_string("JetBrains Mono Nerd Font 20");
    pango_layout_set_font_description(layout, font_desc);
    pango_font_description_free(font_desc);

    pango_layout_set_text(layout, icon_glyph, -1);
    cairo_set_source_rgb(cr, acc_r, acc_g, acc_b);
    cairo_move_to(cr, 16.0, (HUD_HEIGHT - 28.0) / 2.0);
    pango_cairo_show_layout(cr, layout);

    /* Title text */
    font_desc = pango_font_description_from_string("JetBrains Mono Nerd Font Bold 10.5");
    pango_layout_set_font_description(layout, font_desc);
    pango_font_description_free(font_desc);

    pango_layout_set_text(layout, current_title, -1);
    cairo_set_source_rgb(cr, 205.0 / 255.0, 214.0 / 255.0, 244.0 / 255.0); /* Catppuccin Text (#cdd6f4) */
    cairo_move_to(cr, 46.0, 9.0);
    pango_cairo_show_layout(cr, layout);

    /* Subtitle text */
    font_desc = pango_font_description_from_string("JetBrains Mono Nerd Font 9");
    pango_layout_set_font_description(layout, font_desc);
    pango_font_description_free(font_desc);

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

    font_desc = pango_font_description_from_string("JetBrains Mono Nerd Font Bold 8");
    pango_layout_set_font_description(layout, font_desc);
    pango_font_description_free(font_desc);

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

/* Hide callback */
static gboolean hide_timer_cb(gpointer data) {
    (void)data;
    if (is_visible) {
        XUnmapWindow(dpy, win);
        XFlush(dpy);
        is_visible = FALSE;
    }
    hide_timer_id = 0;
    return G_SOURCE_REMOVE;
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
        if (is_visible) {
            XUnmapWindow(dpy, win);
            XFlush(dpy);
            is_visible = FALSE;
        }
        return;
    }

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
        hide_timer_id = g_timeout_add(1200, hide_timer_cb, NULL);
    }
}

/* X11 Expose / Event Handler */
static gboolean x11_event_cb(GIOChannel *source, GIOCondition cond, gpointer data) {
    (void)source; (void)cond; (void)data;
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
    int x = screen_w - HUD_WIDTH - 18;
    int y = 50; /* Positioned directly under Polybar */

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

int main(int argc, char **argv) {
    /* If invoked with arguments as a sender CLI */
    if (argc >= 2) {
        if (strcmp(argv[1], "--hide") == 0) {
            int fd = open(FIFO_PATH, O_WRONLY | O_NONBLOCK);
            if (fd >= 0) {
                dprintf(fd, "hide||\n");
                close(fd);
            }
            return 0;
        } else if (argc >= 4 && strcmp(argv[1], "--update") == 0) {
            int fd = open(FIFO_PATH, O_WRONLY | O_NONBLOCK);
            if (fd >= 0) {
                dprintf(fd, "%s|%s|%s\n", argv[2], argv[3], argc >= 5 ? argv[4] : "");
                close(fd);
            }
            return 0;
        }
    }

    /* Daemon Mode: Only allow single instance */
    unlink(FIFO_PATH);
    if (mkfifo(FIFO_PATH, 0666) == -1) {
        perror("mkfifo");
    }

    init_window();

    /* Open FIFO non-blocking */
    int fifo_fd = open(FIFO_PATH, O_RDONLY | O_NONBLOCK);
    if (fifo_fd < 0) {
        perror("open fifo");
        exit(1);
    }

    /* Open dummy writer so read doesn't hit EOF when client closes */
    int dummy_fd = open(FIFO_PATH, O_WRONLY | O_NONBLOCK);
    (void)dummy_fd;

    GIOChannel *fifo_channel = g_io_channel_unix_new(fifo_fd);
    g_io_channel_set_flags(fifo_channel, G_IO_FLAG_NONBLOCK, NULL);
    g_io_add_watch(fifo_channel, G_IO_IN | G_IO_PRI, fifo_read_cb, NULL);

    GIOChannel *x_channel = g_io_channel_unix_new(ConnectionNumber(dpy));
    g_io_add_watch(x_channel, G_IO_IN | G_IO_PRI, x11_event_cb, NULL);

    loop = g_main_loop_new(NULL, FALSE);
    g_main_loop_run(loop);

    cairo_destroy(cr);
    cairo_surface_destroy(surface);
    XDestroyWindow(dpy, win);
    XCloseDisplay(dpy);
    unlink(FIFO_PATH);

    return 0;
}
