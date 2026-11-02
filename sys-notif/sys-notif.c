/*
 * sys-notif: Ultra-lightweight, modern notification and OSD daemon for Arch Linux / BSPWM.
 *
 * Features:
 *   - Extremely low memory: ~6-10 MB RSS.
 *   - Backward shrinking white progress countdown bar on notification cards.
 *   - Fast non-blocking D-Bus client for CLI --osd calls (<2ms).
 *   - Smooth spam-safe OSD HUD with audio debouncing (no overlapping distortion).
 *   - Full support for volume > 100% (up to 150% amplification) with boost styling.
 *   - App icon support with web service auto-detection (Instagram, WhatsApp, YouTube, etc.).
 *   - Modern floating notification cards with Catppuccin Mocha aesthetic and notification chime.
 *   - 32-bit ARGB TrueColor with Cairo antialiased rounded corners and Pango typography.
 *   - Full Freedesktop org.freedesktop.Notifications D-Bus compliance.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <math.h>
#include <signal.h>
#include <malloc.h>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <cairo/cairo.h>
#include <cairo/cairo-xlib.h>
#include <pango/pangocairo.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <gio/gio.h>

/* Introspection data for org.freedesktop.Notifications */
static const gchar introspection_xml[] =
  "<node>"
  "  <interface name='org.freedesktop.Notifications'>"
  "    <method name='GetCapabilities'>"
  "      <arg type='as' name='capabilities' direction='out'/>"
  "    </method>"
  "    <method name='Notify'>"
  "      <arg type='s' name='app_name' direction='in'/>"
  "      <arg type='u' name='replaces_id' direction='in'/>"
  "      <arg type='s' name='app_icon' direction='in'/>"
  "      <arg type='s' name='summary' direction='in'/>"
  "      <arg type='s' name='body' direction='in'/>"
  "      <arg type='as' name='actions' direction='in'/>"
  "      <arg type='a{sv}' name='hints' direction='in'/>"
  "      <arg type='i' name='expire_timeout' direction='in'/>"
  "      <arg type='u' name='id' direction='out'/>"
  "    </method>"
  "    <method name='CloseNotification'>"
  "      <arg type='u' name='id' direction='in'/>"
  "    </method>"
  "    <method name='GetServerInformation'>"
  "      <arg type='s' name='name' direction='out'/>"
  "      <arg type='s' name='vendor' direction='out'/>"
  "      <arg type='s' name='version' direction='out'/>"
  "      <arg type='s' name='spec_version' direction='out'/>"
  "    </method>"
  "    <signal name='NotificationClosed'>"
  "      <arg type='u' name='id'/>"
  "      <arg type='u' name='reason'/>"
  "    </signal>"
  "    <signal name='ActionInvoked'>"
  "      <arg type='u' name='id'/>"
  "      <arg type='s' name='action_key'/>"
  "    </signal>"
  "  </interface>"
  "</node>";

/* Catppuccin Mocha Color Palette */
#define COLOR_BASE_R    (30.0 / 255.0)
#define COLOR_BASE_G    (30.0 / 255.0)
#define COLOR_BASE_B    (46.0 / 255.0)
#define COLOR_BASE_A    0.95

#define COLOR_MANTLE_R  (24.0 / 255.0)
#define COLOR_MANTLE_G  (24.0 / 255.0)
#define COLOR_MANTLE_B  (37.0 / 255.0)
#define COLOR_MANTLE_A  0.94

#define COLOR_SURFACE_R (49.0 / 255.0)
#define COLOR_SURFACE_G (50.0 / 255.0)
#define COLOR_SURFACE_B (68.0 / 255.0)
#define COLOR_SURFACE_A 0.85

#define COLOR_TEXT_R    (205.0 / 255.0)
#define COLOR_TEXT_G    (214.0 / 255.0)
#define COLOR_TEXT_B    (244.0 / 255.0)

#define COLOR_SUBTEXT_R (166.0 / 255.0)
#define COLOR_SUBTEXT_G (173.0 / 255.0)
#define COLOR_SUBTEXT_B (200.0 / 255.0)

#define COLOR_BLUE_R    (137.0 / 255.0)
#define COLOR_BLUE_G    (180.0 / 255.0)
#define COLOR_BLUE_B    (250.0 / 255.0)

#define COLOR_PEACH_R   (250.0 / 255.0)
#define COLOR_PEACH_G   (179.0 / 255.0)
#define COLOR_PEACH_B   (135.0 / 255.0)

#define COLOR_RED_R     (243.0 / 255.0)
#define COLOR_RED_G     (139.0 / 255.0)
#define COLOR_RED_B     (168.0 / 255.0)

#define COLOR_GREEN_R   (166.0 / 255.0)
#define COLOR_GREEN_G   (227.0 / 255.0)
#define COLOR_GREEN_B   (161.0 / 255.0)

/* X11 & App State */
static Display *dpy = NULL;
static int screen = 0;
static Window root = 0;
static Visual *visual = NULL;
static Colormap colormap = 0;
static int depth = 0;
static GDBusConnection *dbus_conn = NULL;
static guint next_id = 1;
static gint64 last_sound_time = 0;

/* OSD State */
typedef struct {
    Window win;
    cairo_surface_t *surface;
    cairo_t *cr;
    int width;
    int height;
    int x;
    int y;
    gboolean visible;
    gint percent;
    gboolean is_muted;
    char type[32];      /* "volume" or "brightness" */
    char label[64];
    guint timer_id;
} OSDState;

static OSDState osd = {0};

#define MAX_GROUP_MSGS 5

/* Notification Item */
typedef struct NotificationItem {
    guint id;
    char *app_name;
    char *summary;
    char *messages[MAX_GROUP_MSGS];
    int msg_count;       /* Active text message lines in card (0 to 5) */
    int total_msgs;      /* Total text messages received in this thread */
    int reel_count;      /* Number of reels received (tracked separately, piled into pill) */
    char *latest_reel_text;
    char *icon_name;
    GdkPixbuf *pixbuf;
    cairo_surface_t *icon_surf;
    gboolean is_avatar;
    guint8 urgency;      /* 0: low, 1: normal, 2: critical */
    gboolean is_transient;
    char *thread_id;
    char *default_action_key;
    Window win;
    cairo_surface_t *surface;
    cairo_t *cr;
    int width;
    int height;
    int x;
    int y;
    guint timer_id;
    gint64 start_time_us;
    gint64 duration_us;
    double progress;
    gboolean is_hovered; /* True when mouse cursor is hovering over the card */
    guint anim_timer_id;
    struct NotificationItem *next;
} NotificationItem;

static NotificationItem *notif_list = NULL;

/* Cached font descriptions to prevent continuous reallocations */
static PangoFontDescription *f_app = NULL;
static PangoFontDescription *f_sum = NULL;
static PangoFontDescription *f_body = NULL;
static PangoFontDescription *f_badge = NULL;
static PangoFontDescription *f_group = NULL;
static PangoFontDescription *f_osd_icon = NULL;
static PangoFontDescription *f_osd_pct = NULL;

static void init_fonts(void) {
    if (!f_app) f_app = pango_font_description_from_string("JetBrains Mono Bold 9");
    if (!f_sum) f_sum = pango_font_description_from_string("JetBrains Mono Bold 11");
    if (!f_body) f_body = pango_font_description_from_string("JetBrains Mono 9.5");
    if (!f_badge) f_badge = pango_font_description_from_string("JetBrainsMono Nerd Font 13");
    if (!f_group) f_group = pango_font_description_from_string("JetBrains Mono Bold 8");
    if (!f_osd_icon) f_osd_icon = pango_font_description_from_string("JetBrainsMono Nerd Font 13");
    if (!f_osd_pct) f_osd_pct = pango_font_description_from_string("JetBrains Mono Bold 10");
}

/* Helper: draw rounded rectangle */
static void draw_rounded_rect(cairo_t *cr, double x, double y, double w, double h, double r) {
    if (w <= 0 || h <= 0) return;
    if (r > h / 2.0) r = h / 2.0;
    if (r > w / 2.0) r = w / 2.0;
    cairo_new_sub_path(cr);
    cairo_arc(cr, x + w - r, y + r, r, -M_PI_2, 0);
    cairo_arc(cr, x + w - r, y + h - r, r, 0, M_PI_2);
    cairo_arc(cr, x + r, y + h - r, r, M_PI_2, M_PI);
    cairo_arc(cr, x + r, y + r, r, M_PI, 3 * M_PI_2);
    cairo_close_path(cr);
}

/* Find 32-bit ARGB TrueColor Visual for transparent rounded corners */
static void init_visual() {
    XVisualInfo vinfo;
    if (XMatchVisualInfo(dpy, screen, 32, TrueColor, &vinfo)) {
        visual = vinfo.visual;
        depth = 32;
        colormap = XCreateColormap(dpy, root, visual, AllocNone);
    } else {
        visual = DefaultVisual(dpy, screen);
        depth = DefaultDepth(dpy, screen);
        colormap = DefaultColormap(dpy, screen);
    }
}

/* Debounced sound triggers with spam volume lowering */
static void play_sound(const char *sound_id) {
    gint64 now = g_get_monotonic_time();
    gint64 delta_us = now - last_sound_time;
    /* Debounce: only play if at least 120ms has passed since last tick */
    if (delta_us < 120000) {
        return;
    }
    last_sound_time = now;

    /* Lower volume if messages are spamming in rapid succession */
    const char *vol_db = NULL;
    if (delta_us < 800000) {
        vol_db = "-18.0";
    } else if (delta_us < 2000000) {
        vol_db = "-10.0";
    }

    pid_t pid = fork();
    if (pid == 0) {
        close(STDIN_FILENO);
        close(STDOUT_FILENO);
        close(STDERR_FILENO);
        if (vol_db) {
            execlp("canberra-gtk-play", "canberra-gtk-play", "-i", sound_id, "-V", vol_db, (char *)NULL);
        } else {
            execlp("canberra-gtk-play", "canberra-gtk-play", "-i", sound_id, (char *)NULL);
        }
        _exit(0);
    }
}

/* Convert GdkPixbuf to Cairo ARGB surface (pure Cairo/Pixbuf, zero GDK display dependencies) */
static cairo_surface_t *pixbuf_to_surface(GdkPixbuf *pb) {
    if (!pb) return NULL;
    int w = gdk_pixbuf_get_width(pb);
    int h = gdk_pixbuf_get_height(pb);
    int n_channels = gdk_pixbuf_get_n_channels(pb);
    int rowstride = gdk_pixbuf_get_rowstride(pb);
    const guchar *pixels = gdk_pixbuf_get_pixels(pb);

    cairo_surface_t *surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_surface_flush(surf);
    unsigned char *surf_data = cairo_image_surface_get_data(surf);
    int surf_stride = cairo_image_surface_get_stride(surf);

    for (int y = 0; y < h; y++) {
        const guchar *p = pixels + y * rowstride;
        guint32 *out = (guint32 *)(surf_data + y * surf_stride);
        for (int x = 0; x < w; x++) {
            guchar r = p[0], g = p[1], b = p[2];
            guchar a = (n_channels >= 4) ? p[3] : 255;
            p += n_channels;
            /* Cairo ARGB32 requires pre-multiplied alpha */
            guint32 pr = (r * a) / 255;
            guint32 pg = (g * a) / 255;
            guint32 pb_val = (b * a) / 255;
            out[x] = (a << 24) | (pr << 16) | (pg << 8) | pb_val;
        }
    }
    cairo_surface_mark_dirty(surf);
    return surf;
}

/* -------------------------------------------------------------
 * App Icon Loader (Freedesktop lookup + Pixbuf)
 * ------------------------------------------------------------- */
static GdkPixbuf *load_app_icon(const char *name, const char *app_name, int target_size) {
    const char *candidates[4] = { name, app_name, NULL, NULL };
    char lower_app[64] = {0};
    if (app_name) {
        for (int i = 0; app_name[i] && i < 63; i++) {
            lower_app[i] = (char)g_ascii_tolower(app_name[i]);
        }
        candidates[2] = lower_app;
    }

    static const char *dirs[] = {
        "/usr/share/icons/TokyoNight-SE/48x48/apps",
        "/usr/share/icons/Catppuccin-Mocha/apps/64",
        "/usr/share/icons/Sweet-Rainbow/apps/48",
        "/usr/share/icons/Sweet-Rainbow/apps/scalable",
        "/usr/share/icons/Papirus/48x48/apps",
        "/usr/share/icons/Papirus/48x48/status",
        "/usr/share/icons/Papirus/48x48/devices",
        "/usr/share/icons/Papirus/48x48/categories",
        "/usr/share/icons/Papirus/32x32/apps",
        "/usr/share/icons/Papirus/32x32/status",
        "/usr/share/icons/Dracula/scalable/apps",
        "/usr/share/icons/Candy/apps/scalable",
        "/usr/share/icons/hicolor/48x48/apps",
        "/usr/share/icons/hicolor/scalable/apps",
        "/usr/share/icons/hicolor/64x64/apps",
        "/usr/share/icons/hicolor/128x128/apps",
        "/usr/share/pixmaps",
        "/home/vibecoder/.local/share/icons",
        NULL
    };
    static const char *exts[] = { ".png", ".svg", "", NULL };

    for (int c = 0; candidates[c]; c++) {
        const char *cand = candidates[c];
        if (!cand || strlen(cand) == 0) continue;

        /* Absolute path or file URI */
        if (cand[0] == '/' && access(cand, R_OK) == 0) {
            GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(cand, target_size, target_size, TRUE, NULL);
            if (pb) return pb;
        }
        if (strncmp(cand, "file://", 7) == 0 && access(cand + 7, R_OK) == 0) {
            GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(cand + 7, target_size, target_size, TRUE, NULL);
            if (pb) return pb;
        }

        /* Search in system theme directories */
        char path[512];
        for (int d = 0; dirs[d]; d++) {
            for (int e = 0; exts[e]; e++) {
                snprintf(path, sizeof(path), "%s/%s%s", dirs[d], cand, exts[e]);
                if (access(path, R_OK) == 0) {
                    GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(path, target_size, target_size, TRUE, NULL);
                    if (pb) return pb;
                }
            }
        }
    }
    return NULL;
}

/* -------------------------------------------------------------
 * Profile Picture / Avatar Extractor (D-Bus Hints & File Paths)
 * ------------------------------------------------------------- */
static void free_pixbuf_data(guchar *pixels, gpointer data) {
    (void)data;
    g_free(pixels);
}

/* Helper to unwrap any GVariant containing nested variants */
static GVariant *unwrap_variant(GVariant *v) {
    if (!v) return NULL;
    while (g_variant_is_of_type(v, G_VARIANT_TYPE_VARIANT)) {
        GVariant *tmp = g_variant_get_variant(v);
        g_variant_unref(v);
        v = tmp;
    }
    return v;
}

/* Detect and drop generic Instagram noise: "You have unread messages", "You have unseen notifications", etc. */
static gboolean is_instagram_unread_notice(const char *app, const char *sum, const char *bod) {
    gboolean is_insta = FALSE;
    if (app && strcasestr(app, "instagram")) is_insta = TRUE;
    if (sum && strcasestr(sum, "instagram")) is_insta = TRUE;
    if (bod && strcasestr(bod, "instagram")) is_insta = TRUE;
    if (!is_insta) return FALSE;

    #define HAS(txt, str) (txt && strcasestr(txt, str))
    if (HAS(sum, "unread message") || HAS(bod, "unread message") ||
        HAS(sum, "unread messages") || HAS(bod, "unread messages") ||
        HAS(sum, "unseen notification") || HAS(bod, "unseen notification") ||
        HAS(sum, "unseen notifications") || HAS(bod, "unseen notifications") ||
        HAS(sum, "you have unread") || HAS(bod, "you have unread") ||
        HAS(sum, "you have unseen") || HAS(bod, "you have unseen") ||
        HAS(sum, "new message") || HAS(bod, "new message") ||
        HAS(sum, "new messages") || HAS(bod, "new messages")) {
        return TRUE;
    }
    #undef HAS
    return FALSE;
}

