/* =============================================================
 * keyholder-hud: Sleek Catppuccin Mocha Micro-Pill Overlay HUD
 * Click-through (XShape), top-center below Polybar, auto-sized,
 * zero CPU idle with automatic daemon lifecycle.
 * ============================================================= */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/shape.h>
#include <cairo/cairo-xlib.h>
#include <cairo/cairo.h>
#include <glib-unix.h>
#include <glib.h>
#include <pango/pangocairo.h>

#define LEGACY_FIFO_PATH "/tmp/keyholder-hud.fifo"
#define HUD_HEIGHT 34
#define HUD_TOP_Y  52 /* Cleanly below 44px Polybar */
#define HUD_MIN_W  156
#define HUD_MAX_W  440

typedef struct {
    bool is_stop;
    char listen[16];     /* "none", "hold", "spam" */
    char holds[128];     /* comma-separated labels */
    char spam[32];       /* label */
    double cps;
    int ms;
    bool paused;
    long base_sec;
    int64_t recv_mono_ns;
    char stop_msg[96];
} HudState;

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

static int cur_w = 210;
static int cur_h = HUD_HEIGHT;
static bool is_visible = false;
static bool pulse_bright = true;
static guint hide_timer_id = 0;
static guint idle_exit_timer_id = 0;
static guint tick_timer_id = 0;

static int fifo_fd = -1;
static int dummy_fd = -1;
static GIOChannel *fifo_channel = NULL;
static GIOChannel *x_channel = NULL;
static guint fifo_watch_id = 0;
static guint x_watch_id = 0;
static guint sigterm_id = 0;
static guint sigint_id = 0;
static char fifo_path[512] = {0};

static HudState hud = { .cps = 25.0, .ms = 40 };

static PangoFontDescription *f_tag = NULL;
static PangoFontDescription *f_chip = NULL;
static PangoFontDescription *f_meta = NULL;

static int64_t mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + (int64_t)ts.tv_nsec;
}

static void init_fonts(void) {
    if (!f_tag)  f_tag  = pango_font_description_from_string("JetBrainsMono Nerd Font Bold 8");
    if (!f_chip) f_chip = pango_font_description_from_string("JetBrainsMono Nerd Font Bold 9.5");
    if (!f_meta) f_meta = pango_font_description_from_string("JetBrainsMono Nerd Font 8.5");
}

static void free_fonts(void) {
    if (f_tag)  { pango_font_description_free(f_tag);  f_tag = NULL; }
    if (f_chip) { pango_font_description_free(f_chip); f_chip = NULL; }
    if (f_meta) { pango_font_description_free(f_meta); f_meta = NULL; }
}

static void get_fifo_path(char *out, size_t sz) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (xdg && *xdg) {
        snprintf(out, sz, "%s/keyholder-hud.fifo", xdg);
    } else {
        snprintf(out, sz, "/tmp/keyholder-hud-%u.fifo", (unsigned)getuid());
    }
}

static void draw_rounded_rect(cairo_t *c, double x, double y, double w, double h, double r) {
    if (r > h / 2.0) r = h / 2.0;
    if (r > w / 2.0) r = w / 2.0;
    cairo_new_sub_path(c);
    cairo_arc(c, x + w - r, y + r, r, -G_PI / 2.0, 0.0);
    cairo_arc(c, x + w - r, y + h - r, r, 0.0, G_PI / 2.0);
    cairo_arc(c, x + r, y + h - r, r, G_PI / 2.0, G_PI);
    cairo_arc(c, x + r, y + r, r, G_PI, 3.0 * G_PI / 2.0);
    cairo_close_path(c);
}

static int measure_text(PangoFontDescription *font, const char *txt) {
    if (!txt || !*txt || !cr) return 0;
    PangoLayout *l = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(l, font);
    pango_layout_set_text(l, txt, -1);
    int w = 0, h = 0;
    pango_layout_get_pixel_size(l, &w, &h);
    g_object_unref(l);
    return w;
}