/* Helper to extract base group name and individual sender name across messaging apps */
static void parse_chat_conversation(const char *app_name, const char *summary, const char *body,
                                     char **out_group, char **out_sender) {
    (void)app_name;
    const char *sum = summary ? summary : "";
    const char *bod = body ? body : "";

    /* 1. Pattern: "Group • Sender" (e.g. "10th gc • yaarouse") */
    const char *bullet = strstr(sum, " • ");
    if (bullet) {
        int grp_len = (int)(bullet - sum);
        char *grp = g_strndup(sum, grp_len);
        g_strstrip(grp);
        char *snd = strdup(bullet + strlen(" • "));
        g_strstrip(snd);
        *out_group = grp;
        *out_sender = snd;
        return;
    }

    /* 2. Pattern: "Sender to Group" (e.g. "yaarouse to 10th gc" or "yaarouse_capitan to 10th gc") */
    const char *to_kw = strcasestr(sum, " to ");
    if (to_kw && (to_kw - sum) >= 2) {
        char *snd = g_strndup(sum, (int)(to_kw - sum));
        g_strstrip(snd);
        char *grp = strdup(to_kw + 4);
        g_strstrip(grp);
        *out_group = grp;
        *out_sender = snd;
        return;
    }

    /* 3. Pattern: Body contains "Sent a ... to Group" */
    const char *to_in_body = strcasestr(bod, " to ");
    if (to_in_body && (to_in_body - bod) >= 3) {
        const char *grp_start = to_in_body + 4;
        while (*grp_start == ' ') grp_start++;
        if (strlen(grp_start) > 0 &&
            strcasecmp(grp_start, "your group") != 0 &&
            strcasecmp(grp_start, "the group") != 0) {
            *out_group = strdup(grp_start);
            *out_sender = strdup(sum);
            return;
        }
    }

    /* 4. Single chat / direct message fallback */
    *out_group = strdup(sum);
    *out_sender = strdup(sum);
}

/* Cache avatar pixbuf to disk for group chat continuity and Notification Center display */
static char *cache_avatar_pixbuf(GdkPixbuf *pb, const char *app_name, const char *summary) {
    if (!pb) return NULL;
    const char *cache_dir = "/home/vibecoder/.cache/sys-notif/avatars";
    g_mkdir_with_parents(cache_dir, 0755);

    char *grp = NULL, *snd = NULL;
    parse_chat_conversation(app_name, summary, NULL, &grp, &snd);

    const char *app = app_name ? app_name : "app";
    const char *target_snd = (snd && strlen(snd) > 0) ? snd : grp;

    /* Sender avatar key */
    char sender_key[128] = {0};
    int pos = 0;
    for (int i = 0; app[i] && pos < 15; i++) {
        if (g_ascii_isalnum(app[i])) sender_key[pos++] = (char)g_ascii_tolower(app[i]);
    }
    sender_key[pos++] = '_';
    for (int i = 0; target_snd[i] && pos < 60; i++) {
        if (g_ascii_isalnum(target_snd[i])) sender_key[pos++] = (char)g_ascii_tolower(target_snd[i]);
        else sender_key[pos++] = '_';
    }
    sender_key[pos] = '\0';

    static char avatar_path[512];
    snprintf(avatar_path, sizeof(avatar_path), "%s/%s.png", cache_dir, sender_key);
    gdk_pixbuf_save(pb, avatar_path, "png", NULL, NULL);

    free(grp);
    free(snd);
    return avatar_path;
}

/* Load previously cached avatar (for group chats, only loads group icon; for DMs, loads contact icon) */
static GdkPixbuf *load_cached_group_avatar(const char *app_name, const char *summary, char **out_path) {
    const char *cache_dir = "/home/vibecoder/.cache/sys-notif/avatars";
    char *grp = NULL, *snd = NULL;
    parse_chat_conversation(app_name, summary, NULL, &grp, &snd);

    const char *app = app_name ? app_name : "app";
    static char avatar_path[512];

    gboolean is_group = (grp && snd && strlen(grp) > 0 && strlen(snd) > 0 && g_ascii_strcasecmp(grp, snd) != 0);

    if (is_group) {
        /* Group chat: check ONLY group-specific avatar, never sender's avatar */
        char grp_key[128] = {0};
        int gpos = 0;
        for (int i = 0; app[i] && gpos < 15; i++) {
            if (g_ascii_isalnum(app[i])) grp_key[gpos++] = (char)g_ascii_tolower(app[i]);
        }
        grp_key[gpos++] = '_';
        for (int i = 0; grp[i] && gpos < 60; i++) {
            if (g_ascii_isalnum(grp[i])) grp_key[gpos++] = (char)g_ascii_tolower(grp[i]);
            else grp_key[gpos++] = '_';
        }
        grp_key[gpos] = '\0';
        snprintf(avatar_path, sizeof(avatar_path), "%s/%s.png", cache_dir, grp_key);
        if (access(avatar_path, R_OK) == 0) {
            if (out_path) *out_path = avatar_path;
            free(grp); free(snd);
            return gdk_pixbuf_new_from_file_at_scale(avatar_path, 42, 42, TRUE, NULL);
        }
        free(grp); free(snd);
        return NULL;
    }

    /* 1-on-1 contact / DM avatar */
    if (snd && strlen(snd) > 0) {
        char snd_key[128] = {0};
        int pos = 0;
        for (int i = 0; app[i] && pos < 15; i++) {
            if (g_ascii_isalnum(app[i])) snd_key[pos++] = (char)g_ascii_tolower(app[i]);
        }
        snd_key[pos++] = '_';
        for (int i = 0; snd[i] && pos < 60; i++) {
            if (g_ascii_isalnum(snd[i])) snd_key[pos++] = (char)g_ascii_tolower(snd[i]);
            else snd_key[pos++] = '_';
        }
        snd_key[pos] = '\0';
        snprintf(avatar_path, sizeof(avatar_path), "%s/%s.png", cache_dir, snd_key);
        if (access(avatar_path, R_OK) == 0) {
            if (out_path) *out_path = avatar_path;
            free(grp); free(snd);
            return gdk_pixbuf_new_from_file_at_scale(avatar_path, 42, 42, TRUE, NULL);
        }
    }

    free(grp);
    free(snd);
    return NULL;
}

static GdkPixbuf *extract_pfp_from_hints(GVariant *hints, const char *app_icon, gboolean *is_avatar_out) {
    if (is_avatar_out) *is_avatar_out = FALSE;

    /* 1. Raw byte image data hints from D-Bus */
    if (hints) {
        static const char *data_keys[] = {
            "image-data", "image_data", "icon_data", "image", "icon",
            "avatar", "group-icon", "group-avatar", "sender-icon", NULL
        };
        for (int k = 0; data_keys[k]; k++) {
            GVariant *v = g_variant_lookup_value(hints, data_keys[k], NULL);
            if (!v) continue;
            v = unwrap_variant(v);

            if (g_variant_is_of_type(v, G_VARIANT_TYPE("(iiibiiay)"))) {
                gint width = 0, height = 0, rowstride = 0, bits_per_sample = 0, n_channels = 0;
                gboolean has_alpha = FALSE;
                GVariant *data_v = NULL;

                g_variant_get(v, "(iiibii@ay)",
                              &width, &height, &rowstride,
                              &has_alpha, &bits_per_sample, &n_channels,
                              &data_v);

                if (data_v && width > 0 && height > 0) {
                    gsize data_len = 0;
                    const guchar *bytes = (const guchar *)g_variant_get_fixed_array(data_v, &data_len, sizeof(guchar));
                    if (bytes && data_len > 0) {
                        guchar *pixels_copy = g_memdup2(bytes, data_len);
                        GdkPixbuf *raw_pb = gdk_pixbuf_new_from_data(
                            pixels_copy,
                            GDK_COLORSPACE_RGB,
                            has_alpha,
                            bits_per_sample,
                            width,
                            height,
                            rowstride,
                            free_pixbuf_data,
                            NULL
                        );
                        if (raw_pb) {
                            GdkPixbuf *scaled = gdk_pixbuf_scale_simple(raw_pb, 42, 42, GDK_INTERP_BILINEAR);
                            g_object_unref(raw_pb);
                            g_variant_unref(data_v);
                            g_variant_unref(v);
                            if (is_avatar_out) *is_avatar_out = TRUE;
                            return scaled;
                        }
                    }
                    g_variant_unref(data_v);
                }
            }
            g_variant_unref(v);
        }

        /* 2. Image path hints */
        static const char *path_keys[] = {
            "image-path", "image_path", "image-url", "image_url",
            "avatar-path", "avatar_path", "icon-path", "icon_path", NULL
        };
        for (int k = 0; path_keys[k]; k++) {
            GVariant *v = g_variant_lookup_value(hints, path_keys[k], NULL);
            if (!v) continue;
            v = unwrap_variant(v);

            if (g_variant_is_of_type(v, G_VARIANT_TYPE_STRING)) {
                const gchar *img_path = g_variant_get_string(v, NULL);
                if (img_path && strlen(img_path) > 0) {
                    const char *real_path = img_path;
                    if (strncmp(real_path, "file://", 7) == 0) real_path += 7;
                    if (access(real_path, R_OK) == 0) {
                        GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(real_path, 42, 42, TRUE, NULL);
                        g_variant_unref(v);
                        if (pb) {
                            if (is_avatar_out) *is_avatar_out = TRUE;
                            return pb;
                        }
                    }
                }
            }
            g_variant_unref(v);
        }
    }

    /* 3. Check if app_icon is an image file on disk (avatar from file) */
    if (app_icon && strlen(app_icon) > 0) {
        const char *real_path = app_icon;
        if (strncmp(real_path, "file://", 7) == 0) real_path += 7;
        if (real_path[0] == '/' && access(real_path, R_OK) == 0) {
            const char *dot = strrchr(real_path, '.');
            if (dot && (strcasecmp(dot, ".png") == 0 || strcasecmp(dot, ".jpg") == 0 ||
                        strcasecmp(dot, ".jpeg") == 0 || strcasecmp(dot, ".webp") == 0)) {
                GdkPixbuf *pb = gdk_pixbuf_new_from_file_at_scale(real_path, 42, 42, TRUE, NULL);
                if (pb) {
                    if (is_avatar_out) *is_avatar_out = TRUE;
                    return pb;
                }
            }
        }
    }

    return NULL;
}

/* -------------------------------------------------------------
 * OSD HUD Functions (Sound / Brightness)
 * ------------------------------------------------------------- */
static gboolean osd_hide_callback(gpointer data) {
    (void)data;
    if (osd.visible && osd.win) {
        XUnmapWindow(dpy, osd.win);
        XFlush(dpy);
        osd.visible = FALSE;
    }
    osd.timer_id = 0;
    malloc_trim(0);
    return G_SOURCE_REMOVE;
}