static void draw_text_at(PangoFontDescription *font, const char *txt, double x, double y, double r, double g, double b, double a) {
    PangoLayout *l = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(l, font);
    pango_layout_set_text(l, txt, -1);
    int tw = 0, th = 0;
    pango_layout_get_pixel_size(l, &tw, &th);
    cairo_set_source_rgba(cr, r, g, b, a);
    cairo_move_to(cr, x, y - th / 2.0);
    pango_cairo_show_layout(cr, l);
    g_object_unref(l);
}

static double draw_key_chip(const char *label, double x, double cy, double ar, double ag, double ab) {
    int tw = measure_text(f_chip, label);
    double cw = (double)tw + 14.0;
    if (cw < 24.0) cw = 24.0;
    double ch = 22.0;
    double cy_top = cy - ch / 2.0;

    draw_rounded_rect(cr, x, cy_top, cw, ch, 6.0);
    cairo_set_source_rgba(cr, 49.0 / 255.0, 50.0 / 255.0, 68.0 / 255.0, 0.92);
    cairo_fill_preserve(cr);
    cairo_set_source_rgba(cr, ar, ag, ab, 0.65);
    cairo_set_line_width(cr, 1.0);
    cairo_stroke(cr);

    draw_text_at(f_chip, label, x + (cw - tw) / 2.0, cy, 205.0 / 255.0, 214.0 / 255.0, 244.0 / 255.0, 1.0);
    return cw;
}

static void format_elapsed(long sec, char *out, size_t sz) {
    if (sec < 0) sec = 0;
    snprintf(out, sz, "%ld:%02ld", sec / 60, sec % 60);
}

static int compute_target_width(void) {
    if (hud.is_stop) {
        int mw = measure_text(f_meta, hud.stop_msg[0] ? hud.stop_msg : "Released");
        int w = 44 + mw + 16;
        return w < HUD_MIN_W ? HUD_MIN_W : (w > HUD_MAX_W ? HUD_MAX_W : w);
    }

    bool listening = (strcmp(hud.listen, "none") != 0);
    if (listening) {
        char info[64];
        if (strcmp(hud.listen, "spam") == 0) {
            snprintf(info, sizeof(info), "Press key • %.0f/s (scroll ±)", hud.cps);
        } else {
            snprintf(info, sizeof(info), "Press key • Esc");
        }
        int tw = measure_text(f_tag, strcmp(hud.listen, "spam") == 0 ? "SPAM" : "HOLD");
        int iw = measure_text(f_meta, info);
        int w = 26 + tw + 14 + iw + 16;
        return w < 190 ? 190 : (w > HUD_MAX_W ? HUD_MAX_W : w);
    }

    double w = 26.0; /* left dot padding */
    bool has_hold = (hud.holds[0] != '\0');
    bool has_spam = (hud.spam[0] != '\0');

    if (has_hold) {
        w += measure_text(f_tag, (!has_spam && hud.paused) ? "PAUSE" : "HOLD") + 8.0;
        char copy[128];
        snprintf(copy, sizeof(copy), "%s", hud.holds);
        char *sp = NULL;
        for (char *tok = strtok_r(copy, ",", &sp); tok; tok = strtok_r(NULL, ",", &sp)) {
            int cw = measure_text(f_chip, tok) + 14;
            if (cw < 24) cw = 24;
            w += cw + 5.0;
        }
    }

    if (has_hold && has_spam) {
        w += 10.0; /* divider */
    }

    if (has_spam) {
        w += measure_text(f_tag, hud.paused ? "PAUSE" : "SPAM") + 8.0;
        int cw = measure_text(f_chip, hud.spam) + 14;
        if (cw < 24) cw = 24;
        w += cw + 6.0;
        char rate_str[24];
        snprintf(rate_str, sizeof(rate_str), "%.0f/s", hud.cps);
        w += measure_text(f_meta, rate_str) + 6.0;
    }

    char timer_str[24];
    long el = hud.base_sec + (long)((mono_ns() - hud.recv_mono_ns) / 1000000000LL);
    format_elapsed(el, timer_str, sizeof(timer_str));
    w += measure_text(f_meta, timer_str) + 18.0;

    int iw = (int)(w + 0.5);
    return iw < HUD_MIN_W ? HUD_MIN_W : (iw > HUD_MAX_W ? HUD_MAX_W : iw);
}