static void render_osd() {
    if (!osd.win || !osd.cr) return;

    cairo_t *cr = osd.cr;
    int w = osd.width;
    int h = osd.height;

    /* Double-buffering: draw to offscreen group to eliminate flickering */
    cairo_push_group(cr);

    /* Clear surface (transparent background) */
    cairo_set_operator(cr, CAIRO_OPERATOR_CLEAR);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    /* Draw pill body */
    draw_rounded_rect(cr, 1.0, 1.0, w - 2.0, h - 2.0, h / 2.0);
    cairo_set_source_rgba(cr, COLOR_MANTLE_R, COLOR_MANTLE_G, COLOR_MANTLE_B, COLOR_MANTLE_A);
    cairo_fill_preserve(cr);

    /* Border (accent or boost color) */
    if (osd.percent > 100) {
        cairo_set_source_rgba(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B, 0.70);
    } else {
        cairo_set_source_rgba(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B, 0.50);
    }
    cairo_set_line_width(cr, 1.5);
    cairo_stroke(cr);

    /* Icon / Glyph: Dynamic adaptive icons for brightness and volume */
    const char *icon_glyph = "󰕾";
    if (strcmp(osd.type, "brightness") == 0) {
        if (osd.percent <= 33) {
            icon_glyph = "󰃞"; /* Low brightness */
        } else if (osd.percent <= 66) {
            icon_glyph = "󰃟"; /* Medium brightness */
        } else {
            icon_glyph = "󰃠"; /* High brightness */
        }
    } else {
        if (osd.is_muted || osd.percent == 0) {
            icon_glyph = "󰝟"; /* Muted */
        } else if (osd.percent <= 30) {
            icon_glyph = "󰕿"; /* Low volume */
        } else if (osd.percent <= 70) {
            icon_glyph = "󰖀"; /* Medium volume */
        } else {
            icon_glyph = "󰕾"; /* High volume */
        }
    }

    PangoLayout *layout_icon = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(layout_icon, f_osd_icon);
    pango_layout_set_text(layout_icon, icon_glyph, -1);

    if (osd.is_muted) {
        cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
    } else if (osd.percent > 100) {
        cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
    } else {
        cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
    }
    cairo_move_to(cr, 16, 12);
    pango_cairo_show_layout(cr, layout_icon);
    g_object_unref(layout_icon);

    /* Format percentage text */
    char pct_str[24];
    if (osd.is_muted) {
        snprintf(pct_str, sizeof(pct_str), "MUTE");
    } else {
        snprintf(pct_str, sizeof(pct_str), "%d%%", osd.percent);
    }

    PangoLayout *layout_pct = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(layout_pct, f_osd_pct);
    pango_layout_set_text(layout_pct, pct_str, -1);

    int pct_w = 0, pct_h = 0;
    pango_layout_get_pixel_size(layout_pct, &pct_w, &pct_h);

    /* Right-align percentage text so 150% never clips */
    int text_x = w - pct_w - 18;
    int text_y = (h - pct_h) / 2;

    if (osd.is_muted) {
        cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
    } else if (osd.percent > 100) {
        cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
    } else {
        cairo_set_source_rgb(cr, COLOR_TEXT_R, COLOR_TEXT_G, COLOR_TEXT_B);
    }
    cairo_move_to(cr, text_x, text_y);
    pango_cairo_show_layout(cr, layout_pct);
    g_object_unref(layout_pct);

    /* Progress bar track */
    double track_x = 44.0;
    double track_y = (h - 8.0) / 2.0;
    double track_w = text_x - 12.0 - track_x;
    double track_h = 8.0;

    if (track_w < 30.0) track_w = 30.0;

    /* Draw track background */
    draw_rounded_rect(cr, track_x, track_y, track_w, track_h, 4.0);
    cairo_set_source_rgba(cr, COLOR_SURFACE_R, COLOR_SURFACE_G, COLOR_SURFACE_B, 0.9);
    cairo_fill(cr);

    /* Handle volume max: up to 150% boost */
    double max_scale = (strcmp(osd.type, "volume") == 0) ? 150.0 : 100.0;
    double pct_100_ratio = 100.0 / max_scale; /* ~0.667 for 150% max */
    double x_100 = track_x + (track_w * pct_100_ratio);

    /* Subtle tick at 100% boundary if scale is 150% */
    if (max_scale > 100.0) {
        cairo_set_source_rgba(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B, 0.4);
        cairo_set_line_width(cr, 1.0);
        cairo_move_to(cr, x_100, track_y - 2.0);
        cairo_line_to(cr, x_100, track_y + track_h + 2.0);
        cairo_stroke(cr);
    }

    if (!osd.is_muted && osd.percent > 0) {
        double current_val = (double)osd.percent;
        if (current_val > max_scale) current_val = max_scale;

        if (current_val <= 100.0) {
            /* Base blue fill */
            double fill_ratio = current_val / max_scale;
            double fill_w = track_w * fill_ratio;
            if (fill_w < 6.0) fill_w = 6.0;

            draw_rounded_rect(cr, track_x, track_y, fill_w, track_h, 4.0);
            cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
            cairo_fill(cr);
        } else {
            /* 0% to 100% filled with Blue */
            double base_w = track_w * pct_100_ratio;
            draw_rounded_rect(cr, track_x, track_y, base_w, track_h, 4.0);
            cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
            cairo_fill(cr);

            /* >100% portion filled with Peach/Boost color */
            double boost_ratio = (current_val - 100.0) / max_scale;
            double boost_w = track_w * boost_ratio;
            if (boost_w < 4.0) boost_w = 4.0;

            draw_rounded_rect(cr, x_100, track_y, boost_w, track_h, 4.0);
            cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
            cairo_fill(cr);
        }
    }

    /* Pop group and atomically paint to window */
    cairo_pop_group_to_source(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    cairo_surface_flush(osd.surface);
    XFlush(dpy);
}

static void show_osd(const char *type, int percent, gboolean is_muted, const char *label) {
    int screen_w = DisplayWidth(dpy, screen);
    int screen_h = DisplayHeight(dpy, screen);

    osd.width = 300;
    osd.height = 46;
    osd.x = (screen_w - osd.width) / 2;
    osd.y = screen_h - 110;
    osd.percent = percent;
    osd.is_muted = is_muted;
    strncpy(osd.type, type ? type : "volume", sizeof(osd.type) - 1);
    if (label) strncpy(osd.label, label, sizeof(osd.label) - 1);

    if (!osd.win) {
        XSetWindowAttributes attrs;
        attrs.override_redirect = True;
        attrs.colormap = colormap;
        attrs.border_pixel = 0;
        attrs.background_pixmap = None;
        attrs.event_mask = ExposureMask;

        osd.win = XCreateWindow(
            dpy, root, osd.x, osd.y, osd.width, osd.height, 0,
            depth, InputOutput, visual,
            CWOverrideRedirect | CWColormap | CWBorderPixel | CWBackPixmap | CWEventMask,
            &attrs
        );

        Atom net_wm_type = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
        Atom net_wm_type_notif = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_NOTIFICATION", False);
        XChangeProperty(dpy, osd.win, net_wm_type, XA_ATOM, 32, PropModeReplace,
                        (unsigned char *)&net_wm_type_notif, 1);

        XClassHint class_hint = { "sys-osd", "sys-osd" };
        XSetClassHint(dpy, osd.win, &class_hint);

        osd.surface = cairo_xlib_surface_create(dpy, osd.win, visual, osd.width, osd.height);
        osd.cr = cairo_create(osd.surface);
    } else {
        XMoveWindow(dpy, osd.win, osd.x, osd.y);
    }

    render_osd();
    cairo_surface_flush(osd.surface);
    XFlush(dpy);

    if (!osd.visible) {
        XMapRaised(dpy, osd.win);
        XFlush(dpy);
        osd.visible = TRUE;
    }

    /* Reset / start auto-hide timer (1.2s) */
    if (osd.timer_id > 0) {
        g_source_remove(osd.timer_id);
    }
    osd.timer_id = g_timeout_add(1200, osd_hide_callback, NULL);
}

/* -------------------------------------------------------------
 * Notification Window Functions (App / System Alerts)
 * ------------------------------------------------------------- */
static void reposition_notifications() {
    int screen_w = DisplayWidth(dpy, screen);
    int current_y = 45; /* Below Polybar */
    NotificationItem *cur = notif_list;

    while (cur) {
        cur->x = screen_w - cur->width - 16;
        cur->y = current_y;
        XMoveWindow(dpy, cur->win, cur->x, cur->y);
        current_y += cur->height + 10;
        cur = cur->next;
    }
    XFlush(dpy);
}

static void render_notification(NotificationItem *item);
static gboolean notif_timeout_callback(gpointer data);

/* Dismiss all active notification cards */
static void dismiss_all_notifications(void) {
    while (notif_list) {
        notif_timeout_callback(notif_list);
    }
}

/* Notify Polybar notif badge instantly via IPC (0 polling) */
static void update_polybar_notif_badge(void) {
    if (fork() == 0) {
        setsid();
        execlp("polybar-msg", "polybar-msg", "action", "#notif.hook.0", NULL);
        _exit(0);
    }
}

/* Check if Do Not Disturb is enabled */
static gboolean is_dnd_active(void) {
    return (access("/home/vibecoder/.cache/sys-notif/dnd", F_OK) == 0);
}

static void toggle_dnd(void) {
    const char *dnd_file = "/home/vibecoder/.cache/sys-notif/dnd";
    if (is_dnd_active()) {
        unlink(dnd_file);
        if (fork() == 0) {
            setsid();
            execlp("notify-send", "notify-send", "-a", "Do Not Disturb", "-i", "dialog-information",
                   "Disabled", "Notifications will now pop up normally.", NULL);
            _exit(0);
        }
    } else {
        g_mkdir_with_parents("/home/vibecoder/.cache/sys-notif", 0755);
        FILE *f = fopen(dnd_file, "w");
        if (f) {
            fputs("1", f);
            fclose(f);
        }
        dismiss_all_notifications();
        if (fork() == 0) {
            setsid();
            execlp("notify-send", "notify-send", "-a", "Do Not Disturb", "-i", "dialog-information",
                   "Enabled", "Notifications are silenced and saved to history.", NULL);
            _exit(0);
        }
    }
    update_polybar_notif_badge();
}

/* Calculate dynamic card height to fit stacked messages (up to 5) and overflow badge comfortably */
static int calculate_notification_height(const char *summary, char *messages[], int msg_count, int total_msgs, const char *reel_text, int width) {
    init_fonts();

    int content_x = 64;
    int text_available_w = width - content_x - 18;
    if (text_available_w < 100) text_available_w = 100;

    cairo_surface_t *dummy_surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 1, 1);
    cairo_t *dummy_cr = cairo_create(dummy_surf);
    PangoLayout *layout = pango_cairo_create_layout(dummy_cr);

    /* Measure Summary */
    pango_layout_set_font_description(layout, f_sum);
    pango_layout_set_width(layout, text_available_w * PANGO_SCALE);
    pango_layout_set_wrap(layout, PANGO_WRAP_WORD_CHAR);
    pango_layout_set_text(layout, summary ? summary : "", -1);
    int sum_w = 0, sum_h = 0;
    pango_layout_get_pixel_size(layout, &sum_w, &sum_h);

    /* Measure Stacked Messages */
    int total_msg_h = 0;
    pango_layout_set_font_description(layout, f_body);
    pango_layout_set_width(layout, text_available_w * PANGO_SCALE);
    pango_layout_set_wrap(layout, PANGO_WRAP_WORD_CHAR);

    if (msg_count > 0) {
        for (int m = 0; m < msg_count; m++) {
            const char *msg = messages[m] ? messages[m] : "";
            char line_buf[600];
            if (msg_count > 1) {
                snprintf(line_buf, sizeof(line_buf), "• %s", msg);
            } else {
                snprintf(line_buf, sizeof(line_buf), "%s", msg);
            }
            char *valid_utf8 = g_utf8_make_valid(line_buf, -1);
            if (!pango_parse_markup(valid_utf8, -1, 0, NULL, NULL, NULL, NULL)) {
                pango_layout_set_text(layout, valid_utf8, -1);
            } else {
                pango_layout_set_markup(layout, valid_utf8, -1);
            }
            g_free(valid_utf8);
            int mw = 0, mh = 0;
            pango_layout_get_pixel_size(layout, &mw, &mh);
            total_msg_h += mh + 3;
        }
    } else if (reel_text && strlen(reel_text) > 0) {
        pango_layout_set_text(layout, reel_text, -1);
        int mw = 0, mh = 0;
        pango_layout_get_pixel_size(layout, &mw, &mh);
        total_msg_h += mh;
    }

    int overflow_h = 0;
    if (total_msgs > msg_count && msg_count > 0) {
        overflow_h = 16;
    }

    g_object_unref(layout);
    cairo_destroy(dummy_cr);
    cairo_surface_destroy(dummy_surf);

    /* Geometry:
     * App Header: y=12, height ~14
     * Summary: y=30, height=sum_h
     * Gap: 6px
     * Messages: total_msg_h
     * Overflow badge: overflow_h
     * Bottom padding + Progress bar: 16px
     */
    int needed_h = 30 + sum_h + 6 + total_msg_h + overflow_h + 16;
    if (needed_h < 84) needed_h = 84;
    if (needed_h > 420) needed_h = 420;

    return needed_h;
}

/* Helper: check if two notification summaries belong to the same conversation / group */
static gboolean summaries_match(const char *s1, const char *s2) {
    if (!s1 || !s2) return FALSE;
    if (g_ascii_strcasecmp(s1, s2) == 0) return TRUE;

    char *grp1 = NULL, *snd1 = NULL;
    char *grp2 = NULL, *snd2 = NULL;
    parse_chat_conversation(NULL, s1, NULL, &grp1, &snd1);
    parse_chat_conversation(NULL, s2, NULL, &grp2, &snd2);

    gboolean match = FALSE;
    if (grp1 && grp2 && strlen(grp1) > 0 && g_ascii_strcasecmp(grp1, grp2) == 0) {
        match = TRUE;
    }

    free(grp1); free(snd1);
    free(grp2); free(snd2);
    return match;
}

/* Helper: detect if a notification represents an Instagram / social media reel or video */
static gboolean is_reel_notification(const char *app_name, const char *summary, const char *body) {
    (void)app_name;
    if (!body && !summary) return FALSE;

    #define CONTAINS_WORD(text, word) (text && strcasestr(text, word))
    if (CONTAINS_WORD(body, "sent a reel") ||
        CONTAINS_WORD(body, "sent you a reel") ||
        CONTAINS_WORD(body, "sent a video") ||
        CONTAINS_WORD(body, "shared a reel") ||
        CONTAINS_WORD(body, "shared a video") ||
        CONTAINS_WORD(body, "sent a reel to your group") ||
        CONTAINS_WORD(body, "sent a reel to the group") ||
        CONTAINS_WORD(summary, "sent a reel") ||
        CONTAINS_WORD(body, "instagram.com/reel") ||
        CONTAINS_WORD(body, "/reel/") ||
        CONTAINS_WORD(body, "/reels/") ||
        (CONTAINS_WORD(body, "reel") && (CONTAINS_WORD(body, "sent") || CONTAINS_WORD(body, "shared")))) {
        return TRUE;
    }
    #undef CONTAINS_WORD
    return FALSE;
}

/* Clear all entries for a specific conversation from history when user actively dismisses/actions it */
static void clear_conversation_from_history(const char *app_name, const char *summary) {
    const char *path = "/home/vibecoder/.cache/sys-notif/history.txt";
    FILE *f = fopen(path, "r");
    if (!f) return;

    char *lines[35];
    int count = 0;
    char buf[1024];
    while (fgets(buf, sizeof(buf), f) && count < 30) {
        lines[count++] = strdup(buf);
    }
    fclose(f);

    f = fopen(path, "w");
    if (!f) {
        for (int i = 0; i < count; i++) free(lines[i]);
        return;
    }

    for (int i = 0; i < count; i++) {
        char copy[1024];
        snprintf(copy, sizeof(copy), "%s", lines[i]);
        char *time_p = strtok(copy, "|\n");
        char *app_p = strtok(NULL, "|\n");
        char *sum_p = strtok(NULL, "|\n");
        (void)time_p;

        if (app_p && sum_p) {
            if (g_ascii_strcasecmp(app_p, app_name ? app_name : "System") == 0 &&
                summaries_match(sum_p, summary)) {
                /* User explicitly cleared this conversation: omit from remaining unread history */
                continue;
            }
        }
        fputs(lines[i], f);
    }
    fclose(f);

    for (int i = 0; i < count; i++) free(lines[i]);
    update_polybar_notif_badge();
}


/* Helper: retrieve the most recent chat contact/conversation name from history for an app */
static char *get_last_chat_contact_for_app(const char *target_app) {
    if (!target_app || strlen(target_app) == 0) return NULL;
    const char *history_path = "/home/vibecoder/.cache/sys-notif/history.txt";
    FILE *f = fopen(history_path, "r");
    if (!f) return NULL;

    char *lines[100];
    int count = 0;
    char buf[1024];
    while (fgets(buf, sizeof(buf), f) && count < 100) {
        lines[count++] = strdup(buf);
    }
    fclose(f);

    char *found_contact = NULL;
    for (int i = count - 1; i >= 0; i--) {
        char *line = lines[i];
        g_strstrip(line);
        char *parts[5] = {0};
        int idx = 0;
        char *token = strtok(line, "|");
        while (token && idx < 5) {
            parts[idx++] = token;
            token = strtok(NULL, "|");
        }

        if (idx >= 3 && parts[1] && parts[2]) {
            if (g_ascii_strcasecmp(parts[1], target_app) == 0) {
                const char *s = parts[2];
                if (g_ascii_strcasecmp(s, target_app) != 0 &&
                    g_ascii_strcasecmp(s, "Notification") != 0 &&
                    strlen(s) > 0) {
                    const char *b = strstr(s, " • ");
                    if (b) {
                        found_contact = g_strndup(s, (int)(b - s));
                    } else {
                        found_contact = strdup(s);
                    }
                    g_strstrip(found_contact);
                    break;
                }
            }
        }
    }

    for (int i = 0; i < count; i++) free(lines[i]);
    return found_contact;
}

/* Find active notification in same conversation / thread (stays single card, rolling last 5 messages) */
static NotificationItem *find_group_match(const char *app_name, const char *summary, const char *thread_id, guint replaces_id) {
    NotificationItem *cur = notif_list;
    while (cur) {
        if (replaces_id > 0 && cur->id == replaces_id) {
            return cur;
        }
        if (thread_id && cur->thread_id && strcmp(thread_id, cur->thread_id) == 0) {
            return cur;
        }
        if (app_name && cur->app_name && g_ascii_strcasecmp(app_name, cur->app_name) == 0) {
            if (summaries_match(summary, cur->summary)) {
                return cur;
            }
        }
        cur = cur->next;
    }
    return NULL;
}

/* Activate application or open URL when notification is clicked */
static void activate_app(const char *app_name, const char *summary, const char *body) {
    if (!app_name) return;

    /* Check for URLs in body or summary (ignore root domains like web.whatsapp.com) */
    char url[512] = {0};
    const char *p = (body && strstr(body, "http")) ? strstr(body, "http") :
                    (summary && strstr(summary, "http")) ? strstr(summary, "http") : NULL;
    if (p) {
        if (!strstr(p, "web.whatsapp.com") && !strstr(p, "instagram.com")) {
            int i = 0;
            while (p[i] && p[i] != ' ' && p[i] != '\n' && p[i] != '\t' && p[i] != '"' && p[i] != '\'' && i < 510) {
                url[i] = p[i];
                i++;
            }
            url[i] = '\0';
            if (strlen(url) > 0) {
                if (fork() == 0) {
                    setsid();
                    execlp("xdg-open", "xdg-open", url, NULL);
                    _exit(0);
                }
                return;
            }
        }
    }

    if (fork() == 0) {
        setsid();
        execlp("/home/vibecoder/.local/bin/sys-control", "sys-control", "--activate", app_name, summary ? summary : "", NULL);
        _exit(0);
    }
}

static gboolean notif_timeout_callback(gpointer data) {
    NotificationItem *target = (NotificationItem *)data;
    if (!target) return G_SOURCE_REMOVE;

    if (target->anim_timer_id > 0) {
        g_source_remove(target->anim_timer_id);
        target->anim_timer_id = 0;
    }
    if (target->timer_id > 0) {
        g_source_remove(target->timer_id);
        target->timer_id = 0;
    }

    /* Remove from list */
    NotificationItem **curr = &notif_list;
    while (*curr) {
        if (*curr == target) {
            *curr = target->next;
            break;
        }
        curr = &((*curr)->next);
    }

    /* Send NotificationClosed signal */
    if (dbus_conn) {
        g_dbus_connection_emit_signal(
            dbus_conn, NULL, "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications", "NotificationClosed",
            g_variant_new("(uu)", target->id, 2), NULL
        );
    }

    if (target->pixbuf) g_object_unref(target->pixbuf);
    if (target->icon_surf) cairo_surface_destroy(target->icon_surf);
    if (target->cr) cairo_destroy(target->cr);
    if (target->surface) cairo_surface_destroy(target->surface);
    if (target->win) {
        XDestroyWindow(dpy, target->win);
        target->win = 0;
        XFlush(dpy);
    }
    for (int m = 0; m < target->msg_count; m++) {
        if (target->messages[m]) free(target->messages[m]);
    }
    if (target->latest_reel_text) free(target->latest_reel_text);
    if (target->thread_id) free(target->thread_id);
    if (target->default_action_key) free(target->default_action_key);
    free(target->app_name);
    free(target->summary);
    free(target->icon_name);
    free(target);

    reposition_notifications();

    /* Release freed heap memory back to the kernel immediately */
    malloc_trim(0);

    return G_SOURCE_REMOVE;
}

static gboolean notif_progress_tick(gpointer data) {
    NotificationItem *target = (NotificationItem *)data;
    if (!target) return G_SOURCE_REMOVE;

    if (target->is_hovered) {
        /* Paused while mouse cursor hovers over card */
        target->start_time_us = g_get_monotonic_time() - (gint64)((1.0 - target->progress) * target->duration_us);
        return G_SOURCE_CONTINUE;
    }

    gint64 now = g_get_monotonic_time();
    gint64 elapsed = now - target->start_time_us;

    if (elapsed >= target->duration_us) {
        target->anim_timer_id = 0;
        notif_timeout_callback(target);
        return G_SOURCE_REMOVE;
    }

    /* Progress shrinks backwards from 1.0 down to 0.0 */
    target->progress = 1.0 - ((double)elapsed / (double)target->duration_us);
    render_notification(target);
    return G_SOURCE_CONTINUE;
}

static void render_notification(NotificationItem *item) {
    if (!item->win || !item->cr) return;
    cairo_t *cr = item->cr;
    int w = item->width;
    int h = item->height;

    /* Double-buffering: redirect drawing to offscreen group to completely eliminate tearing & flickering */
    cairo_push_group(cr);

    /* Clear */
    cairo_set_operator(cr, CAIRO_OPERATOR_CLEAR);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    /* Background Card */
    draw_rounded_rect(cr, 1.0, 1.0, w - 2.0, h - 2.0, 12.0);
    cairo_set_source_rgba(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B, COLOR_BASE_A);
    cairo_fill_preserve(cr);

    /* Border with subtle accent (Catppuccin Red for Critical Urgency) */
    if (item->urgency == 2) {
        cairo_set_source_rgba(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B, 0.85);
        cairo_set_line_width(cr, 1.8);
    } else {
        cairo_set_source_rgba(cr, COLOR_SURFACE_R, COLOR_SURFACE_G, COLOR_SURFACE_B, 0.9);
        cairo_set_line_width(cr, 1.2);
    }
    cairo_stroke(cr);

    /* Left accent vertical indicator strip (Red for Critical, Blue for Normal/Low) */
    draw_rounded_rect(cr, 3.0, 10.0, 4.0, h - 20.0, 2.0);
    if (item->urgency == 2) {
        cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
    } else {
        cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
    }
    cairo_fill(cr);

    /* App Icon / PFP Rendering */
    int content_x = 18;
    int icon_size = 38;
    int icon_x = 16;
    int icon_y = 16;

    if (item->icon_surf) {
        cairo_surface_t *surf = item->icon_surf;
        cairo_save(cr);
        if (item->is_avatar) {
            /* Circular avatar */
            double r = icon_size / 2.0;
            double cx = icon_x + r;
            double cy = icon_y + r;

            cairo_arc(cr, cx, cy, r, 0, 2 * M_PI);
            cairo_clip(cr);
            cairo_set_source_surface(cr, surf, icon_x, icon_y);
            cairo_paint(cr);
            cairo_restore(cr);

            /* Antialiased border ring */
            cairo_arc(cr, cx, cy, r, 0, 2 * M_PI);
            cairo_set_source_rgba(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B, 0.5);
            cairo_set_line_width(cr, 1.5);
            cairo_stroke(cr);

            /* Platform micro-badge in bottom-right corner */
            if (item->app_name) {
                double bx = cx + r * 0.58;
                double by = cy + r * 0.58;
                double br = 6.0;

                /* Micro-badge base */
                cairo_arc(cr, bx, by, br, 0, 2 * M_PI);
                cairo_set_source_rgba(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B, 1.0);
                cairo_fill(cr);

                /* Color dot based on platform */
                cairo_arc(cr, bx, by, br - 1.2, 0, 2 * M_PI);
                if (strcasestr(item->app_name, "whatsapp")) {
                    cairo_set_source_rgb(cr, COLOR_GREEN_R, COLOR_GREEN_G, COLOR_GREEN_B);
                } else if (strcasestr(item->app_name, "instagram")) {
                    cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
                } else if (strcasestr(item->app_name, "discord")) {
                    cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
                } else if (strcasestr(item->app_name, "youtube")) {
                    cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
                } else {
                    cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
                }
                cairo_fill(cr);
            }
        } else {
            /* App icon squircle */
            draw_rounded_rect(cr, icon_x, icon_y, icon_size, icon_size, 8.0);
            cairo_clip(cr);
            cairo_set_source_surface(cr, surf, icon_x, icon_y);
            cairo_paint(cr);
            cairo_restore(cr);
        }
        content_x = 64;
    } else {
        /* Elegant fallback badge glyph */
        draw_rounded_rect(cr, icon_x, icon_y, icon_size, icon_size, 8.0);
        cairo_set_source_rgba(cr, COLOR_SURFACE_R, COLOR_SURFACE_G, COLOR_SURFACE_B, 0.7);
        cairo_fill(cr);

        PangoLayout *layout_badge = pango_cairo_create_layout(cr);
        pango_layout_set_font_description(layout_badge, f_badge);
        pango_layout_set_text(layout_badge, "󰂚", -1);
        cairo_set_source_rgb(cr, COLOR_BLUE_R, COLOR_BLUE_G, COLOR_BLUE_B);
        cairo_move_to(cr, icon_x + 9, icon_y + 8);
        pango_cairo_show_layout(cr, layout_badge);
        g_object_unref(layout_badge);
        content_x = 64;
    }

    int text_available_w = w - content_x - 18;

    /* Header: App Name */
    PangoLayout *layout = pango_cairo_create_layout(cr);
    pango_layout_set_font_description(layout, f_app);
    pango_layout_set_text(layout, item->app_name ? item->app_name : "Notification", -1);
    cairo_set_source_rgb(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B);
    cairo_move_to(cr, content_x, 12);
    pango_cairo_show_layout(cr, layout);

    /* Pill Badges in top-right (Messages pill and Reels pill) */
    double cur_pill_right = (double)w - 30.0; /* to the left of the close button */

    /* 1. Reel Pill Badge (Catppuccin Pink/Mauve) */
    if (item->reel_count > 0) {
        char reel_txt[32];
        if (item->reel_count == 1) {
            snprintf(reel_txt, sizeof(reel_txt), "󰕧 1 reel");
        } else {
            snprintf(reel_txt, sizeof(reel_txt), "󰕧 %d reels", item->reel_count);
        }

        PangoLayout *layout_reel = pango_cairo_create_layout(cr);
        pango_layout_set_font_description(layout_reel, f_group);
        pango_layout_set_text(layout_reel, reel_txt, -1);

        int text_w = 0, text_h = 0;
        pango_layout_get_pixel_size(layout_reel, &text_w, &text_h);

        double pill_w = text_w + 14.0;
        double pill_h = 17.0;
        double pill_x = cur_pill_right - pill_w;
        double pill_y = 10.0;

        /* Soft Catppuccin Pink/Mauve Pill background */
        draw_rounded_rect(cr, pill_x, pill_y, pill_w, pill_h, 8.5);
        cairo_set_source_rgba(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B, 0.22);
        cairo_fill_preserve(cr);
        cairo_set_source_rgba(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B, 0.65);
        cairo_set_line_width(cr, 1.0);
        cairo_stroke(cr);

        /* Pill text */
        cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
        cairo_move_to(cr, pill_x + 7.0, pill_y + 1.5);
        pango_cairo_show_layout(cr, layout_reel);
        g_object_unref(layout_reel);

        cur_pill_right = pill_x - 6.0;
    }

    /* 2. Message Count Pill Badge (Catppuccin Peach) */
    int display_msgs = (item->total_msgs > item->msg_count) ? item->total_msgs : item->msg_count;
    if (display_msgs > 1) {
        char grp_txt[32];
        snprintf(grp_txt, sizeof(grp_txt), "%d msgs", display_msgs);

        PangoLayout *layout_grp = pango_cairo_create_layout(cr);
        pango_layout_set_font_description(layout_grp, f_group);
        pango_layout_set_text(layout_grp, grp_txt, -1);

        int text_w = 0, text_h = 0;
        pango_layout_get_pixel_size(layout_grp, &text_w, &text_h);

        double pill_w = text_w + 14.0;
        double pill_h = 17.0;
        double pill_x = cur_pill_right - pill_w;
        double pill_y = 10.0;

        /* Soft Catppuccin Peach Pill background */
        draw_rounded_rect(cr, pill_x, pill_y, pill_w, pill_h, 8.5);
        cairo_set_source_rgba(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B, 0.22);
        cairo_fill_preserve(cr);
        cairo_set_source_rgba(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B, 0.6);
        cairo_set_line_width(cr, 1.0);
        cairo_stroke(cr);

        /* Pill text */
        cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
        cairo_move_to(cr, pill_x + 7.0, pill_y + 1.5);
        pango_cairo_show_layout(cr, layout_grp);
        g_object_unref(layout_grp);
    }

    /* Close Button hint '✕' */
    pango_layout_set_text(layout, "✕", -1);
    cairo_move_to(cr, w - 24, 11);
    pango_cairo_show_layout(cr, layout);

    /* Title / Summary */
    pango_layout_set_font_description(layout, f_sum);
    pango_layout_set_width(layout, text_available_w * PANGO_SCALE);
    pango_layout_set_wrap(layout, PANGO_WRAP_WORD_CHAR);
    pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
    const char *display_title = item->summary ? item->summary : "";
    if (item->app_name && g_ascii_strcasecmp(display_title, item->app_name) == 0) {
        display_title = "Direct Message";
    }
    pango_layout_set_text(layout, display_title, -1);
    int sum_w = 0, sum_h = 0;
    pango_layout_get_pixel_size(layout, &sum_w, &sum_h);

    cairo_set_source_rgb(cr, COLOR_TEXT_R, COLOR_TEXT_G, COLOR_TEXT_B);
    cairo_move_to(cr, content_x, 30);
    pango_cairo_show_layout(cr, layout);

    int body_y = 30 + sum_h + 6;

    /* Message Body: Render stacked messages (up to 5 messages) */
    if (item->msg_count > 0) {
        pango_layout_set_font_description(layout, f_body);
        pango_layout_set_width(layout, text_available_w * PANGO_SCALE);
        pango_layout_set_wrap(layout, PANGO_WRAP_WORD_CHAR);
        pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_NONE);

        for (int m = 0; m < item->msg_count; m++) {
            const char *msg = item->messages[m] ? item->messages[m] : "";
            char line_buf[600];

            if (item->msg_count > 1) {
                snprintf(line_buf, sizeof(line_buf), "• %s", msg);
                if (m < item->msg_count - 1) {
                    cairo_set_source_rgba(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B, 0.75);
                } else {
                    cairo_set_source_rgb(cr, COLOR_TEXT_R, COLOR_TEXT_G, COLOR_TEXT_B);
                }
            } else {
                snprintf(line_buf, sizeof(line_buf), "%s", msg);
                cairo_set_source_rgb(cr, COLOR_TEXT_R, COLOR_TEXT_G, COLOR_TEXT_B);
            }

            char *valid_utf8 = g_utf8_make_valid(line_buf, -1);
            if (!pango_parse_markup(valid_utf8, -1, 0, NULL, NULL, NULL, NULL)) {
                pango_layout_set_text(layout, valid_utf8, -1);
            } else {
                pango_layout_set_markup(layout, valid_utf8, -1);
            }
            g_free(valid_utf8);

            cairo_move_to(cr, content_x, body_y);
            pango_cairo_show_layout(cr, layout);

            int lw = 0, lh = 0;
            pango_layout_get_pixel_size(layout, &lw, &lh);
            body_y += lh + 3;
        }

        /* Show subtle overflow indicator if more than 5 messages received in this thread */
        if (item->total_msgs > item->msg_count) {
            int older_count = item->total_msgs - item->msg_count;
            char overflow_txt[64];
            snprintf(overflow_txt, sizeof(overflow_txt), "+ %d older in Notification Center", older_count);

            PangoLayout *layout_over = pango_cairo_create_layout(cr);
            pango_layout_set_font_description(layout_over, f_group);
            pango_layout_set_text(layout_over, overflow_txt, -1);

            cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
            cairo_move_to(cr, content_x + 2, body_y + 1);
            pango_cairo_show_layout(cr, layout_over);
            g_object_unref(layout_over);
        }
    } else if (item->reel_count > 0) {
        /* Only reels received: show elegant reel indicator in body */
        pango_layout_set_font_description(layout, f_body);
        pango_layout_set_width(layout, text_available_w * PANGO_SCALE);
        char reel_body[128];
        if (item->reel_count == 1) {
            snprintf(reel_body, sizeof(reel_body), "<span foreground=\"#cdd6f4\">• Sent a reel</span>");
        } else {
            snprintf(reel_body, sizeof(reel_body), "<span foreground=\"#cdd6f4\">• Sent %d reels</span>", item->reel_count);
        }
        pango_layout_set_markup(layout, reel_body, -1);
        cairo_move_to(cr, content_x, body_y);
        pango_cairo_show_layout(cr, layout);
    }

    g_object_unref(layout);

    /* Backward-Shrinking White Progress Bar (Timeout Indicator) */
    double p = item->progress;
    if (p < 0.0) p = 0.0;
    if (p > 1.0) p = 1.0;

    double bar_margin = 14.0;
    double bar_w_total = (double)w - (2.0 * bar_margin);
    double bar_h = 2.5;
    double bar_y = (double)h - 6.0;

    /* Subtle dark track */
    draw_rounded_rect(cr, bar_margin, bar_y, bar_w_total, bar_h, 1.25);
    cairo_set_source_rgba(cr, COLOR_SURFACE_R, COLOR_SURFACE_G, COLOR_SURFACE_B, 0.45);
    cairo_fill(cr);

    /* Active progress bar shrinking backwards (Red for Critical Urgency, White for Normal) */
    double cur_w = bar_w_total * p;
    if (cur_w > 1.0) {
        draw_rounded_rect(cr, bar_margin, bar_y, cur_w, bar_h, 1.25);
        if (item->urgency == 2) {
            cairo_set_source_rgba(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B, 0.95); /* Vivid Red */
        } else {
            cairo_set_source_rgba(cr, 1.0, 1.0, 1.0, 0.85); /* Clean white */
        }
        cairo_fill(cr);
    }

    /* Atomically blit the complete rendered frame to the window in a single operation */
    cairo_pop_group_to_source(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);

    cairo_surface_flush(item->surface);
    XFlush(dpy);
}