static void sync_window_geometry(int target_w) {
    if (!dpy || win == None) return;
    if (target_w == cur_w) return;
    cur_w = target_w;
    int screen_w = DisplayWidth(dpy, screen);
    int x = (screen_w - cur_w) / 2;
    XMoveResizeWindow(dpy, win, x, HUD_TOP_Y, (unsigned)cur_w, (unsigned)cur_h);
    cairo_xlib_surface_set_size(surface, cur_w, cur_h);
}

static void render_hud(void) {
    if (!cr || !surface) return;

    int target_w = compute_target_width();
    sync_window_geometry(target_w);

    double w = (double)cur_w;
    double h = (double)cur_h;
    double cy = h / 2.0;

    /* Accent color */
    double ar = 166.0 / 255.0, ag = 227.0 / 255.0, ab = 161.0 / 255.0; /* Green */
    if (hud.is_stop) {
        ar = 243.0 / 255.0; ag = 139.0 / 255.0; ab = 168.0 / 255.0; /* Red */
    } else if (strcmp(hud.listen, "hold") == 0 || (hud.holds[0] && !hud.spam[0])) {
        ar = 116.0 / 255.0; ag = 199.0 / 255.0; ab = 236.0 / 255.0; /* Sapphire */
    } else if (strcmp(hud.listen, "spam") == 0 || hud.paused) {
        ar = 250.0 / 255.0; ag = 179.0 / 255.0; ab = 135.0 / 255.0; /* Peach */
    }

    cairo_push_group(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_CLEAR);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    /* Sleek Mantle/Base pill */
    draw_rounded_rect(cr, 1.0, 1.0, w - 2.0, h - 2.0, (h - 2.0) / 2.0);
    cairo_set_source_rgba(cr, 24.0 / 255.0, 24.0 / 255.0, 37.0 / 255.0, 0.92);
    cairo_fill_preserve(cr);
    cairo_set_source_rgba(cr, ar, ag, ab, 0.55);
    cairo_set_line_width(cr, 1.25);
    cairo_stroke(cr);

    /* Glowing status dot on left */
    double dot_alpha = pulse_bright ? 1.0 : 0.45;
    cairo_arc(cr, 15.0, cy, 4.0, 0.0, 2.0 * G_PI);
    cairo_set_source_rgba(cr, ar, ag, ab, dot_alpha);
    cairo_fill(cr);

    double cx = 26.0;

    if (hud.is_stop) {
        draw_text_at(f_meta, hud.stop_msg[0] ? hud.stop_msg : "Released", cx, cy,
                     205.0 / 255.0, 214.0 / 255.0, 244.0 / 255.0, 0.95);
    } else if (strcmp(hud.listen, "none") != 0) {
        bool is_sp = (strcmp(hud.listen, "spam") == 0);
        const char *tag = is_sp ? "SPAM" : "HOLD";
        double tr = is_sp ? (250.0 / 255.0) : (116.0 / 255.0);
        double tg = is_sp ? (179.0 / 255.0) : (199.0 / 255.0);
        double tb = is_sp ? (135.0 / 255.0) : (236.0 / 255.0);

        draw_text_at(f_tag, tag, cx, cy, tr, tg, tb, 1.0);
        cx += measure_text(f_tag, tag) + 10.0;

        char info[64];
        if (is_sp) {
            snprintf(info, sizeof(info), "Press key • %.0f/s (scroll ±)", hud.cps);
        } else {
            snprintf(info, sizeof(info), "Press key • Esc");
        }
        draw_text_at(f_meta, info, cx, cy, 186.0 / 255.0, 194.0 / 255.0, 222.0 / 255.0, 0.95);
    } else {
        bool has_hold = (hud.holds[0] != '\0');
        bool has_spam = (hud.spam[0] != '\0');

        if (has_hold) {
            bool hpaused = (!has_spam && hud.paused);
            const char *htag = hpaused ? "PAUSE" : "HOLD";
            double hr = hpaused ? (250.0 / 255.0) : (116.0 / 255.0);
            double hg = hpaused ? (179.0 / 255.0) : (199.0 / 255.0);
            double hb = hpaused ? (135.0 / 255.0) : (236.0 / 255.0);
            draw_text_at(f_tag, htag, cx, cy, hr, hg, hb, 1.0);
            cx += measure_text(f_tag, htag) + 7.0;
            char copy[128];
            snprintf(copy, sizeof(copy), "%s", hud.holds);
            char *sp = NULL;
            for (char *tok = strtok_r(copy, ",", &sp); tok; tok = strtok_r(NULL, ",", &sp)) {
                cx += draw_key_chip(tok, cx, cy, hr, hg, hb) + 5.0;
            }
        }

        if (has_hold && has_spam) {
            cairo_set_source_rgba(cr, 88.0 / 255.0, 91.0 / 255.0, 112.0 / 255.0, 0.7);
            cairo_set_line_width(cr, 1.0);
            cairo_move_to(cr, cx + 2.0, 8.0);
            cairo_line_to(cr, cx + 2.0, h - 8.0);
            cairo_stroke(cr);
            cx += 9.0;
        }

        if (has_spam) {
            double sr = hud.paused ? (250.0 / 255.0) : (166.0 / 255.0);
            double sg = hud.paused ? (179.0 / 255.0) : (227.0 / 255.0);
            double sb = hud.paused ? (135.0 / 255.0) : (161.0 / 255.0);
            const char *stag = hud.paused ? "PAUSE" : "SPAM";
            draw_text_at(f_tag, stag, cx, cy, sr, sg, sb, 1.0);
            cx += measure_text(f_tag, stag) + 7.0;
            cx += draw_key_chip(hud.spam, cx, cy, sr, sg, sb) + 6.0;
            char rate_str[24];
            snprintf(rate_str, sizeof(rate_str), "%.0f/s", hud.cps);
            draw_text_at(f_meta, rate_str, cx, cy, 166.0 / 255.0, 173.0 / 255.0, 200.0 / 255.0, 0.95);
        }

        char timer_str[24];
        long el = hud.base_sec + (long)((mono_ns() - hud.recv_mono_ns) / 1000000000LL);
        format_elapsed(el, timer_str, sizeof(timer_str));
        int tw = measure_text(f_meta, timer_str);
        draw_text_at(f_meta, timer_str, w - tw - 14.0, cy, 147.0 / 255.0, 153.0 / 255.0, 178.0 / 255.0, 0.9);
    }

    cairo_pop_group_to_source(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
    cairo_surface_flush(surface);
    XFlush(dpy);
}

static void stop_tick_timer(void) {
    if (tick_timer_id) {
        g_source_remove(tick_timer_id);
        tick_timer_id = 0;
    }
}

static gboolean tick_cb(gpointer data) {
    (void)data;
    if (!is_visible || hud.is_stop) {
        tick_timer_id = 0;
        return G_SOURCE_REMOVE;
    }
    pulse_bright = !pulse_bright;
    render_hud();
    return G_SOURCE_CONTINUE;
}

static void start_tick_timer(void) {
    if (!tick_timer_id) {
        tick_timer_id = g_timeout_add(500, tick_cb, NULL);
    }
}

static gboolean idle_exit_cb(gpointer data) {
    (void)data;
    idle_exit_timer_id = 0;
    if (loop && g_main_loop_is_running(loop)) g_main_loop_quit(loop);
    return G_SOURCE_REMOVE;
}

static void schedule_idle_exit(guint delay_ms) {
    if (idle_exit_timer_id) g_source_remove(idle_exit_timer_id);
    idle_exit_timer_id = g_timeout_add(delay_ms, idle_exit_cb, NULL);
}

static void cancel_idle_exit(void) {
    if (idle_exit_timer_id) {
        g_source_remove(idle_exit_timer_id);
        idle_exit_timer_id = 0;
    }
}

static gboolean hide_timer_cb(gpointer data) {
    (void)data;
    stop_tick_timer();
    if (is_visible && dpy && win != None) {
        XUnmapWindow(dpy, win);
        XFlush(dpy);
        is_visible = false;
    }
    hide_timer_id = 0;
    schedule_idle_exit(2500);
    return G_SOURCE_REMOVE;
}

static void show_window(void) {
    if (!is_visible) {
        XMapRaised(dpy, win);
        XFlush(dpy);
        is_visible = true;
    } else {
        XRaiseWindow(dpy, win);
        XFlush(dpy);
    }
}

static void apply_line(char *line) {
    g_strstrip(line);
    if (!*line) return;

    if (hide_timer_id) {
        g_source_remove(hide_timer_id);
        hide_timer_id = 0;
    }

    if (strcmp(line, "hide") == 0 || strncmp(line, "hide|", 5) == 0) {
        stop_tick_timer();
        if (is_visible && dpy && win != None) {
            XUnmapWindow(dpy, win);
            XFlush(dpy);
            is_visible = false;
        }
        schedule_idle_exit(2000);
        return;
    }

    cancel_idle_exit();
    hud.recv_mono_ns = mono_ns();
    pulse_bright = true;

    if (strncmp(line, "state|", 6) == 0) {
        hud.is_stop = false;
        snprintf(hud.listen, sizeof(hud.listen), "none");
        hud.holds[0] = '\0';
        hud.spam[0] = '\0';
        hud.paused = false;
        hud.base_sec = 0;

        char *saveptr = NULL;
        for (char *tok = strtok_r(line + 6, "|", &saveptr); tok; tok = strtok_r(NULL, "|", &saveptr)) {
            if (strncmp(tok, "listen=", 7) == 0) snprintf(hud.listen, sizeof(hud.listen), "%s", tok + 7);
            else if (strncmp(tok, "holds=", 6) == 0) snprintf(hud.holds, sizeof(hud.holds), "%s", tok + 6);
            else if (strncmp(tok, "spam=", 5) == 0) snprintf(hud.spam, sizeof(hud.spam), "%s", tok + 5);
            else if (strncmp(tok, "cps=", 4) == 0) hud.cps = atof(tok + 4);
            else if (strncmp(tok, "ms=", 3) == 0) hud.ms = atoi(tok + 3);
            else if (strncmp(tok, "paused=", 7) == 0) hud.paused = (atoi(tok + 7) != 0);
            else if (strncmp(tok, "sec=", 4) == 0) hud.base_sec = atol(tok + 4);
        }
        render_hud();
        show_window();
        start_tick_timer();
        return;
    }

    if (strncmp(line, "stop|", 5) == 0) {
        stop_tick_timer();
        hud.is_stop = true;
        hud.stop_msg[0] = '\0';
        char *saveptr = NULL;
        int idx = 0;
        for (char *tok = strtok_r(line + 5, "|", &saveptr); tok; tok = strtok_r(NULL, "|", &saveptr)) {
            if (idx == 0) snprintf(hud.stop_msg, sizeof(hud.stop_msg), "%s", tok);
            else if (strncmp(tok, "cps=", 4) == 0) hud.cps = atof(tok + 4);
            else if (strncmp(tok, "ms=", 3) == 0) hud.ms = atoi(tok + 3);
            idx++;
        }
        render_hud();
        show_window();
        hide_timer_id = g_timeout_add(700, hide_timer_cb, NULL);
        return;
    }

    /* Legacy fallback: mode|title|sub */
    char *p1 = strchr(line, '|');
    if (p1) {
        *p1 = '\0';
        hud.is_stop = (strcmp(line, "stop") == 0);
        snprintf(hud.stop_msg, sizeof(hud.stop_msg), "%s", p1 + 1);
        render_hud();
        show_window();
        if (hud.is_stop) hide_timer_id = g_timeout_add(700, hide_timer_cb, NULL);
        else start_tick_timer();
    }
}

static gboolean fifo_read_cb(GIOChannel *source, GIOCondition cond, gpointer data) {
    (void)data;
    if (cond & (G_IO_IN | G_IO_PRI)) {
        int fd = g_io_channel_unix_get_fd(source);
        char buf[1024];
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        if (n > 0) {
            buf[n] = '\0';
            char *sp = NULL;
            for (char *line = strtok_r(buf, "\r\n", &sp); line; line = strtok_r(NULL, "\r\n", &sp)) {
                apply_line(line);
            }
        }
    }
    return G_SOURCE_CONTINUE;
}

static gboolean x11_event_cb(GIOChannel *source, GIOCondition cond, gpointer data) {
    (void)source; (void)cond; (void)data;
    if (!dpy) return G_SOURCE_CONTINUE;
    while (XPending(dpy)) {
        XEvent ev;
        XNextEvent(dpy, &ev);
        if (ev.type == Expose && is_visible) render_hud();
    }
    return G_SOURCE_CONTINUE;
}

static gboolean sig_handler_cb(gpointer data) {
    (void)data;
    if (loop && g_main_loop_is_running(loop)) g_main_loop_quit(loop);
    return G_SOURCE_CONTINUE;
}

static void cleanup(void) {
    stop_tick_timer();
    if (hide_timer_id) g_source_remove(hide_timer_id);
    if (idle_exit_timer_id) g_source_remove(idle_exit_timer_id);
    if (sigterm_id) g_source_remove(sigterm_id);
    if (sigint_id) g_source_remove(sigint_id);
    if (fifo_watch_id) g_source_remove(fifo_watch_id);
    if (x_watch_id) g_source_remove(x_watch_id);
    if (fifo_channel) g_io_channel_unref(fifo_channel);
    if (x_channel) g_io_channel_unref(x_channel);
    if (dummy_fd >= 0) close(dummy_fd);
    if (fifo_fd >= 0) close(fifo_fd);
    free_fonts();
    if (cr) cairo_destroy(cr);
    if (surface) cairo_surface_destroy(surface);
    if (dpy) {
        if (win != None) XDestroyWindow(dpy, win);
        if (colormap != None && colormap != DefaultColormap(dpy, screen)) XFreeColormap(dpy, colormap);
        XCloseDisplay(dpy);
    }
    if (fifo_path[0]) unlink(fifo_path);
    if (strcmp(fifo_path, LEGACY_FIFO_PATH) != 0) unlink(LEGACY_FIFO_PATH);
}

static void init_window(void) {
    dpy = XOpenDisplay(NULL);
    if (!dpy) {
        fprintf(stderr, "keyholder-hud: Cannot open X display\n");
        cleanup();
        exit(1);
    }

    screen = DefaultScreen(dpy);
    root = RootWindow(dpy, screen);

    XVisualInfo vinfo;
    if (!XMatchVisualInfo(dpy, screen, 32, TrueColor, &vinfo)) {
        visual = DefaultVisual(dpy, screen);
        depth = DefaultDepth(dpy, screen);
        colormap = DefaultColormap(dpy, screen);
    } else {
        visual = vinfo.visual;
        depth = vinfo.depth;
        colormap = XCreateColormap(dpy, root, visual, AllocNone);
    }

    int screen_w = DisplayWidth(dpy, screen);
    int x = (screen_w - cur_w) / 2;

    XSetWindowAttributes attrs = {
        .override_redirect = True,
        .colormap = colormap,
        .border_pixel = 0,
        .background_pixmap = None,
        .event_mask = ExposureMask,
    };

    win = XCreateWindow(
        dpy, root, x, HUD_TOP_Y, (unsigned)cur_w, (unsigned)cur_h, 0,
        depth, InputOutput, visual,
        CWOverrideRedirect | CWColormap | CWBorderPixel | CWBackPixmap | CWEventMask,
        &attrs
    );

    /* Make HUD 100% click-through via empty XShape input region */
    int shape_ev = 0, shape_err = 0;
    if (XShapeQueryExtension(dpy, &shape_ev, &shape_err)) {
        XShapeCombineRectangles(dpy, win, ShapeInput, 0, 0, NULL, 0, ShapeSet, Unsorted);
    }

    Atom net_wm_type = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
    Atom net_wm_type_dock = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_DOCK", False);
    XChangeProperty(dpy, win, net_wm_type, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)&net_wm_type_dock, 1);

    Atom net_wm_state = XInternAtom(dpy, "_NET_WM_STATE", False);
    Atom state_atoms[2] = {
        XInternAtom(dpy, "_NET_WM_STATE_ABOVE", False),
        XInternAtom(dpy, "_NET_WM_STATE_STAYS_ON_TOP", False),
    };
    XChangeProperty(dpy, win, net_wm_state, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)state_atoms, 2);

    XClassHint class_hint = { "keyholder-hud", "keyholder-hud" };
    XSetClassHint(dpy, win, &class_hint);

    surface = cairo_xlib_surface_create(dpy, win, visual, cur_w, cur_h);
    cr = cairo_create(surface);
}