/* Detect web service from browser notifications (e.g. Instagram, WhatsApp, YouTube on Firefox/Chrome) */
static void detect_web_service(const char **app_name, const char **app_icon,
                               const char *summary, const char *body, GVariant *hints) {
    if (!app_name) return;
    const char *orig_app = *app_name;

    /* Check if browser or generic sender */
    gboolean is_browser_or_generic = FALSE;
    if (!orig_app || strlen(orig_app) == 0) {
        is_browser_or_generic = TRUE;
    } else if (strcasestr(orig_app, "firefox") ||
               strcasestr(orig_app, "chrom") ||
               strcasestr(orig_app, "brave") ||
               strcasestr(orig_app, "browser") ||
               strcasestr(orig_app, "notify-send") ||
               strcasestr(orig_app, "web")) {
        is_browser_or_generic = TRUE;
    }

    if (!is_browser_or_generic) return;

    const char *icon_str = (app_icon && *app_icon) ? *app_icon : "";

    /* Also check hints string values (origin, desktop-entry, image-path, tag) */
    char hint_context[512] = {0};
    if (hints) {
        static const char *hint_keys[] = { "desktop-entry", "origin", "image-path", "avatar-path", "tag", NULL };
        for (int h = 0; hint_keys[h]; h++) {
            GVariant *hv = g_variant_lookup_value(hints, hint_keys[h], G_VARIANT_TYPE_STRING);
            if (hv) {
                const char *hs = g_variant_get_string(hv, NULL);
                if (hs) {
                    strncat(hint_context, " ", sizeof(hint_context) - strlen(hint_context) - 1);
                    strncat(hint_context, hs, sizeof(hint_context) - strlen(hint_context) - 1);
                }
                g_variant_unref(hv);
            }
        }
    }

    #define MATCHES(needle) \
        ((summary && strcasestr(summary, needle)) || \
         (body && strcasestr(body, needle)) || \
         strcasestr(icon_str, needle) || \
         strcasestr(hint_context, needle))

    #define SET_APP(name, icon_name) do { \
        *app_name = name; \
        if (!(*app_icon) || ((*app_icon)[0] != '/' && strncmp(*app_icon, "file://", 7) != 0)) { \
            *app_icon = icon_name; \
        } \
    } while (0)

    if (MATCHES("instagram") || MATCHES("instagr.am") || MATCHES("ig.me") || MATCHES("cdninstagram") || MATCHES("fbcdn")) {
        SET_APP("Instagram", "instagram");
    } else if (MATCHES("whatsapp") || MATCHES("web.whatsapp.com") || MATCHES("whatsapp.net")) {
        SET_APP("WhatsApp", "whatsapp");
    } else if (MATCHES("youtube") || MATCHES("youtu.be")) {
        SET_APP("YouTube", "youtube");
    } else if (MATCHES("discord") || MATCHES("discordapp")) {
        SET_APP("Discord", "discord");
    } else if (MATCHES("twitter") || MATCHES("x.com") || MATCHES("t.co")) {
        SET_APP("X (Twitter)", "twitter");
    } else if (MATCHES("reddit") || MATCHES("reddit.com")) {
        SET_APP("Reddit", "reddit");
    } else if (MATCHES("github") || MATCHES("github.com")) {
        SET_APP("GitHub", "github");
    } else if (MATCHES("gmail") || MATCHES("google mail") || MATCHES("mail.google.com")) {
        SET_APP("Gmail", "gmail");
    } else if (MATCHES("twitch") || MATCHES("twitch.tv")) {
        SET_APP("Twitch", "twitch");
    } else if (MATCHES("spotify") || MATCHES("spotify.com")) {
        SET_APP("Spotify", "spotify");
    } else if (MATCHES("telegram") || MATCHES("web.telegram.org") || MATCHES("t.me")) {
        SET_APP("Telegram", "telegram");
    } else if (MATCHES("slack") || MATCHES("slack.com")) {
        SET_APP("Slack", "slack");
    }
    #undef SET_APP
    #undef MATCHES
}

static void append_history(const char *app, const char *summary, const char *body, const char *icon_path) {
    if (!app) app = "System";

    /* Drop Instagram "unread messages" spam completely */
    if (is_instagram_unread_notice(app, summary, body)) {
        return;
    }

    /* NEVER persist notification center confirmations, DND toggles, transient system alerts, or terminal messages */
    if (g_ascii_strcasecmp(app, "Notification Center") == 0 ||
        g_ascii_strcasecmp(app, "Do Not Disturb") == 0 ||
        g_ascii_strcasecmp(app, "sys-notif") == 0 ||
        g_ascii_strcasecmp(app, "sys-control") == 0 ||
        g_ascii_strcasecmp(app, "notify-send") == 0 ||
        strcasestr(app, "terminal") != NULL ||
        strcasestr(app, "kitty") != NULL ||
        strcasestr(app, "alacritty") != NULL ||
        strcasestr(app, "wezterm") != NULL ||
        strcasestr(app, "xterm") != NULL ||
        strcasestr(app, "foot") != NULL ||
        strcasestr(app, "ghostty") != NULL ||
        strcasestr(app, "urxvt") != NULL ||
        strcasestr(app, "bash") != NULL ||
        strcasestr(app, "zsh") != NULL ||
        strcasestr(app, "fish") != NULL) {
        return;
    }
    if (summary && (strcasestr(summary, "History Cleared") ||
                    strcasestr(summary, "Notification Dismissed") ||
                    strcasestr(summary, "No Missed Notifications") ||
                    strcasestr(summary, "Touchpad") ||
                    strcasestr(summary, "Screenshot Captured") ||
                    strcasestr(summary, "Full Screenshot Saved"))) {
        return;
    }

    const char *cache_dir = "/home/vibecoder/.cache/sys-notif";
    g_mkdir_with_parents(cache_dir, 0755);
    char path[512];
    snprintf(path, sizeof(path), "%s/history.txt", cache_dir);

    FILE *f = fopen(path, "r");
    char *lines[35];
    int count = 0;
    if (f) {
        char buf[1024];
        while (fgets(buf, sizeof(buf), f) && count < 30) {
            lines[count++] = strdup(buf);
        }
        fclose(f);
    }

    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char time_str[32];
    strftime(time_str, sizeof(time_str), "%I:%M %p", tm_info);

    char clean_sum[128] = {0};
    char clean_bod[256] = {0};
    if (summary) {
        for (int i = 0; summary[i] && i < 127; i++) {
            clean_sum[i] = (summary[i] == '\n' || summary[i] == '\r' || summary[i] == '|') ? ' ' : summary[i];
        }
        g_strstrip(clean_sum);
    }
    if (body) {
        for (int i = 0; body[i] && i < 255; i++) {
            clean_bod[i] = (body[i] == '\n' || body[i] == '\r' || body[i] == '|') ? ' ' : body[i];
        }
        g_strstrip(clean_bod);
    }

    const char *icon_to_log = icon_path;
    if (!icon_to_log || strlen(icon_to_log) == 0) {
        if (app && strcasestr(app, "whatsapp")) icon_to_log = "whatsapp-desktop";
        else if (app && strcasestr(app, "instagram")) icon_to_log = "instagram";
        else if (app && strcasestr(app, "discord")) icon_to_log = "discord";
        else if (app && strcasestr(app, "youtube")) icon_to_log = "youtube";
        else if (app && strcasestr(app, "spotify")) icon_to_log = "spotify";
        else if (app && strcasestr(app, "telegram")) icon_to_log = "telegram";
        else if (app && strcasestr(app, "power")) icon_to_log = "battery-charging";
        else icon_to_log = "preferences-desktop-notification-bell";
    }

    f = fopen(path, "w");
    if (f) {
        int start = (count >= 25) ? (count - 24) : 0;
        for (int i = start; i < count; i++) {
            fputs(lines[i], f);
        }
        fprintf(f, "%s|%s|%s|%s|%s\n", time_str, app ? app : "System", clean_sum, clean_bod, icon_to_log);
        fclose(f);
    }

    for (int i = 0; i < count; i++) free(lines[i]);
    update_polybar_notif_badge();
}

/* -------------------------------------------------------------
 * Intelligent Title & Body Normalizer (Username & Group Parser)
 * ------------------------------------------------------------- */
static void normalize_notification_content(const char *app_name,
                                           const char *raw_summary,
                                           const char *raw_body,
                                           char *out_summary, size_t sum_sz,
                                           char *out_body, size_t body_sz) {
    char sum[256] = {0};
    char bod[512] = {0};

    if (raw_summary) snprintf(sum, sizeof(sum), "%s", raw_summary);
    if (raw_body) snprintf(bod, sizeof(bod), "%s", raw_body);

    /* 1. Strip whitespace from edges */
    g_strstrip(sum);
    g_strstrip(bod);

    /* 2. Strip generic domain names if summary is a URL */
    if (g_str_has_prefix(sum, "https://") || g_str_has_prefix(sum, "http://")) {
        char *slash = strchr(sum + 8, '/');
        if (slash) *slash = '\0';
        if (strcasestr(sum, "whatsapp") || strcasestr(sum, "instagram") || strcasestr(sum, "discord")) {
            sum[0] = '\0';
        }
    }
    if (strcasecmp(sum, "web.whatsapp.com") == 0 ||
        strcasecmp(sum, "www.instagram.com") == 0 ||
        strcasecmp(sum, "discord.com") == 0) {
        sum[0] = '\0';
    }

    /* 3. Strip app name prefix (e.g. "Instagram • ", "WhatsApp: ", "Discord - ") */
    if (app_name && strlen(app_name) > 0 && strlen(sum) > 0) {
        static const char *delims[] = { " • ", ": ", " - ", " | ", NULL };
        for (int d = 0; delims[d]; d++) {
            char pfx[64];
            snprintf(pfx, sizeof(pfx), "%s%s", app_name, delims[d]);
            if (g_ascii_strncasecmp(sum, pfx, strlen(pfx)) == 0) {
                memmove(sum, sum + strlen(pfx), strlen(sum) - strlen(pfx) + 1);
                g_strstrip(sum);
                break;
            }
        }

        /* 4. Strip app name suffix (e.g. " • Instagram", " - WhatsApp", " (Instagram)", " on Discord") */
        for (int d = 0; delims[d]; d++) {
            char sfx[64];
            snprintf(sfx, sizeof(sfx), "%s%s", delims[d], app_name);
            int sfx_len = (int)strlen(sfx);
            int sum_len = (int)strlen(sum);
            if (sum_len > sfx_len && g_ascii_strcasecmp(sum + sum_len - sfx_len, sfx) == 0) {
                sum[sum_len - sfx_len] = '\0';
                g_strstrip(sum);
                break;
            }
        }
        char sfx_paren[64], sfx_on[64];
        snprintf(sfx_paren, sizeof(sfx_paren), " (%s)", app_name);
        snprintf(sfx_on, sizeof(sfx_on), " on %s", app_name);
        if (g_str_has_suffix(sum, sfx_paren)) {
            sum[strlen(sum) - strlen(sfx_paren)] = '\0';
            g_strstrip(sum);
        } else if (g_str_has_suffix(sum, sfx_on)) {
            sum[strlen(sum) - strlen(sfx_on)] = '\0';
            g_strstrip(sum);
        }
    }

    /* 5. Check if summary is still just the app name itself (or empty, or generic placeholder) */
    gboolean is_generic_sum = FALSE;
    if (strlen(sum) == 0 ||
        (app_name && g_ascii_strcasecmp(sum, app_name) == 0) ||
        g_ascii_strcasecmp(sum, "Notification") == 0 ||
        g_ascii_strcasecmp(sum, "Notifications") == 0 ||
        g_ascii_strcasecmp(sum, "Direct") == 0 ||
        g_ascii_strcasecmp(sum, "Messages") == 0 ||
        g_ascii_strcasecmp(sum, "Message") == 0 ||
        g_ascii_strcasecmp(sum, "New Message") == 0 ||
        g_ascii_strcasecmp(sum, "Chat") == 0) {
        is_generic_sum = TRUE;
    }

    /* 6. Extract sender or group from body */
    if (strlen(bod) > 0) {
        /* Pattern 0: "From •User•" or "From User:" (Instagram Direct Web notifications) */
        if (is_generic_sum && (g_str_has_prefix(bod, "From ") || g_str_has_prefix(bod, "from "))) {
            const char *p = bod + 5;
            while (*p == ' ' || *p == '\t') p++;
            const char *bullet_start = strstr(p, "•");
            char sender[64] = {0};
            if (bullet_start) {
                const char *u_start = bullet_start + strlen("•");
                while (*u_start == ' ') u_start++;
                const char *bullet_end = strstr(u_start, "•");
                if (bullet_end && (bullet_end - u_start) > 0 && (bullet_end - u_start) < 60) {
                    snprintf(sender, sizeof(sender), "%.*s", (int)(bullet_end - u_start), u_start);
                    g_strstrip(sender);
                }
            }
            if (strlen(sender) == 0) {
                const char *colon = strchr(p, ':');
                if (colon && (colon - p) < 60) {
                    snprintf(sender, sizeof(sender), "%.*s", (int)(colon - p), p);
                } else {
                    g_strlcpy(sender, p, sizeof(sender));
                }
                g_strstrip(sender);
            }

            if (strlen(sender) > 0) {
                snprintf(sum, sizeof(sum), "%s", sender);
                const char *colon = strchr(bod, ':');
                if (colon) {
                    const char *msg = colon + 1;
                    while (*msg == ' ') msg++;
                    snprintf(bod, sizeof(bod), "%s", msg);
                } else {
                    snprintf(bod, sizeof(bod), "Sent a message");
                }
                is_generic_sum = FALSE;
            }
        }

        /* Pattern A: "Sender: Message" */
        const char *colon = strchr(bod, ':');
        if (colon && (colon - bod) >= 2 && (colon - bod) <= 36) {
            char sender[64] = {0};
            int s_len = (int)(colon - bod);
            snprintf(sender, sizeof(sender), "%.*s", s_len, bod);
            g_strstrip(sender);

            const char *msg = colon + 1;
            while (*msg == ' ') msg++;

            if (is_generic_sum) {
                /* Promote sender to summary */
                snprintf(sum, sizeof(sum), "%s", sender);
                snprintf(bod, sizeof(bod), "%s", msg);
                is_generic_sum = FALSE;
            } else {
                /* Group conversation: isolate base group name if it already has bullet */
                char group[128] = {0};
                const char *bullet = strstr(sum, " • ");
                if (bullet) {
                    snprintf(group, sizeof(group), "%.*s", (int)(bullet - sum), sum);
                } else {
                    snprintf(group, sizeof(group), "%s", sum);
                }
                g_strstrip(group);

                snprintf(sum, sizeof(sum), "%s • %s", group, sender);
                /* For groups, preserve "Sender: Message" so threaded cards display who sent each message */
                snprintf(bod, sizeof(bod), "%s: %s", sender, msg);
            }
        }

        /* Pattern B: Social media actions like "Alex sent a reel...", "Alex liked your story", etc. */
        if (is_generic_sum) {
            static const char *action_verbs[] = {
                " sent you a sticker", " sent a sticker",
                " sent you a gif", " sent a gif",
                " sent a reel to your group", " sent a reel to the group",
                " sent you a reel", " sent a reel",
                " sent you a message", " sent a message",
                " sent you a photo", " sent a photo",
                " sent you a video", " sent a video",
                " sent you a voice", " sent a voice",
                " sent an attachment", " liked your ",
                " reacted to ", " mentioned you",
                " started following", " requested to", NULL
            };

            for (int v = 0; action_verbs[v]; v++) {
                const char *pos = strcasestr(bod, action_verbs[v]);
                if (pos && (pos - bod) >= 2 && (pos - bod) <= 40) {
                    char sender[64] = {0};
                    int s_len = (int)(pos - bod);
                    snprintf(sender, sizeof(sender), "%.*s", s_len, bod);
                    g_strstrip(sender);

                    /* Capitalize the action description in body */
                    char clean_action[256];
                    const char *action_start = pos + 1;
                    snprintf(clean_action, sizeof(clean_action), "%s", action_start);
                    if (clean_action[0] >= 'a' && clean_action[0] <= 'z') {
                        clean_action[0] -= 32;
                    }

                    snprintf(sum, sizeof(sum), "%s", sender);
                    snprintf(bod, sizeof(bod), "%s", clean_action);
                    is_generic_sum = FALSE;
                    break;
                }
            }
        }

        /* Pattern C: "Sender to Group" in summary (e.g. "yaarouse capitan to 10th gc", "ALOO to 10th gc") */
        const char *to_kw = strcasestr(sum, " to ");
        if (to_kw && (to_kw - sum) >= 2) {
            char sender[64] = {0};
            char group[128] = {0};
            int s_len = (int)(to_kw - sum);
            snprintf(sender, sizeof(sender), "%.*s", s_len, sum);
            g_strstrip(sender);

            const char *grp_start = to_kw + 4;
            while (*grp_start == ' ') grp_start++;
            snprintf(group, sizeof(group), "%s", grp_start);
            g_strstrip(group);

            if (strlen(group) > 0 && strlen(sender) > 0) {
                snprintf(sum, sizeof(sum), "%s • %s", group, sender);
                is_generic_sum = FALSE;
            }
        }

        /* Pattern D: "Sender in Group" or "Sender @ Group" in summary */
        if (strstr(sum, " • ") == NULL) {
            const char *sep = strcasestr(sum, " in ");
            int sep_len = 4;
            if (!sep) {
                sep = strstr(sum, " @ ");
                sep_len = 3;
            }
            if (sep && (sep - sum) >= 2) {
                char sender[64] = {0};
                char group[128] = {0};
                int s_len = (int)(sep - sum);
                snprintf(sender, sizeof(sender), "%.*s", s_len, sum);
                g_strstrip(sender);

                const char *grp_start = sep + sep_len;
                while (*grp_start == ' ') grp_start++;
                snprintf(group, sizeof(group), "%s", grp_start);
                g_strstrip(group);

                if (strlen(group) > 0 && strlen(sender) > 0) {
                    snprintf(sum, sizeof(sum), "%s • %s", group, sender);
                    is_generic_sum = FALSE;
                }
            }
        }

        /* Pattern E: Body has "... to Group" when summary is just a single name/sender (e.g. "Sent a photo to 10th gc") */
        if (strstr(sum, " • ") == NULL && strlen(bod) > 0) {
            const char *to_in_body = strcasestr(bod, " to ");
            if (to_in_body && (to_in_body - bod) >= 3) {
                const char *grp_start = to_in_body + 4;
                while (*grp_start == ' ') grp_start++;
                if (strlen(grp_start) > 0 && strcasecmp(grp_start, "your group") != 0 && strcasecmp(grp_start, "the group") != 0) {
                    char sender[64] = {0};
                    snprintf(sender, sizeof(sender), "%s", sum);
                    g_strstrip(sender);

                    snprintf(sum, sizeof(sum), "%s • %s", grp_start, sender);

                    /* Truncate " to <Group>" from body */
                    char clean_b[512] = {0};
                    snprintf(clean_b, sizeof(clean_b), "%.*s", (int)(to_in_body - bod), bod);
                    g_strstrip(clean_b);
                    if (strlen(clean_b) > 0) {
                        snprintf(bod, sizeof(bod), "%s", clean_b);
                    }
                    is_generic_sum = FALSE;
                }
            }
        }
    }

    /* If summary is STILL generic app name (e.g. "Instagram"), check active cards and recent history */
    if (is_generic_sum && app_name && strlen(app_name) > 0) {
        /* 1. Check if there is an active notification card for this app with a real contact */
        NotificationItem *cur = notif_list;
        while (cur) {
            if (cur->app_name && g_ascii_strcasecmp(cur->app_name, app_name) == 0 &&
                cur->summary && g_ascii_strcasecmp(cur->summary, app_name) != 0 &&
                strlen(cur->summary) > 0) {
                snprintf(sum, sizeof(sum), "%s", cur->summary);
                is_generic_sum = FALSE;
                break;
            }
            cur = cur->next;
        }

        /* 2. If no active card, check history.txt for the last known chat contact for this app */
        if (is_generic_sum) {
            char *last_contact = get_last_chat_contact_for_app(app_name);
            if (last_contact) {
                snprintf(sum, sizeof(sum), "%s", last_contact);
                is_generic_sum = FALSE;
                free(last_contact);
            }
        }
    }

    /* Fallback if summary was completely blank */
    if (strlen(sum) == 0) {
        snprintf(sum, sizeof(sum), "%s", app_name ? app_name : "Notification");
    }

    snprintf(out_summary, sum_sz, "%s", sum);
    snprintf(out_body, body_sz, "%s", bod);
}

static gboolean is_single_system_alert(const char *app_name, const char *summary) {
    if (!app_name) return FALSE;
    char lower[128];
    g_strlcpy(lower, app_name, sizeof(lower));
    for (int i = 0; lower[i]; i++) lower[i] = g_ascii_tolower(lower[i]);

    if (strstr(lower, "power") || strstr(lower, "battery") ||
        strstr(lower, "volume") || strstr(lower, "brightness") ||
        strstr(lower, "backlight") || strstr(lower, "osd")) {
        return TRUE;
    }
    if (summary) {
        if (strcasestr(summary, "battery") || strcasestr(summary, "charging")) return TRUE;
    }
    return FALSE;
}

static guint show_notification(const char *app_name, const char *summary, const char *body,
                              const char *icon_name, GVariant *hints, GVariant *actions, int timeout_ms, guint replaces_id) {
    /* Drop Instagram "You have unread messages" / "unseen notifications" spam immediately */
    if (is_instagram_unread_notice(app_name, summary, body)) {
        return next_id++;
    }

    /* Intelligently normalize usernames, group names, and message body */
    char clean_summary[256];
    char clean_body[512];
    normalize_notification_content(app_name, summary, body,
                                   clean_summary, sizeof(clean_summary),
                                   clean_body, sizeof(clean_body));

    /* Check again after normalization in case Instagram placed it in summary or body */
    if (is_instagram_unread_notice(app_name, clean_summary, clean_body)) {
        return next_id++;
    }

    /* DEBUG: Log incoming notification parameters and hints */
    {
        FILE *df = fopen("/tmp/notif_hints.log", "a");
        if (df) {
            fprintf(df, "=== NOTIF: app='%s', sum='%s', bod='%s', icon='%s', rep=%u ===\n",
                    app_name ? app_name : "", summary ? summary : "", body ? body : "", icon_name ? icon_name : "", replaces_id);
            if (hints) {
                GVariantIter iter;
                g_variant_iter_init(&iter, hints);
                char *k;
                GVariant *v;
                while (g_variant_iter_next(&iter, "{sv}", &k, &v)) {
                    char *printed = g_variant_print(v, TRUE);
                    fprintf(df, "  HINT: '%s' = %s\n", k, printed);
                    g_free(printed);
                    g_free(k);
                    g_variant_unref(v);
                }
            }
            fclose(df);
        }
    }

    /* Extract urgency, transient, and thread-id from hints */
    guint8 urgency = 1; /* Default: Normal (1) */
    gboolean is_transient = FALSE;
    const char *thread_id = NULL;

    if (hints) {
        GVariant *urg_v = g_variant_lookup_value(hints, "urgency", NULL);
        if (urg_v) {
            if (g_variant_is_of_type(urg_v, G_VARIANT_TYPE_BYTE)) {
                urgency = g_variant_get_byte(urg_v);
            } else if (g_variant_is_of_type(urg_v, G_VARIANT_TYPE_INT32)) {
                urgency = (guint8)g_variant_get_int32(urg_v);
            } else if (g_variant_is_of_type(urg_v, G_VARIANT_TYPE_UINT32)) {
                urgency = (guint8)g_variant_get_uint32(urg_v);
            } else if (g_variant_is_of_type(urg_v, G_VARIANT_TYPE_INT16)) {
                urgency = (guint8)g_variant_get_int16(urg_v);
            }
            g_variant_unref(urg_v);
        }
        if (urgency > 2) urgency = 2;

        GVariant *trans_v = g_variant_lookup_value(hints, "transient", G_VARIANT_TYPE_BOOLEAN);
        if (trans_v) {
            is_transient = g_variant_get_boolean(trans_v);
            g_variant_unref(trans_v);
        }

        GVariant *th_v = g_variant_lookup_value(hints, "thread-id", G_VARIANT_TYPE_STRING);
        if (!th_v) th_v = g_variant_lookup_value(hints, "x-dunst-stack-tag", G_VARIANT_TYPE_STRING);
        if (th_v) {
            thread_id = g_variant_get_string(th_v, NULL);
            g_variant_unref(th_v);
        }
    }

    /* Do Not Disturb mode: Critical urgency (2) bypasses DND so emergency alerts are never missed */
    if (is_dnd_active() && urgency < 2) {
        if (!is_transient) {
            append_history(app_name ? app_name : "System", clean_summary, clean_body, icon_name ? icon_name : app_name);
        }
        return next_id++;
    }

    guint id = next_id++;

    /* Extract action key if provided */
    const char *default_action_key = NULL;
    if (actions && g_variant_is_of_type(actions, G_VARIANT_TYPE_STRING_ARRAY)) {
        gsize n_actions = g_variant_n_children(actions);
        for (gsize i = 0; i < n_actions; i += 2) {
            GVariant *k = g_variant_get_child_value(actions, i);
            const char *ks = g_variant_get_string(k, NULL);
            if (strcmp(ks, "default") == 0 || !default_action_key) {
                default_action_key = ks;
            }
            g_variant_unref(k);
        }
    }

    /* Parse chat conversation attributes (group name vs individual sender) */
    char *chat_grp = NULL, *chat_snd = NULL;
    parse_chat_conversation(app_name, clean_summary, clean_body, &chat_grp, &chat_snd);

    gboolean is_group_chat = (chat_grp && chat_snd && strlen(chat_grp) > 0 && strlen(chat_snd) > 0 &&
                              g_ascii_strcasecmp(chat_grp, chat_snd) != 0);

    /* Extract avatar / PFP or icon (with group & contact avatar cache support) */
    gboolean is_avatar = FALSE;
    char *cached_avatar_path = NULL;
    GdkPixbuf *pb = NULL;

    if (is_group_chat) {
        /* In a group chat, the card avatar MUST be the group icon */
        pb = load_cached_group_avatar(app_name, chat_grp, &cached_avatar_path);
        if (pb) {
            is_avatar = TRUE;
        } else {
            /* Fallback to app icon, NEVER use an individual sender's face as the group's icon */
            pb = load_app_icon(icon_name, app_name, 38);
            is_avatar = FALSE;
        }

        /* If hints contained the individual sender's profile picture, cache it under sender's name */
        gboolean snd_is_avatar = FALSE;
        GdkPixbuf *snd_pb = extract_pfp_from_hints(hints, icon_name, &snd_is_avatar);
        if (snd_pb && snd_is_avatar) {
            cache_avatar_pixbuf(snd_pb, app_name, chat_snd);
            g_object_unref(snd_pb);
        } else if (snd_pb) {
            g_object_unref(snd_pb);
        }
    } else {
        /* Direct message (DM) or system notification */
        pb = extract_pfp_from_hints(hints, icon_name, &is_avatar);
        if (pb && is_avatar) {
            cached_avatar_path = cache_avatar_pixbuf(pb, app_name, clean_summary);
        } else {
            pb = load_cached_group_avatar(app_name, clean_summary, &cached_avatar_path);
            if (pb) {
                is_avatar = TRUE;
            } else {
                pb = load_app_icon(icon_name, app_name, 38);
                is_avatar = FALSE;
            }
        }
    }

    gboolean is_reel = is_reel_notification(app_name, clean_summary, clean_body);

    /* Check for existing notification in the same group/conversation (holds up to 5, rolls FIFO) */
    NotificationItem *existing = find_group_match(app_name, clean_summary, thread_id, replaces_id);
    if (existing) {
        if (is_reel) {
            existing->reel_count++;
            if (existing->latest_reel_text) free(existing->latest_reel_text);
            existing->latest_reel_text = strdup(clean_body);
        } else {
            if (!is_single_system_alert(app_name, clean_summary)) {
                existing->total_msgs++;

                char formatted_msg[768];
                if (chat_snd && strlen(chat_snd) > 0 && chat_grp && g_ascii_strcasecmp(chat_snd, chat_grp) != 0 &&
                    g_ascii_strcasecmp(chat_snd, app_name) != 0 && !g_str_has_prefix(clean_body, chat_snd)) {
                    snprintf(formatted_msg, sizeof(formatted_msg), "%s: %s", chat_snd, clean_body);
                } else {
                    snprintf(formatted_msg, sizeof(formatted_msg), "%s", clean_body);
                }

                if (existing->msg_count < MAX_GROUP_MSGS) {
                    existing->messages[existing->msg_count++] = strdup(formatted_msg);
                } else {
                    /* Rolling window of 5: discard oldest, shift down, add newest */
                    free(existing->messages[0]);
                    for (int m = 1; m < MAX_GROUP_MSGS; m++) {
                        existing->messages[m - 1] = existing->messages[m];
                    }
                    existing->messages[MAX_GROUP_MSGS - 1] = strdup(formatted_msg);
                }
            } else {
                /* Non-chat apps update in place */
                existing->total_msgs = 1;
                for (int m = 0; m < existing->msg_count; m++) {
                    if (existing->messages[m]) free(existing->messages[m]);
                    existing->messages[m] = NULL;
                }
                existing->messages[0] = strdup(clean_body);
                existing->msg_count = 1;
            }
        }

        /* Update summary to base group or latest summary (never downgrade to generic app name) */
        if (chat_grp && strlen(chat_grp) > 0 && g_ascii_strcasecmp(chat_grp, app_name) != 0) {
            free(existing->summary);
            existing->summary = strdup(chat_grp);
        } else if (strlen(clean_summary) > 0 && g_ascii_strcasecmp(clean_summary, app_name) != 0) {
            free(existing->summary);
            existing->summary = strdup(clean_summary);
        }
        if (default_action_key) {
            free(existing->default_action_key);
            existing->default_action_key = strdup(default_action_key);
        }

        if (is_group_chat) {
            /* Group cards keep their group icon; do not replace with sender's photo */
            if (pb) {
                g_object_unref(pb);
                pb = NULL;
            }
        } else if (pb && is_avatar) {
            if (existing->pixbuf) g_object_unref(existing->pixbuf);
            existing->pixbuf = pb;
            existing->is_avatar = TRUE;
            if (existing->icon_surf) {
                cairo_surface_destroy(existing->icon_surf);
                existing->icon_surf = NULL;
            }
            existing->icon_surf = pixbuf_to_surface(existing->pixbuf);
            pb = NULL;
        } else if (pb) {
            g_object_unref(pb);
            pb = NULL;
        }

        /* Dynamic card height to fit stacked messages */
        int needed_h = calculate_notification_height(existing->summary, existing->messages, existing->msg_count, existing->total_msgs, existing->latest_reel_text, existing->width);
        if (existing->height != needed_h) {
            existing->height = needed_h;
            XResizeWindow(dpy, existing->win, existing->width, existing->height);
            if (existing->cr) cairo_destroy(existing->cr);
            if (existing->surface) cairo_surface_destroy(existing->surface);
            existing->surface = cairo_xlib_surface_create(dpy, existing->win, visual, existing->width, existing->height);
            existing->cr = cairo_create(existing->surface);
            reposition_notifications();
        }

        if (urgency > existing->urgency) {
            existing->urgency = urgency;
        }

        int to = timeout_ms > 0 ? timeout_ms : 5000;
        if (existing->urgency == 2 && to < 20000) {
            to = 20000;
        }
        existing->start_time_us = g_get_monotonic_time();
        existing->duration_us = (gint64)to * 1000;
        existing->progress = 1.0;
        if (existing->anim_timer_id == 0) {
            existing->anim_timer_id = g_timeout_add(30, notif_progress_tick, existing);
        }

        render_notification(existing);
        cairo_surface_flush(existing->surface);
        XFlush(dpy);

        if (existing->urgency == 2) {
            play_sound("dialog-warning");
        } else {
            play_sound("message");
        }

        if (!is_transient && !is_single_system_alert(existing->app_name, existing->summary)) {
            const char *log_icon = cached_avatar_path ? cached_avatar_path : (existing->icon_name ? existing->icon_name : existing->app_name);
            char log_sum[512];
            if (chat_snd && strlen(chat_snd) > 0 && chat_grp && g_ascii_strcasecmp(chat_snd, chat_grp) != 0) {
                snprintf(log_sum, sizeof(log_sum), "%s • %s", chat_grp, chat_snd);
            } else {
                snprintf(log_sum, sizeof(log_sum), "%s", existing->summary);
            }
            append_history(existing->app_name, log_sum, clean_body, log_icon);
        }

        free(chat_grp); free(chat_snd);
        return existing->id;
    }

    /* New notification: initialize first message */
    int init_msgs = 0;
    int init_total = 1;
    char *init_messages[MAX_GROUP_MSGS] = {0};
    char *init_reel_text = NULL;
    int init_reels = 0;

    if (is_reel) {
        init_reels = 1;
        init_reel_text = strdup(clean_body);
    } else {
        init_msgs = 1;
        char formatted_msg[768];
        if (chat_snd && strlen(chat_snd) > 0 && chat_grp && g_ascii_strcasecmp(chat_snd, chat_grp) != 0 &&
            g_ascii_strcasecmp(chat_snd, app_name) != 0 && !g_str_has_prefix(clean_body, chat_snd)) {
            snprintf(formatted_msg, sizeof(formatted_msg), "%s: %s", chat_snd, clean_body);
        } else {
            snprintf(formatted_msg, sizeof(formatted_msg), "%s", clean_body);
        }
        init_messages[0] = strdup(formatted_msg);
    }

    const char *display_title = (chat_grp && strlen(chat_grp) > 0) ? chat_grp : clean_summary;
    int w = 380;
    int h = calculate_notification_height(display_title, init_messages, init_msgs, init_total, init_reel_text, w);

    int screen_w = DisplayWidth(dpy, screen);
    int x = screen_w - w - 16;
    int y = 45;

    XSetWindowAttributes attrs;
    attrs.override_redirect = True;
    attrs.colormap = colormap;
    attrs.border_pixel = 0;
    attrs.background_pixmap = None;
    attrs.event_mask = ButtonPressMask | ExposureMask | EnterWindowMask | LeaveWindowMask;

    Window win = XCreateWindow(
        dpy, root, x, y, w, h, 0,
        depth, InputOutput, visual,
        CWOverrideRedirect | CWColormap | CWBorderPixel | CWBackPixmap | CWEventMask,
        &attrs
    );

    Atom net_wm_type = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
    Atom net_wm_type_notif = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_NOTIFICATION", False);
    XChangeProperty(dpy, win, net_wm_type, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)&net_wm_type_notif, 1);

    XClassHint class_hint = { "sys-notif", "sys-notif" };
    XSetClassHint(dpy, win, &class_hint);

    Atom net_wm_state = XInternAtom(dpy, "_NET_WM_STATE", False);
    Atom net_wm_state_above = XInternAtom(dpy, "_NET_WM_STATE_ABOVE", False);
    Atom net_wm_state_stays_on_top = XInternAtom(dpy, "_NET_WM_STATE_STAYS_ON_TOP", False);
    Atom state_atoms[2] = { net_wm_state_above, net_wm_state_stays_on_top };
    XChangeProperty(dpy, win, net_wm_state, XA_ATOM, 32, PropModeReplace,
                    (unsigned char *)state_atoms, 2);

    NotificationItem *item = calloc(1, sizeof(NotificationItem));
    item->id = id;
    item->app_name = strdup(app_name ? app_name : "System");
    item->summary = strdup(display_title);
    for (int m = 0; m < init_msgs; m++) {
        item->messages[m] = init_messages[m];
    }
    item->msg_count = init_msgs;
    item->total_msgs = init_total;
    item->reel_count = init_reels;
    item->latest_reel_text = init_reel_text;
    item->icon_name = icon_name ? strdup(icon_name) : NULL;
    item->pixbuf = pb;
    item->icon_surf = pb ? pixbuf_to_surface(pb) : NULL;
    item->is_avatar = is_avatar;
    item->urgency = urgency;
    item->is_transient = is_transient;
    item->thread_id = thread_id ? strdup(thread_id) : NULL;
    item->default_action_key = default_action_key ? strdup(default_action_key) : NULL;
    item->win = win;
    item->width = w;
    item->height = h;
    item->x = x;
    item->y = y;
    item->surface = cairo_xlib_surface_create(dpy, win, visual, w, h);
    item->cr = cairo_create(item->surface);

    item->next = notif_list;
    notif_list = item;

    reposition_notifications();
    render_notification(item);
    cairo_surface_flush(item->surface);
    XFlush(dpy);

    XMapRaised(dpy, win);
    XFlush(dpy);

    /* Play distinct chime: warning sound for critical urgency, message chime otherwise */
    if (item->urgency == 2) {
        play_sound("dialog-warning");
    } else {
        play_sound("message");
    }

    /* Log to persistent history if not marked transient */
    if (!is_transient) {
        const char *log_icon = cached_avatar_path ? cached_avatar_path : (item->icon_name ? item->icon_name : item->app_name);
        char log_sum[512];
        if (chat_snd && strlen(chat_snd) > 0 && chat_grp && g_ascii_strcasecmp(chat_snd, chat_grp) != 0) {
            snprintf(log_sum, sizeof(log_sum), "%s • %s", chat_grp, chat_snd);
        } else {
            snprintf(log_sum, sizeof(log_sum), "%s", item->summary);
        }
        append_history(item->app_name, log_sum, clean_body, log_icon);
    }

    free(chat_grp);
    free(chat_snd);

    int to = timeout_ms > 0 ? timeout_ms : 5000;
    if (item->urgency == 2 && to < 20000) {
        to = 20000;
    }
    item->start_time_us = g_get_monotonic_time();
    item->duration_us = (gint64)to * 1000;
    item->progress = 1.0;
    item->anim_timer_id = g_timeout_add(30, notif_progress_tick, item);

    return id;
}