static void spawn_daemon(void) {
    char exe[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (len > 0) exe[len] = '\0';

    pid_t pid = fork();
    if (pid == 0) {
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            close(devnull);
        }
        setsid();
        if (len > 0) execl(exe, "keyholder-hud", (char *)NULL);
        execlp("keyholder-hud", "keyholder-hud", (char *)NULL);
        _exit(127);
    }
}

static int send_cli_message(const char *msg) {
    char path[512];
    get_fifo_path(path, sizeof(path));

    int fd = open(path, O_WRONLY | O_NONBLOCK);
    if (fd < 0 && strcmp(path, LEGACY_FIFO_PATH) != 0) {
        fd = open(LEGACY_FIFO_PATH, O_WRONLY | O_NONBLOCK);
    }

    if (fd < 0) {
        spawn_daemon();
        struct timespec ts = { .tv_sec = 0, .tv_nsec = 10000000L };
        for (int i = 0; i < 20; i++) {
            nanosleep(&ts, NULL);
            fd = open(path, O_WRONLY | O_NONBLOCK);
            if (fd >= 0) break;
        }
    }
    if (fd < 0) return 1;

    size_t total = strlen(msg), sent = 0;
    while (sent < total) {
        ssize_t n = write(fd, msg + sent, total - sent);
        if (n > 0) sent += (size_t)n;
        else if (n < 0 && errno == EINTR) continue;
        else break;
    }
    close(fd);
    return 0;
}

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);

    if (argc >= 2) {
        if (strcmp(argv[1], "--hide") == 0) {
            return send_cli_message("hide\n");
        } else if (strcmp(argv[1], "--raw") == 0 && argc >= 3) {
            char msg[512];
            snprintf(msg, sizeof(msg), "%s\n", argv[2]);
            return send_cli_message(msg);
        } else if (strcmp(argv[1], "--update") == 0) {
            char msg[512];
            snprintf(msg, sizeof(msg), "%s|%s|%s\n",
                     argc >= 3 ? argv[2] : "", argc >= 4 ? argv[3] : "", argc >= 5 ? argv[4] : "");
            return send_cli_message(msg);
        } else if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
            printf("Usage: %s [--raw <msg> | --hide]\n", argv[0]);
            return 0;
        }
    }

    get_fifo_path(fifo_path, sizeof(fifo_path));
    int test_fd = open(fifo_path, O_WRONLY | O_NONBLOCK);
    if (test_fd >= 0) {
        close(test_fd);
        return 0;
    }

    unlink(fifo_path);
    mkfifo(fifo_path, 0600);
    if (strcmp(fifo_path, LEGACY_FIFO_PATH) != 0) {
        unlink(LEGACY_FIFO_PATH);
        if (symlink(fifo_path, LEGACY_FIFO_PATH) == -1) {
            /* non-fatal */
        }
    }

    init_fonts();
    init_window();

    fifo_fd = open(fifo_path, O_RDONLY | O_NONBLOCK);
    if (fifo_fd < 0) {
        cleanup();
        return 1;
    }
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