/* ==========================================================================
 * Native Low-Overhead Battery & Power Monitor
 * Replaces external Bash daemon (0 extra RAM, microsecond direct sysfs read)
 * ========================================================================== */
static char g_bat_path[256] = {0};
static char g_bat_last_status[32] = {0};
static gboolean g_bat_alert_20 = FALSE;
static gboolean g_bat_alert_10 = FALSE;
static gboolean g_bat_alert_5 = FALSE;
static gboolean g_bat_alert_full = FALSE;

static void init_battery_monitor(void) {
    if (access("/sys/class/power_supply/BAT1", F_OK) == 0) {
        snprintf(g_bat_path, sizeof(g_bat_path), "/sys/class/power_supply/BAT1");
    } else if (access("/sys/class/power_supply/BAT0", F_OK) == 0) {
        snprintf(g_bat_path, sizeof(g_bat_path), "/sys/class/power_supply/BAT0");
    } else {
        GDir *dir = g_dir_open("/sys/class/power_supply", 0, NULL);
        if (dir) {
            const char *name;
            while ((name = g_dir_read_name(dir)) != NULL) {
                if (g_str_has_prefix(name, "BAT")) {
                    snprintf(g_bat_path, sizeof(g_bat_path), "/sys/class/power_supply/%s", name);
                    break;
                }
            }
            g_dir_close(dir);
        }
    }

    if (g_bat_path[0] != '\0') {
        char path_st[300];
        snprintf(path_st, sizeof(path_st), "%s/status", g_bat_path);
        FILE *f = fopen(path_st, "r");
        if (f) {
            if (fgets(g_bat_last_status, sizeof(g_bat_last_status), f)) {
                g_strstrip(g_bat_last_status);
            }
            fclose(f);
        }
    }
}

static gboolean battery_monitor_tick(gpointer user_data) {
    (void)user_data;
    if (g_bat_path[0] == '\0') return TRUE;

    char path_cap[300], path_st[300];
    snprintf(path_cap, sizeof(path_cap), "%s/capacity", g_bat_path);
    snprintf(path_st, sizeof(path_st), "%s/status", g_bat_path);

    FILE *f_cap = fopen(path_cap, "r");
    FILE *f_st = fopen(path_st, "r");
    if (!f_cap || !f_st) {
        if (f_cap) fclose(f_cap);
        if (f_st) fclose(f_st);
        return TRUE;
    }

    int capacity = 0;
    if (fscanf(f_cap, "%d", &capacity) != 1) {
        fclose(f_cap); fclose(f_st);
        return TRUE;
    }
    fclose(f_cap);

    char status[32] = {0};
    if (fgets(status, sizeof(status), f_st)) {
        g_strstrip(status);
    }
    fclose(f_st);

    gboolean is_discharging = (g_ascii_strcasecmp(status, "Discharging") == 0);

    /* 1. Charger connected transition */
    if (!is_discharging) {
        if (strlen(g_bat_last_status) > 0 && g_ascii_strcasecmp(g_bat_last_status, "Discharging") == 0) {
            char body[128];
            snprintf(body, sizeof(body), "Battery is now charging (%d%%).", capacity);
            show_notification("Power Manager", "AC Power Connected", body, "battery-charging", NULL, NULL, 5000, 0);
            play_sound("power-plug");
        }
        g_bat_alert_20 = FALSE;
        g_bat_alert_10 = FALSE;
        g_bat_alert_5 = FALSE;

        /* Full charge alert */
        if (capacity >= 100) {
            if (!g_bat_alert_full) {
                show_notification("Power Manager", "Battery Fully Charged",
                                  "Battery is at 100%. You can disconnect your charger.",
                                  "battery-full-charged", NULL, NULL, 6000, 0);
                play_sound("complete");
                g_bat_alert_full = TRUE;
            }
        } else {
            g_bat_alert_full = FALSE;
        }

        snprintf(g_bat_last_status, sizeof(g_bat_last_status), "%s", status);
        return TRUE;
    }

    /* 2. Charger disconnected transition */
    if (strlen(g_bat_last_status) > 0 && g_ascii_strcasecmp(g_bat_last_status, "Discharging") != 0) {
        char body[128];
        snprintf(body, sizeof(body), "Running on battery power (%d%%).", capacity);
        show_notification("Power Manager", "Charger Disconnected", body, "battery-discharging", NULL, NULL, 5000, 0);
        play_sound("power-unplug");
    }

    snprintf(g_bat_last_status, sizeof(g_bat_last_status), "Discharging");
    g_bat_alert_full = FALSE;

    /* 3. Low Battery Threshold Alerts */
    if (capacity <= 5) {
        if (!g_bat_alert_5) {
            GVariantBuilder b;
            g_variant_builder_init(&b, G_VARIANT_TYPE("a{sv}"));
            g_variant_builder_add(&b, "{sv}", "urgency", g_variant_new_byte(2));
            GVariant *hints = g_variant_builder_end(&b);

            char sum[64], bod[128];
            snprintf(sum, sizeof(sum), "EMERGENCY: Battery at %d%%", capacity);
            snprintf(bod, sizeof(bod), "System will shut down imminently! Plug in your charger immediately.");
            show_notification("Power Manager", sum, bod, "battery-empty", hints, NULL, 20000, 0);
            play_sound("alarm-clock-elapsed");
            g_bat_alert_5 = TRUE;
        }
    } else if (capacity <= 10) {
        if (!g_bat_alert_10) {
            GVariantBuilder b;
            g_variant_builder_init(&b, G_VARIANT_TYPE("a{sv}"));
            g_variant_builder_add(&b, "{sv}", "urgency", g_variant_new_byte(2));
            GVariant *hints = g_variant_builder_end(&b);

            char sum[64], bod[128];
            snprintf(sum, sizeof(sum), "Critical Battery Alert (%d%%)", capacity);
            snprintf(bod, sizeof(bod), "Battery level is critical! Please connect your charger to avoid data loss.");
            show_notification("Power Manager", sum, bod, "battery-empty", hints, NULL, 15000, 0);
            play_sound("dialog-warning");
            g_bat_alert_10 = TRUE;
        }
    } else if (capacity <= 20) {
        if (!g_bat_alert_20) {
            char sum[64], bod[128];
            snprintf(sum, sizeof(sum), "Low Battery Warning (%d%%)", capacity);
            snprintf(bod, sizeof(bod), "Battery is running low. Please connect your charger.");
            show_notification("Power Manager", sum, bod, "battery-caution", NULL, NULL, 8000, 0);
            play_sound("dialog-information");
            g_bat_alert_20 = TRUE;
        }
    }

    return TRUE;
}

static void on_upower_changed(GDBusConnection *conn, const gchar *sender_name,
                             const gchar *object_path, const gchar *interface_name,
                             const gchar *signal_name, GVariant *parameters,
                             gpointer user_data) {
    (void)conn; (void)sender_name; (void)object_path; (void)interface_name;
    (void)signal_name; (void)parameters; (void)user_data;
    battery_monitor_tick(NULL);
}

/* -------------------------------------------------------------
 * D-Bus Handler
 * ------------------------------------------------------------- */
static void handle_method_call(GDBusConnection *conn,
                               const gchar *sender,
                               const gchar *object_path,
                               const gchar *interface_name,
                               const gchar *method_name,
                               GVariant *parameters,
                               GDBusMethodInvocation *invocation,
                               gpointer user_data) {
    (void)conn; (void)sender; (void)object_path; (void)interface_name; (void)user_data;

    if (g_strcmp0(method_name, "GetCapabilities") == 0) {
        const gchar *caps[] = {"body", "body-markup", "actions", "icon-static", "sound", NULL};
        g_dbus_method_invocation_return_value(invocation, g_variant_new("(^as)", caps));
    }
    else if (g_strcmp0(method_name, "GetServerInformation") == 0) {
        g_dbus_method_invocation_return_value(invocation,
            g_variant_new("(ssss)", "sys-notif", "System", "1.0", "1.2"));
    }
    else if (g_strcmp0(method_name, "CloseNotification") == 0) {
        guint32 id;
        g_variant_get(parameters, "(u)", &id);
        NotificationItem *cur = notif_list;
        while (cur) {
            if (cur->id == id) {
                notif_timeout_callback(cur);
                break;
            }
            cur = cur->next;
        }
        g_dbus_method_invocation_return_value(invocation, NULL);
    }
    else if (g_strcmp0(method_name, "Notify") == 0) {
        const gchar *app_name = NULL, *app_icon = NULL, *summary = NULL, *body = NULL;
        guint32 replaces_id = 0;
        gint32 expire_timeout = -1;
        GVariant *actions = NULL, *hints = NULL;

        g_variant_get(parameters, "(&su&s&s&s@as@a{sv}i)",
                      &app_name, &replaces_id, &app_icon, &summary, &body,
                      &actions, &hints, &expire_timeout);

        /* Detect if this is an OSD notification (Sound / Volume / Brightness) */
        gboolean is_osd = FALSE;
        gint osd_val = -1;
        const char *osd_type = "volume";
        gboolean is_muted = FALSE;

        if (hints) {
            GVariant *val_v = g_variant_lookup_value(hints, "value", G_VARIANT_TYPE_INT32);
            if (!val_v) val_v = g_variant_lookup_value(hints, "value", G_VARIANT_TYPE_BYTE);
            if (!val_v) val_v = g_variant_lookup_value(hints, "value", G_VARIANT_TYPE_DOUBLE);
            if (val_v) {
                if (g_variant_is_of_type(val_v, G_VARIANT_TYPE_INT32)) osd_val = g_variant_get_int32(val_v);
                else if (g_variant_is_of_type(val_v, G_VARIANT_TYPE_BYTE)) osd_val = g_variant_get_byte(val_v);
                else if (g_variant_is_of_type(val_v, G_VARIANT_TYPE_DOUBLE)) osd_val = (gint)g_variant_get_double(val_v);
                g_variant_unref(val_v);
            }

            GVariant *tag_v = g_variant_lookup_value(hints, "x-dunst-stack-tag", G_VARIANT_TYPE_STRING);
            if (tag_v) {
                const gchar *tag = g_variant_get_string(tag_v, NULL);
                if (g_str_has_prefix(tag, "cvolum") || g_str_has_prefix(tag, "volume")) {
                    is_osd = TRUE;
                    osd_type = "volume";
                } else if (g_str_has_prefix(tag, "cbright") || g_str_has_prefix(tag, "brightness")) {
                    is_osd = TRUE;
                    osd_type = "brightness";
                }
                g_variant_unref(tag_v);
            }
        }

        /* Check summary or app_name prefixes */
        if (!is_osd) {
            if ((app_name && g_ascii_strcasecmp(app_name, "volume") == 0) ||
                g_ascii_strncasecmp(summary, "volume", 6) == 0 ||
                g_ascii_strncasecmp(summary, "volumen", 7) == 0 ||
                g_ascii_strncasecmp(summary, "muted", 5) == 0 ||
                g_ascii_strncasecmp(summary, "unmuted", 7) == 0) {
                is_osd = TRUE;
                osd_type = "volume";
            } else if ((app_name && g_ascii_strcasecmp(app_name, "brightness") == 0) ||
                       g_ascii_strncasecmp(summary, "brightness", 10) == 0) {
                is_osd = TRUE;
                osd_type = "brightness";
            }
        }

        if (is_osd) {
            /* Parse percent from summary if not in hints */
            if (osd_val < 0) {
                const char *p = strchr(summary, ':');
                if (p) {
                    p++;
                    while (*p == ' ') p++;
                    if (strncasecmp(p, "muted", 5) == 0) {
                        is_muted = TRUE;
                        osd_val = 0;
                    } else {
                        osd_val = atoi(p);
                    }
                } else if (strstr(summary, "Muted")) {
                    is_muted = TRUE;
                    osd_val = 0;
                } else if (sscanf(summary, "%*[^0-9]%d", &osd_val) <= 0) {
                    osd_val = 50;
                }
            }
            if (strstr(summary, "Muted") || strstr(body, "Muted")) {
                is_muted = TRUE;
            }

            show_osd(osd_type, osd_val, is_muted, summary);
            g_dbus_method_invocation_return_value(invocation, g_variant_new("(u)", 999999));
        } else {
            /* Standard Notification Card: group seamlessly by conversation or replaces_id */
            detect_web_service((const char **)&app_name, (const char **)&app_icon, summary, body, hints);
            guint id = show_notification(app_name, summary, body, app_icon, hints, actions, expire_timeout, replaces_id);
            g_dbus_method_invocation_return_value(invocation, g_variant_new("(u)", id));
        }

        if (actions) g_variant_unref(actions);
        if (hints) g_variant_unref(hints);
    }
}

static const GDBusInterfaceVTable vtable = {
    handle_method_call, NULL, NULL, {0}
};

/* Handle X11 events via GLib event loop */
static gboolean x11_event_handler(GIOChannel *source, GIOCondition condition, gpointer data) {
    (void)source; (void)condition; (void)data;
    while (XPending(dpy)) {
        XEvent ev;
        XNextEvent(dpy, &ev);

        if (ev.type == EnterNotify) {
            NotificationItem *cur = notif_list;
            while (cur) {
                if (cur->win == ev.xcrossing.window) {
                    cur->is_hovered = TRUE;
                    break;
                }
                cur = cur->next;
            }
        } else if (ev.type == LeaveNotify) {
            NotificationItem *cur = notif_list;
            while (cur) {
                if (cur->win == ev.xcrossing.window) {
                    cur->is_hovered = FALSE;
                    cur->start_time_us = g_get_monotonic_time() - (gint64)((1.0 - cur->progress) * cur->duration_us);
                    break;
                }
                cur = cur->next;
            }
        } else if (ev.type == ButtonPress) {
            NotificationItem *cur = notif_list;
            while (cur) {
                if (cur->win == ev.xbutton.window) {
                    if (ev.xbutton.button == Button1 || ev.xbutton.button == Button2) {
                        /* Left Click or Middle Click: Dismiss silently */
                        if (ev.xbutton.state & ShiftMask) {
                            NotificationItem *it = notif_list;
                            while (it) {
                                clear_conversation_from_history(it->app_name, it->summary);
                                it = it->next;
                            }
                            dismiss_all_notifications();
                        } else {
                            clear_conversation_from_history(cur->app_name, cur->summary);
                            notif_timeout_callback(cur);
                        }
                    } else if (ev.xbutton.button == Button3) {
                        /* Right Click: Focus app/chat, clear conversation from history, and dismiss popup */
                        if (ev.xbutton.state & ShiftMask) {
                            NotificationItem *it = notif_list;
                            while (it) {
                                clear_conversation_from_history(it->app_name, it->summary);
                                it = it->next;
                            }
                            dismiss_all_notifications();
                        } else {
                            if (dbus_conn && cur->id > 0) {
                                const char *act = cur->default_action_key ? cur->default_action_key : "default";
                                g_dbus_connection_emit_signal(
                                    dbus_conn, NULL, "/org/freedesktop/Notifications",
                                    "org.freedesktop.Notifications", "ActionInvoked",
                                    g_variant_new("(us)", cur->id, act), NULL
                                );
                            }
                            const char *last_msg = (cur->msg_count > 0 && cur->messages[cur->msg_count - 1]) ?
                                                   cur->messages[cur->msg_count - 1] : "";
                            activate_app(cur->app_name, cur->summary, last_msg);
                            clear_conversation_from_history(cur->app_name, cur->summary);
                            notif_timeout_callback(cur);
                        }
                    }
                    break;
                }
                cur = cur->next;
            }
        } else if (ev.type == Expose) {
            /* Only redraw on the final expose event in a batch to eliminate redundant draws */
            if (ev.xexpose.count == 0) {
                if (osd.visible && ev.xexpose.window == osd.win) {
                    render_osd();
                } else {
                    NotificationItem *cur = notif_list;
                    while (cur) {
                        if (cur->win == ev.xexpose.window) {
                            render_notification(cur);
                            break;
                        }
                        cur = cur->next;
                    }
                }
            }
        }
    }
    return TRUE;
}

static void on_bus_acquired(GDBusConnection *conn, const gchar *name, gpointer user_data) {
    (void)name; (void)user_data;
    dbus_conn = conn;

    GError *error = NULL;
    GDBusNodeInfo *node_info = g_dbus_node_info_new_for_xml(introspection_xml, &error);
    if (!node_info) {
        fprintf(stderr, "Failed to parse D-Bus XML: %s\n", error ? error->message : "unknown");
        return;
    }

    g_dbus_connection_register_object(
        conn,
        "/org/freedesktop/Notifications",
        node_info->interfaces[0],
        &vtable,
        NULL, NULL, &error
    );

    if (error) {
        fprintf(stderr, "Failed to register D-Bus object: %s\n", error->message);
        g_error_free(error);
    }
    g_dbus_node_info_unref(node_info);
}

static gboolean on_standalone_timeout(gpointer data) {
    g_main_loop_quit((GMainLoop *)data);
    return G_SOURCE_REMOVE;
}

int main(int argc, char *argv[]) {
    setlinebuf(stdout);
    setlinebuf(stderr);
    /* Automatically reap child processes so canberra-gtk-play leaves zero zombies */
    signal(SIGCHLD, SIG_IGN);

    /* Fast CLI: Polybar Badge / Unread Counter */
    if (argc >= 2 && strcmp(argv[1], "--badge") == 0) {
        gboolean dnd = (access("/home/vibecoder/.cache/sys-notif/dnd", F_OK) == 0);
        const char *path = "/home/vibecoder/.cache/sys-notif/history.txt";
        FILE *f = fopen(path, "r");
        int count = 0;
        if (f) {
            char buf[512];
            while (fgets(buf, sizeof(buf), f)) count++;
            fclose(f);
        }
        if (dnd) {
            if (count == 0) {
                printf("%%{F#fab387}󰂛%%{F-}\n");
            } else {
                printf("%%{F#fab387}󰂛%%{F-} %%{F#cdd6f4}%d%%{F-}\n", count);
            }
        } else {
            if (count == 0) {
                printf("%%{F#6c7086}󰂚%%{F-}\n");
            } else {
                printf("%%{F#89b4fa}󱅫%%{F-} %%{F#cdd6f4}%d%%{F-}\n", count);
            }
        }
        return 0;
    }

    /* Fast CLI: Toggle DND */
    if (argc >= 2 && strcmp(argv[1], "--dnd-toggle") == 0) {
        toggle_dnd();
        return 0;
    }

    /* Fast CLI: Clear History */
    if (argc >= 2 && strcmp(argv[1], "--clear") == 0) {
        unlink("/home/vibecoder/.cache/sys-notif/history.txt");
        update_polybar_notif_badge();
        printf("Notification history cleared.\n");
        return 0;
    }

    /* Fast CLI: Open History Menu */
    if (argc >= 2 && strcmp(argv[1], "--history") == 0) {
        execl("/home/vibecoder/.local/bin/sys-notif-menu", "sys-notif-menu", NULL);
        return 0;
    }

    /* Fast CLI Client: Send D-Bus message to the running daemon and exit in 2ms */
    if (argc >= 4 && strcmp(argv[1], "--osd") == 0) {
        const char *type = argv[2];
        int val = atoi(argv[3]);
        const char *extra = (argc >= 5) ? argv[4] : "";

        GError *err = NULL;
        GDBusConnection *conn = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, &err);
        if (conn) {
            GVariantBuilder hints_builder;
            g_variant_builder_init(&hints_builder, G_VARIANT_TYPE("a{sv}"));
            g_variant_builder_add(&hints_builder, "{sv}", "value", g_variant_new_int32(val));
            const char *stack_tag = (strcmp(type, "brightness") == 0) ? "cbright" : "cvolum";
            g_variant_builder_add(&hints_builder, "{sv}", "x-dunst-stack-tag", g_variant_new_string(stack_tag));

            char cap_type[32];
            snprintf(cap_type, sizeof(cap_type), "%s", type);
            if (cap_type[0] >= 'a' && cap_type[0] <= 'z') cap_type[0] -= 32;

            char summary[64];
            if (strcmp(extra, "muted") == 0) {
                snprintf(summary, sizeof(summary), "%s: Muted", cap_type);
            } else {
                snprintf(summary, sizeof(summary), "%s: %d%%", cap_type, val);
            }

            g_dbus_connection_call_sync(
                conn,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                "Notify",
                g_variant_new("(susssasa{sv}i)",
                              type, 999999, "", summary, "",
                              NULL, &hints_builder, 1200),
                NULL,
                G_DBUS_CALL_FLAGS_NONE,
                200, /* 200ms timeout */
                NULL,
                NULL
            );
            g_object_unref(conn);
            return 0;
        }
    }

    dpy = XOpenDisplay(NULL);
    if (!dpy) {
        fprintf(stderr, "Cannot open X display\n");
        return 1;
    }
    screen = DefaultScreen(dpy);
    root = RootWindow(dpy, screen);

    init_visual();
    init_fonts();

    /* Standalone fallback if daemon was not active */
    if (argc >= 4 && strcmp(argv[1], "--osd") == 0) {
        const char *type = argv[2];
        int val = atoi(argv[3]);
        gboolean muted = (argc >= 5 && strcmp(argv[4], "muted") == 0);
        show_osd(type, val, muted, NULL);

        GMainLoop *loop = g_main_loop_new(NULL, FALSE);
        g_timeout_add(1300, on_standalone_timeout, loop);
        g_main_loop_run(loop);
        XCloseDisplay(dpy);
        return 0;
    }

    /* Fast single-instance check for daemon mode */
    const char *lock_file = "/tmp/.sys_notif_daemon.pid";
    FILE *lf = fopen(lock_file, "r");
    if (lf) {
        pid_t existing_pid = 0;
        if (fscanf(lf, "%d", &existing_pid) == 1 && existing_pid > 0) {
            if (kill(existing_pid, 0) == 0 && existing_pid != getpid()) {
                fprintf(stderr, "sys-notif: another daemon instance is already running (PID %d). Exiting.\n", existing_pid);
                fclose(lf);
                XCloseDisplay(dpy);
                return 0;
            }
        }
        fclose(lf);
    }
    lf = fopen(lock_file, "w");
    if (lf) {
        fprintf(lf, "%d\n", getpid());
        fclose(lf);
    }

    GMainLoop *loop = g_main_loop_new(NULL, FALSE);

    /* Hook X11 file descriptor into GLib main loop */
    int x11_fd = ConnectionNumber(dpy);
    GIOChannel *x11_chan = g_io_channel_unix_new(x11_fd);
    g_io_add_watch(x11_chan, G_IO_IN | G_IO_HUP | G_IO_ERR, x11_event_handler, NULL);

    /* Initialize native battery & power monitor */
    init_battery_monitor();
    g_timeout_add_seconds(15, battery_monitor_tick, NULL);

    /* Hook into UPower system D-Bus signals for instant 0ms charger plug/unplug events */
    GError *s_err = NULL;
    GDBusConnection *sys_bus = g_bus_get_sync(G_BUS_TYPE_SYSTEM, NULL, &s_err);
    if (sys_bus) {
        g_dbus_connection_signal_subscribe(
            sys_bus,
            "org.freedesktop.UPower",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            NULL,
            NULL,
            G_DBUS_SIGNAL_FLAGS_NONE,
            on_upower_changed,
            NULL,
            NULL
        );
    } else if (s_err) {
        g_error_free(s_err);
    }

    /* Acquire org.freedesktop.Notifications name on D-Bus session bus */
    g_bus_own_name(
        G_BUS_TYPE_SESSION,
        "org.freedesktop.Notifications",
        G_BUS_NAME_OWNER_FLAGS_REPLACE,
        on_bus_acquired,
        NULL,
        NULL,
        G_DBUS_SIGNAL_FLAGS_NONE,
        NULL
    );

    printf("sys-notif v1.0 daemon running (X11, D-Bus & Power Monitor connected)\n");
    g_main_loop_run(loop);

    XCloseDisplay(dpy);
    unlink(lock_file);
    return 0;
}
