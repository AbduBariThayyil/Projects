#define _GNU_SOURCE
#include <gtk/gtk.h>
#include <gdk/gdk.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <regex.h>
#include <math.h>

#define HISTORY_FILE "/home/vibecoder/.cache/sys-notif/history.txt"
#define AVATAR_DIR   "/home/vibecoder/.cache/sys-notif/avatars"

typedef struct {
    char *time;
    char *sender;
    char *body;
} MessageItem;

typedef struct {
    char *app;
    char *base_name;
    char *icon_str;
    GList *messages;     /* List of MessageItem* */
    int msg_count;
    GtkWidget *card_widget;
    GtkWidget *revealer;
    GtkWidget *toggle_btn;
    gboolean expanded;
} ConversationGroup;

static GList *group_list = NULL;
static GtkWidget *main_window = NULL;
static GtkWidget *cards_box = NULL;
static GtkWidget *unread_badge = NULL;

/* --------------------------------------------------------------------------
 * CSS Styling (Catppuccin Mocha)
 * -------------------------------------------------------------------------- */
static const char *STYLE_CSS =
"window.center-modal {\n"
"    background-color: rgba(30, 30, 46, 0.95);\n"
"    border: 1.5px solid rgba(137, 180, 250, 0.6);\n"
"    border-radius: 16px;\n"
"}\n"
"\n"
".header-bar {\n"
"    padding: 14px 18px 10px 18px;\n"
"    border-bottom: 1px solid rgba(49, 50, 68, 0.7);\n"
"}\n"
"\n"
".header-title {\n"
"    font-family: 'JetBrainsMono Nerd Font';\n"
"    font-size: 13pt;\n"
"    font-weight: bold;\n"
"    color: #cdd6f4;\n"
"}\n"
"\n"
".header-badge {\n"
"    background-color: rgba(250, 179, 135, 0.22);\n"
"    color: #fab387;\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 8.5pt;\n"
"    font-weight: bold;\n"
"    padding: 2px 8px;\n"
"    border-radius: 10px;\n"
"}\n"
"\n"
".btn-clear {\n"
"    background-color: rgba(243, 139, 168, 0.18);\n"
"    color: #f38ba8;\n"
"    font-family: 'JetBrainsMono Nerd Font';\n"
"    font-size: 9pt;\n"
"    font-weight: bold;\n"
"    padding: 4px 12px;\n"
"    border-radius: 8px;\n"
"    border: 1px solid rgba(243, 139, 168, 0.4);\n"
"}\n"
".btn-clear:hover {\n"
"    background-color: rgba(243, 139, 168, 0.35);\n"
"    color: #ffffff;\n"
"}\n"
"\n"
".btn-close {\n"
"    background-color: transparent;\n"
"    color: #a6adc8;\n"
"    font-size: 11pt;\n"
"    font-weight: bold;\n"
"    padding: 4px 8px;\n"
"    border-radius: 6px;\n"
"    border: none;\n"
"}\n"
".btn-close:hover {\n"
"    background-color: rgba(243, 139, 168, 0.25);\n"
"    color: #f38ba8;\n"
"}\n"
"\n"
".cards-container {\n"
"    padding: 12px 16px;\n"
"}\n"
"\n"
".notif-card {\n"
"    background-color: rgba(24, 24, 37, 0.75);\n"
"    border: 1px solid rgba(49, 50, 68, 0.65);\n"
"    border-radius: 10px;\n"
"    padding: 10px 14px;\n"
"    margin-bottom: 8px;\n"
"    transition: all 120ms ease;\n"
"}\n"
".notif-card:hover {\n"
"    background-color: rgba(49, 50, 68, 0.6);\n"
"    border-color: rgba(137, 180, 250, 0.5);\n"
"}\n"
"\n"
".card-header {\n"
"    margin-bottom: 6px;\n"
"}\n"
"\n"
".tag-pill {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 8pt;\n"
"    font-weight: bold;\n"
"    padding: 1px 6px;\n"
"    border-radius: 6px;\n"
"    margin-right: 6px;\n"
"}\n"
".tag-whatsapp  { background-color: rgba(166, 227, 161, 0.2); color: #a6e3a1; }\n"
".tag-instagram { background-color: rgba(245, 194, 231, 0.2); color: #f5c2e7; }\n"
".tag-discord   { background-color: rgba(180, 190, 254, 0.2); color: #b4befe; }\n"
".tag-power     { background-color: rgba(250, 179, 135, 0.2); color: #fab387; }\n"
".tag-default   { background-color: rgba(137, 180, 250, 0.2); color: #89b4fa; }\n"
"\n"
".card-title {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 10pt;\n"
"    font-weight: bold;\n"
"    color: #cdd6f4;\n"
"}\n"
"\n"
".card-time {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 8pt;\n"
"    color: #6c7086;\n"
"}\n"
"\n"
".msg-line {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 9pt;\n"
"    color: #cdd6f4;\n"
"    margin-top: 3px;\n"
"}\n"
"\n"
".msg-sender {\n"
"    color: #89b4fa;\n"
"    font-weight: bold;\n"
"}\n"
"\n"
".msg-subtext {\n"
"    color: #a6adc8;\n"
"}\n"
"\n"
".btn-dismiss-card {\n"
"    background-color: transparent;\n"
"    color: #6c7086;\n"
"    font-size: 9pt;\n"
"    padding: 2px 6px;\n"
"    border-radius: 4px;\n"
"    border: none;\n"
"}\n"
".btn-dismiss-card:hover {\n"
"    color: #f38ba8;\n"
"    background-color: rgba(243, 139, 168, 0.2);\n"
"}\n"
"\n"
".btn-expand {\n"
"    background-color: rgba(49, 50, 68, 0.4);\n"
"    color: #fab387;\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 8.5pt;\n"
"    font-weight: bold;\n"
"    padding: 3px 8px;\n"
"    border-radius: 6px;\n"
"    border: none;\n"
"    margin: 4px 0px;\n"
"}\n"
".btn-expand:hover {\n"
"    background-color: rgba(250, 179, 135, 0.2);\n"
"}\n"
"\n"
".empty-state {\n"
"    padding: 40px 20px;\n"
"}\n"
".empty-icon {\n"
"    font-family: 'JetBrainsMono Nerd Font';\n"
"    font-size: 36pt;\n"
"    color: #6c7086;\n"
"}\n"
".empty-label {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 11pt;\n"
"    font-weight: bold;\n"
"    color: #cdd6f4;\n"
"    margin-top: 8px;\n"
"}\n"
".empty-sub {\n"
"    font-family: 'JetBrains Mono';\n"
"    font-size: 9pt;\n"
"    color: #6c7086;\n"
"}\n";

/* --------------------------------------------------------------------------
 * Normalization & Conversation Group Parsing
 * -------------------------------------------------------------------------- */
static char *normalize_app_name(const char *app_str) {
    if (!app_str) return strdup("System");
    char *low = g_ascii_strdown(app_str, -1);
    char *res = NULL;
    if (strstr(low, "whatsapp")) res = strdup("WhatsApp");
    else if (strstr(low, "instagram")) res = strdup("Instagram");
    else if (strstr(low, "discord") || strstr(low, "vesktop")) res = strdup("Discord");
    else if (strstr(low, "telegram")) res = strdup("Telegram");
    else if (strstr(low, "power") || strstr(low, "battery")) res = strdup("Power Manager");
    else res = strdup(app_str);
    g_free(low);
    return res;
}

static void extract_conversation_key(const char *norm_app, const char *sum_str, const char *bod_str,
                                     char **out_group, char **out_sender, char **out_body) {
    if (g_ascii_strcasecmp(norm_app, "Power Manager") == 0) {
        *out_group = strdup("Battery & Power Alerts");
        *out_sender = strdup("");
        *out_body = (bod_str && strlen(bod_str) > 0) ? g_strdup_printf("%s: %s", sum_str, bod_str) : strdup(sum_str);
        return;
    }

    const char *sum = sum_str ? sum_str : "";
    const char *bod = bod_str ? bod_str : "";

    /* Pattern: "Group • Sender" */
    const char *bullet = strstr(sum, " • ");
    if (bullet) {
        int grp_len = (int)(bullet - sum);
        char *grp = g_strndup(sum, grp_len);
        g_strstrip(grp);
        char *snd = strdup(bullet + strlen(" • "));
        g_strstrip(snd);

        /* Auto-heal corrupted legacy history entry where group had ": <Message>" and sender was generic app */
        if (g_ascii_strcasecmp(snd, norm_app) == 0 && strchr(grp, ':')) {
            const char *col = strchr(grp, ':');
            if (col && (col - grp) >= 2) {
                char *actual_grp = g_strndup(grp, (int)(col - grp));
                g_strstrip(actual_grp);
                char *actual_msg = strdup(col + 1);
                g_strstrip(actual_msg);

                *out_group = actual_grp;
                *out_sender = strdup(bod); /* bod contained the sender */
                *out_body = actual_msg;    /* actual message was inside group */
                free(grp);
                free(snd);
                return;
            }
        }

        *out_group = grp;
        *out_sender = snd;
        /* Strip sender prefix if body already has "Sender: " */
        char pfx[128];
        snprintf(pfx, sizeof(pfx), "%s: ", snd);
        if (g_str_has_prefix(bod, pfx)) {
            *out_body = strdup(bod + strlen(pfx));
        } else {
            *out_body = strdup(bod);
        }
        return;
    }

    /* Pattern: "<Sender> to <Group>: <Message>" in bod */
    const char *to_in_bod = strcasestr(bod, " to ");
    if (to_in_bod && (to_in_bod - bod) >= 2) {
        const char *grp_start = to_in_bod + 4;
        while (*grp_start == ' ') grp_start++;
        const char *col = strchr(grp_start, ':');
        if (col && (col - grp_start) >= 2) {
            char *snd = g_strndup(bod, (int)(to_in_bod - bod));
            g_strstrip(snd);
            char *grp = g_strndup(grp_start, (int)(col - grp_start));
            g_strstrip(grp);
            int glen = (int)strlen(grp);
            while (glen > 0 && (grp[glen-1] == '.' || grp[glen-1] == ':' || grp[glen-1] == ',')) {
                grp[--glen] = '\0';
            }
            const char *msg = col + 1;
            while (*msg == ' ') msg++;
            *out_group = grp;
            *out_sender = snd;
            *out_body = strdup(msg);
            return;
        }
    }

    /* Pattern: "Sender to Group" in summary */
    const char *to_kw = strcasestr(sum, " to ");
    if (to_kw && (to_kw - sum) >= 2) {
        char *snd = g_strndup(sum, (int)(to_kw - sum));
        g_strstrip(snd);
        char *grp = strdup(to_kw + 4);
        g_strstrip(grp);
        int glen = (int)strlen(grp);
        while (glen > 0 && (grp[glen-1] == '.' || grp[glen-1] == ':' || grp[glen-1] == ',')) {
            grp[--glen] = '\0';
        }
        *out_group = grp;
        *out_sender = snd;
        *out_body = strdup(bod);
        return;
    }

    /* Pattern: "Sent a ... to Group" in body */
    if (to_in_bod && (to_in_bod - bod) >= 3) {
        const char *grp_start = to_in_bod + 4;
        while (*grp_start == ' ') grp_start++;
        if (strlen(grp_start) > 0 && strcasecmp(grp_start, "your group") != 0 && strcasecmp(grp_start, "the group") != 0) {
            char *grp = strdup(grp_start);
            int glen = (int)strlen(grp);
            while (glen > 0 && (grp[glen-1] == '.' || grp[glen-1] == ':' || grp[glen-1] == ',')) {
                grp[--glen] = '\0';
            }
            *out_group = grp;
            *out_sender = strdup(sum);
            *out_body = g_strndup(bod, (int)(to_in_bod - bod));
            g_strstrip(*out_body);
            return;
        }
    }

    /* Pattern: "From •User•" or "From User" (e.g. Instagram DMs) */
    if ((g_str_has_prefix(bod, "From ") || g_str_has_prefix(bod, "from ")) &&
        (strlen(sum) == 0 || g_ascii_strcasecmp(sum, norm_app) == 0)) {
        const char *p = bod + 5;
        while (*p == ' ' || *p == '\t') p++;
        const char *b_start = strstr(p, "•");
        char sender[64] = {0};
        if (b_start) {
            const char *u = b_start + strlen("•");
            while (*u == ' ') u++;
            const char *b_end = strstr(u, "•");
            if (b_end && (b_end - u) > 0 && (b_end - u) < 60) {
                snprintf(sender, sizeof(sender), "%.*s", (int)(b_end - u), u);
                g_strstrip(sender);
            }
        }
        if (strlen(sender) == 0) {
            const char *col = strchr(p, ':');
            if (col && (col - p) < 60) {
                snprintf(sender, sizeof(sender), "%.*s", (int)(col - p), p);
            } else {
                snprintf(sender, sizeof(sender), "%s", p);
            }
            g_strstrip(sender);
        }
        if (strlen(sender) > 0) {
            *out_group = strdup(sender);
            *out_sender = strdup(sender);
            const char *col = strchr(bod, ':');
            if (col) {
                *out_body = strdup(col + 1);
                g_strstrip(*out_body);
            } else {
                *out_body = strdup("Sent a message");
            }
            return;
        }
    }

    /* Fallback: single chat */
    *out_group = strdup(sum);
    *out_sender = strdup("");
    *out_body = strdup(bod);

    /* If sender is empty, check if body begins with "Sender: Message" */
    const char *colon = strstr(bod, ": ");
    if (colon && (colon - bod) >= 2 && (colon - bod) < 40) {
        char *snd = g_strndup(bod, (int)(colon - bod));
        g_strstrip(snd);
        if (g_ascii_strcasecmp(snd, norm_app) != 0 && g_ascii_strcasecmp(snd, *out_group) != 0) {
            free(*out_sender);
            *out_sender = snd;
            free(*out_body);
            *out_body = strdup(colon + 2);
        } else {
            free(snd);
        }
    }
}

static const char *clean_message_body_sender_prefix(const char *body, const char *sender) {
    if (!body) return "";
    if (!sender || strlen(sender) == 0) return body;
    int s_len = (int)strlen(sender);
    if (g_ascii_strncasecmp(body, sender, s_len) == 0) {
        const char *p = body + s_len;
        if (*p == ':' || *p == ' ') {
            if (*p == ':') p++;
            while (*p == ' ') p++;
            return p;
        }
    }
    return body;
}

/* --------------------------------------------------------------------------
 * Avatar / Icon Loader with Circular Cropping
 * -------------------------------------------------------------------------- */
static GdkPixbuf *pixbuf_round_crop(GdkPixbuf *src, int size) {
    if (!src) return NULL;
    cairo_surface_t *surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
    cairo_t *cr = cairo_create(surf);

    double r = size / 2.0;
    cairo_arc(cr, r, r, r - 0.5, 0, 2 * M_PI);
    cairo_clip(cr);

    GdkPixbuf *scaled = gdk_pixbuf_scale_simple(src, size, size, GDK_INTERP_BILINEAR);
    gdk_cairo_set_source_pixbuf(cr, scaled, 0, 0);
    cairo_paint(cr);
    g_object_unref(scaled);

    /* Antialiased border ring */
    cairo_reset_clip(cr);
    cairo_arc(cr, r, r, r - 0.75, 0, 2 * M_PI);
    cairo_set_source_rgba(cr, 137.0/255.0, 180.0/255.0, 250.0/255.0, 0.45);
    cairo_set_line_width(cr, 1.2);
    cairo_stroke(cr);

    GdkPixbuf *res = gdk_pixbuf_get_from_surface(surf, 0, 0, size, size);
    cairo_destroy(cr);
    cairo_surface_destroy(surf);
    return res;
}

static GdkPixbuf *create_fallback_badge(const char *app, const char *title, int size) {
    cairo_surface_t *surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
    cairo_t *cr = cairo_create(surf);

    double r = size / 2.0;
    cairo_arc(cr, r, r, r, 0, 2 * M_PI);

    char *low = g_ascii_strdown(app ? app : "", -1);
    if (strstr(low, "whatsapp")) {
        cairo_set_source_rgb(cr, 166.0/255.0, 227.0/255.0, 161.0/255.0);
    } else if (strstr(low, "instagram")) {
        cairo_set_source_rgb(cr, 245.0/255.0, 194.0/255.0, 231.0/255.0);
    } else if (strstr(low, "discord")) {
        cairo_set_source_rgb(cr, 180.0/255.0, 190.0/255.0, 254.0/255.0);
    } else if (strstr(low, "power")) {
        cairo_set_source_rgb(cr, 250.0/255.0, 179.0/255.0, 135.0/255.0);
    } else {
        cairo_set_source_rgb(cr, 137.0/255.0, 180.0/255.0, 250.0/255.0);
    }
    g_free(low);

    cairo_fill_preserve(cr);
    cairo_set_source_rgba(cr, 24.0/255.0, 24.0/255.0, 37.0/255.0, 0.4);
    cairo_set_line_width(cr, 1.5);
    cairo_stroke(cr);

    /* Draw initial letter */
    char letter[2] = {0};
    if (title && strlen(title) > 0) letter[0] = (char)g_ascii_toupper(title[0]);
    else letter[0] = (char)g_ascii_toupper(app ? app[0] : 'N');

    cairo_select_font_face(cr, "JetBrains Mono", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD);
    cairo_set_font_size(cr, size * 0.48);
    cairo_set_source_rgb(cr, 24.0/255.0, 24.0/255.0, 37.0/255.0);

    cairo_text_extents_t ext;
    cairo_text_extents(cr, letter, &ext);
    cairo_move_to(cr, r - ext.width/2.0 - ext.x_bearing, r - ext.height/2.0 - ext.y_bearing);
    cairo_show_text(cr, letter);

    GdkPixbuf *res = gdk_pixbuf_get_from_surface(surf, 0, 0, size, size);
    cairo_destroy(cr);
    cairo_surface_destroy(surf);
    return res;
}

static GdkPixbuf *load_avatar_or_icon(const char *app, const char *group, const char *sender, const char *icon_hint, int size) {
    const char *a = app ? app : "app";
    char avatar_path[512];
    gboolean is_group = (group && sender && strlen(group) > 0 && strlen(sender) > 0 &&
                         g_ascii_strcasecmp(group, sender) != 0);

    /* 1. For a Group Chat, prioritize the Group Icon */
    if (is_group) {
        char grp_name[128] = {0};
        int pos = 0;
        for (int i = 0; a[i] && pos < 15; i++) {
            if (g_ascii_isalnum(a[i])) grp_name[pos++] = (char)g_ascii_tolower(a[i]);
        }
        grp_name[pos++] = '_';
        for (int i = 0; group[i] && pos < 60; i++) {
            if (g_ascii_isalnum(group[i])) grp_name[pos++] = (char)g_ascii_tolower(group[i]);
            else grp_name[pos++] = '_';
        }
        grp_name[pos] = '\0';

        snprintf(avatar_path, sizeof(avatar_path), "%s/%s.png", AVATAR_DIR, grp_name);
        if (access(avatar_path, R_OK) == 0) {
            GdkPixbuf *raw = gdk_pixbuf_new_from_file(avatar_path, NULL);
            if (raw) {
                GdkPixbuf *res = pixbuf_round_crop(raw, size);
                g_object_unref(raw);
                return res;
            }
        }
        /* Group icon not found: fallback to clean badge, never use sender's personal photo */
        return create_fallback_badge(app, group, size);
    }

    /* 2. For Direct Messages / 1-on-1 contact, check contact avatar */
    const char *target = (sender && strlen(sender) > 0) ? sender : group;
    if (target && strlen(target) > 0) {
        char clean_name[128] = {0};
        int pos = 0;
        for (int i = 0; a[i] && pos < 15; i++) {
            if (g_ascii_isalnum(a[i])) clean_name[pos++] = (char)g_ascii_tolower(a[i]);
        }
        clean_name[pos++] = '_';
        for (int i = 0; target[i] && pos < 60; i++) {
            if (g_ascii_isalnum(target[i])) clean_name[pos++] = (char)g_ascii_tolower(target[i]);
            else clean_name[pos++] = '_';
        }
        clean_name[pos] = '\0';

        snprintf(avatar_path, sizeof(avatar_path), "%s/%s.png", AVATAR_DIR, clean_name);
        if (access(avatar_path, R_OK) == 0) {
            GdkPixbuf *raw = gdk_pixbuf_new_from_file(avatar_path, NULL);
            if (raw) {
                GdkPixbuf *res = pixbuf_round_crop(raw, size);
                g_object_unref(raw);
                return res;
            }
        }
    }

    /* Check icon hint if it is a real file path */
    if (icon_hint && icon_hint[0] == '/' && access(icon_hint, R_OK) == 0) {
        GdkPixbuf *raw = gdk_pixbuf_new_from_file(icon_hint, NULL);
        if (raw) {
            GdkPixbuf *res = pixbuf_round_crop(raw, size);
            g_object_unref(raw);
            return res;
        }
    }

    /* Fallback: load standard system icon */
    GtkIconTheme *theme = gtk_icon_theme_get_default();
    const char *icon_name = "preferences-desktop-notification-bell";
    char *low = g_ascii_strdown(app ? app : "", -1);
    if (strstr(low, "whatsapp")) icon_name = "whatsapp-desktop";
    else if (strstr(low, "instagram")) icon_name = "instagram";
    else if (strstr(low, "discord")) icon_name = "discord";
    else if (strstr(low, "power") || strstr(low, "battery")) icon_name = "battery-charging";
    g_free(low);

    if (gtk_icon_theme_has_icon(theme, icon_name)) {
        GdkPixbuf *raw = gtk_icon_theme_load_icon(theme, icon_name, size, GTK_ICON_LOOKUP_FORCE_SIZE, NULL);
        if (raw) {
            GdkPixbuf *res = pixbuf_round_crop(raw, size);
            g_object_unref(raw);
            return res;
        }
    }

    /* Last resort fallback: elegant circular badge with initial */
    return create_fallback_badge(app, group, size);
}

/* --------------------------------------------------------------------------
 * History File Management
 * -------------------------------------------------------------------------- */
static void remove_group_from_history(const char *target_app, const char *target_group) {
    if (access(HISTORY_FILE, F_OK) != 0) return;

    FILE *f = fopen(HISTORY_FILE, "r");
    if (!f) return;

    char *lines[1024];
    int count = 0;
    char buf[1024];

    while (fgets(buf, sizeof(buf), f) && count < 1024) {
        char *line = strdup(buf);
        char *p = strdup(buf);
        char *p_app = NULL, *p_sum = NULL, *p_bod = NULL;

        char *token = strtok(p, "|");
        int idx = 0;
        while (token) {
            if (idx == 1) p_app = token;
            else if (idx == 2) p_sum = token;
            else if (idx == 3) p_bod = token;
            token = strtok(NULL, "|");
            idx++;
        }

        if (p_app && p_sum) {
            char *norm_app = normalize_app_name(p_app);
            char *grp = NULL, *snd = NULL, *bod = NULL;
            extract_conversation_key(norm_app, p_sum, p_bod, &grp, &snd, &bod);

            if (g_ascii_strcasecmp(norm_app, target_app) == 0 &&
                g_ascii_strcasecmp(grp, target_group) == 0) {
                free(line);
                free(p);
                free(norm_app);
                free(grp); free(snd); free(bod);
                continue;
            }
            free(norm_app);
            free(grp); free(snd); free(bod);
        }

        lines[count++] = line;
        free(p);
    }
    fclose(f);

    f = fopen(HISTORY_FILE, "w");
    if (f) {
        for (int i = 0; i < count; i++) {
            fputs(lines[i], f);
            free(lines[i]);
        }
        fclose(f);
    }
}

static void activate_conversation(const char *app, const char *group, GList *messages) {
    /* Copy messages to clipboard */
    GString *text = g_string_new("");
    for (GList *l = messages; l != NULL; l = l->next) {
        MessageItem *m = (MessageItem *)l->data;
        if (m->sender && strlen(m->sender) > 0) {
            g_string_append_printf(text, "%s: %s\n", m->sender, m->body);
        } else {
            g_string_append_printf(text, "%s\n", m->body);
        }
    }

    GtkClipboard *cb = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
    gtk_clipboard_set_text(cb, text->str, -1);
    g_string_free(text, TRUE);

    /* Open links if found in latest message */
    if (messages) {
        MessageItem *last = (MessageItem *)g_list_last(messages)->data;
        if (last && last->body && strstr(last->body, "http")) {
            const char *p = strstr(last->body, "http");
            if (!strstr(p, "web.whatsapp.com") && !strstr(p, "instagram.com")) {
                char url[512] = {0};
                int i = 0;
                while (p[i] && p[i] != ' ' && p[i] != '\n' && p[i] != '\t' && p[i] != '"' && p[i] != '\'' && i < 510) {
                    url[i] = p[i];
                    i++;
                }
                url[i] = '\0';
                if (fork() == 0) {
                    setsid();
                    execlp("xdg-open", "xdg-open", url, NULL);
                    _exit(0);
                }
            }
        }
    }

    /* Focus app window via sys-control */
    if (fork() == 0) {
        setsid();
        execlp("/home/vibecoder/.local/bin/sys-control", "sys-control", "--activate", app, group, NULL);
        _exit(0);
    }

    remove_group_from_history(app, group);
    gtk_main_quit();
}

/* --------------------------------------------------------------------------
 * Card Dismiss Callback
 * -------------------------------------------------------------------------- */
static void dismiss_card(ConversationGroup *cg) {
    remove_group_from_history(cg->app, cg->base_name);
    group_list = g_list_remove(group_list, cg);

    if (cg->card_widget) {
        gtk_widget_destroy(cg->card_widget);
        cg->card_widget = NULL;
    }

    /* Update unread badge */
    int total_unread = g_list_length(group_list);
    if (total_unread > 0) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%d unread", total_unread);
        gtk_label_set_text(GTK_LABEL(unread_badge), buf);
    } else {
        gtk_widget_hide(unread_badge);

        /* Show empty state */
        GtkWidget *empty_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
        gtk_style_context_add_class(gtk_widget_get_style_context(empty_box), "empty-state");
        gtk_widget_set_halign(empty_box, GTK_ALIGN_CENTER);
        gtk_widget_set_valign(empty_box, GTK_ALIGN_CENTER);

        GtkWidget *lbl_icon = gtk_label_new("󰂛");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_icon), "empty-icon");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_icon, FALSE, FALSE, 0);

        GtkWidget *lbl_txt = gtk_label_new("No missed notifications");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_txt), "empty-label");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_txt, FALSE, FALSE, 0);

        GtkWidget *lbl_sub = gtk_label_new("You're all caught up!");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_sub), "empty-sub");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_sub, FALSE, FALSE, 0);

        gtk_box_pack_start(GTK_BOX(cards_box), empty_box, TRUE, TRUE, 20);
        gtk_widget_show_all(empty_box);
    }
}

/* --------------------------------------------------------------------------
 * Toggle Expand / Collapse (>5 messages)
 * -------------------------------------------------------------------------- */
static void toggle_expand(GtkButton *btn, ConversationGroup *cg) {
    (void)btn;
    cg->expanded = !cg->expanded;
    gtk_revealer_set_reveal_child(GTK_REVEALER(cg->revealer), cg->expanded);

    if (cg->expanded) {
        gtk_button_set_label(GTK_BUTTON(cg->toggle_btn), "▲ Hide earlier messages");
    } else {
        char buf[64];
        snprintf(buf, sizeof(buf), "▼ Show %d earlier messages", cg->msg_count - 5);
        gtk_button_set_label(GTK_BUTTON(cg->toggle_btn), buf);
    }
}

/* --------------------------------------------------------------------------
 * Card Mouse Event Handler
 * -------------------------------------------------------------------------- */
static gboolean on_card_button_press(GtkWidget *widget, GdkEventButton *event, ConversationGroup *cg) {
    (void)widget;
    if (event->type == GDK_BUTTON_PRESS) {
        if (event->button == GDK_BUTTON_PRIMARY || event->button == GDK_BUTTON_MIDDLE) {
            /* Left Click or Middle Click: Dismiss card silently */
            dismiss_card(cg);
            return TRUE;
        } else if (event->button == GDK_BUTTON_SECONDARY) {
            /* Right Click: Focus app & activate conversation */
            activate_conversation(cg->app, cg->base_name, cg->messages);
            return TRUE;
        }
    }
    return FALSE;
}

static void on_dismiss_btn_clicked(GtkButton *btn, ConversationGroup *cg) {
    (void)btn;
    dismiss_card(cg);
}

static void on_clear_all_clicked(GtkButton *btn, gpointer data) {
    (void)btn; (void)data;
    if (fork() == 0) {
        setsid();
        execlp("/home/vibecoder/.local/bin/sys-notif", "sys-notif", "--clear", NULL);
        _exit(0);
    }
    gtk_main_quit();
}

static gboolean on_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    (void)widget; (void)user_data;
    if (event->keyval == GDK_KEY_Escape) {
        gtk_main_quit();
        return TRUE;
    }
    return FALSE;
}

static char *safe_markup_escape(const char *str) {
    if (!str) return g_strdup("");
    char *valid = g_utf8_make_valid(str, -1);
    char *escaped = g_markup_escape_text(valid, -1);
    g_free(valid);
    return escaped;
}

/* --------------------------------------------------------------------------
 * Parse History & Build Groups
 * -------------------------------------------------------------------------- */
static void load_history_groups(void) {
    if (access(HISTORY_FILE, F_OK) != 0) return;

    FILE *f = fopen(HISTORY_FILE, "r");
    if (!f) return;

    char buf[1024];
    while (fgets(buf, sizeof(buf), f)) {
        char *line = g_strdup(buf);
        g_strstrip(line);
        if (strlen(line) == 0) { g_free(line); continue; }

        char *parts[5] = {0};
        char *token = strtok(line, "|");
        int idx = 0;
        while (token && idx < 5) {
            parts[idx++] = token;
            token = strtok(NULL, "|");
        }

        if (idx < 3) { g_free(line); continue; }

        const char *time_str = parts[0];
        const char *app_str  = parts[1];
        const char *sum_str  = parts[2];
        const char *bod_str  = (idx > 3) ? parts[3] : "";
        const char *icon_str = (idx > 4) ? parts[4] : "";

        /* Drop internal confirmation spam */
        char *low_sum = g_ascii_strdown(sum_str, -1);
        char *low_bod = g_ascii_strdown(bod_str, -1);
        if (strstr(low_sum, "history cleared") || strstr(low_sum, "notification dismissed") ||
            strstr(low_sum, "no missed notifications") || strstr(low_sum, "screenshot captured") ||
            strstr(low_sum, "touchpad")) {
            g_free(low_sum); g_free(low_bod); g_free(line);
            continue;
        }

        /* Drop Instagram unread/unseen notifications spam */
        if (strstr(low_sum, "unread message") || strstr(low_bod, "unread message") ||
            strstr(low_sum, "unseen notification") || strstr(low_bod, "unseen notification")) {
            g_free(low_sum); g_free(low_bod); g_free(line);
            continue;
        }
        g_free(low_sum); g_free(low_bod);

        char *norm_app = normalize_app_name(app_str);
        char *grp = NULL, *snd = NULL, *bod = NULL;
        extract_conversation_key(norm_app, sum_str, bod_str, &grp, &snd, &bod);

        /* Find existing conversation group */
        ConversationGroup *target_cg = NULL;
        for (GList *l = group_list; l != NULL; l = l->next) {
            ConversationGroup *cg = (ConversationGroup *)l->data;
            if (g_ascii_strcasecmp(cg->app, norm_app) == 0 &&
                g_ascii_strcasecmp(cg->base_name, grp) == 0) {
                target_cg = cg;
                break;
            }
        }

        if (!target_cg && g_ascii_strcasecmp(grp, norm_app) == 0) {
            for (GList *l = g_list_last(group_list); l != NULL; l = l->prev) {
                ConversationGroup *cg = (ConversationGroup *)l->data;
                if (g_ascii_strcasecmp(cg->app, norm_app) == 0) {
                    target_cg = cg;
                    break;
                }
            }
        }

        if (!target_cg) {
            target_cg = g_new0(ConversationGroup, 1);
            target_cg->app = strdup(norm_app);
            target_cg->base_name = (g_ascii_strcasecmp(grp, norm_app) == 0) ? strdup("Direct Message") : strdup(grp);
            target_cg->icon_str = (icon_str && strlen(icon_str) > 0) ? strdup(icon_str) : NULL;
            target_cg->messages = NULL;
            target_cg->msg_count = 0;
            target_cg->expanded = FALSE;
            group_list = g_list_append(group_list, target_cg);
        }

        MessageItem *m = g_new0(MessageItem, 1);
        m->time = strdup(time_str);
        m->sender = strdup(snd);
        m->body = strdup(bod);
        target_cg->messages = g_list_append(target_cg->messages, m);
        target_cg->msg_count++;

        if (icon_str && strlen(icon_str) > 0 && (!target_cg->icon_str || access(target_cg->icon_str, R_OK) != 0)) {
            if (target_cg->icon_str) free(target_cg->icon_str);
            target_cg->icon_str = strdup(icon_str);
        }

        free(norm_app);
        free(grp); free(snd); free(bod);
        g_free(line);
    }
    fclose(f);
}

/* --------------------------------------------------------------------------
 * Create Single Unified Block Widget for a Conversation
 * -------------------------------------------------------------------------- */
static GtkWidget *create_conversation_card(ConversationGroup *cg) {
    GtkWidget *event_box = gtk_event_box_new();
    gtk_event_box_set_above_child(GTK_EVENT_BOX(event_box), FALSE);

    GtkWidget *card = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
    gtk_style_context_add_class(gtk_widget_get_style_context(card), "notif-card");
    gtk_container_add(GTK_CONTAINER(event_box), card);

    /* 1. Card Header */
    GtkWidget *header = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_style_context_add_class(gtk_widget_get_style_context(header), "card-header");

    /* PFP or App Icon */
    MessageItem *latest_m = (MessageItem *)g_list_last(cg->messages)->data;
    GdkPixbuf *pb = load_avatar_or_icon(cg->app, cg->base_name, latest_m ? latest_m->sender : NULL, cg->icon_str, 34);
    if (pb) {
        GtkWidget *img = gtk_image_new_from_pixbuf(pb);
        gtk_box_pack_start(GTK_BOX(header), img, FALSE, FALSE, 0);
        g_object_unref(pb);
    }

    /* Titles & Info */
    GtkWidget *title_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);

    GtkWidget *top_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);

    /* App Tag Pill */
    GtkWidget *pill = gtk_label_new(cg->app);
    GtkStyleContext *p_ctx = gtk_widget_get_style_context(pill);
    gtk_style_context_add_class(p_ctx, "tag-pill");
    char *low_app = g_ascii_strdown(cg->app, -1);
    if (strstr(low_app, "whatsapp")) gtk_style_context_add_class(p_ctx, "tag-whatsapp");
    else if (strstr(low_app, "instagram")) gtk_style_context_add_class(p_ctx, "tag-instagram");
    else if (strstr(low_app, "discord")) gtk_style_context_add_class(p_ctx, "tag-discord");
    else if (strstr(low_app, "power")) gtk_style_context_add_class(p_ctx, "tag-power");
    else gtk_style_context_add_class(p_ctx, "tag-default");
    g_free(low_app);
    gtk_box_pack_start(GTK_BOX(top_row), pill, FALSE, FALSE, 0);

    /* Conversation Title */
    GtkWidget *lbl_title = gtk_label_new(cg->base_name);
    gtk_style_context_add_class(gtk_widget_get_style_context(lbl_title), "card-title");
    gtk_label_set_xalign(GTK_LABEL(lbl_title), 0.0);
    gtk_box_pack_start(GTK_BOX(top_row), lbl_title, FALSE, FALSE, 0);

    /* Message Count Badge if > 1 */
    if (cg->msg_count > 1) {
        char count_buf[32];
        snprintf(count_buf, sizeof(count_buf), "(%d msgs)", cg->msg_count);
        GtkWidget *lbl_count = gtk_label_new(count_buf);
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_count), "header-badge");
        gtk_box_pack_start(GTK_BOX(top_row), lbl_count, FALSE, FALSE, 0);
    }

    /* Timestamp */
    if (latest_m && latest_m->time) {
        GtkWidget *lbl_time = gtk_label_new(latest_m->time);
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_time), "card-time");
        gtk_box_pack_start(GTK_BOX(top_row), lbl_time, FALSE, FALSE, 0);
    }

    gtk_box_pack_start(GTK_BOX(title_box), top_row, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(header), title_box, TRUE, TRUE, 0);

    /* Dismiss Button ✕ */
    GtkWidget *btn_dismiss = gtk_button_new_with_label("✕");
    gtk_style_context_add_class(gtk_widget_get_style_context(btn_dismiss), "btn-dismiss-card");
    g_signal_connect(btn_dismiss, "clicked", G_CALLBACK(on_dismiss_btn_clicked), cg);
    gtk_box_pack_end(GTK_BOX(header), btn_dismiss, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(card), header, FALSE, FALSE, 0);

    /* 2. Messages Layout */
    int total = cg->msg_count;

    if (total > 5) {
        /* Earlier messages inside Revealer */
        cg->revealer = gtk_revealer_new();
        gtk_revealer_set_transition_type(GTK_REVEALER(cg->revealer), GTK_REVEALER_TRANSITION_TYPE_SLIDE_DOWN);
        gtk_revealer_set_transition_duration(GTK_REVEALER(cg->revealer), 150);

        GtkWidget *rev_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 3);
        int earlier_count = total - 5;
        int idx = 0;
        for (GList *l = cg->messages; l != NULL && idx < earlier_count; l = l->next, idx++) {
            MessageItem *m = (MessageItem *)l->data;
            const char *clean_b = clean_message_body_sender_prefix(m->body, m->sender);
            char *esc_sender = safe_markup_escape(m->sender);
            char *esc_body = safe_markup_escape(clean_b);
            char *line_str = NULL;
            if (m->sender && strlen(m->sender) > 0 && g_ascii_strcasecmp(m->sender, cg->app) != 0) {
                line_str = g_strdup_printf("• <span foreground='#89b4fa'><b>%s:</b></span> <span foreground='#a6adc8'>%s</span>",
                                           esc_sender, esc_body);
            } else {
                line_str = g_strdup_printf("• <span foreground='#a6adc8'>%s</span>", esc_body);
            }
            g_free(esc_sender);
            g_free(esc_body);

            GtkWidget *lbl = gtk_label_new(NULL);
            gtk_label_set_markup(GTK_LABEL(lbl), line_str);
            gtk_label_set_line_wrap(GTK_LABEL(lbl), TRUE);
            gtk_label_set_line_wrap_mode(GTK_LABEL(lbl), PANGO_WRAP_WORD_CHAR);
            gtk_label_set_xalign(GTK_LABEL(lbl), 0.0);
            gtk_box_pack_start(GTK_BOX(rev_box), lbl, FALSE, FALSE, 0);
            g_free(line_str);
        }
        gtk_container_add(GTK_CONTAINER(cg->revealer), rev_box);
        gtk_box_pack_start(GTK_BOX(card), cg->revealer, FALSE, FALSE, 0);

        /* Expand/Collapse Toggle Button */
        char toggle_lbl[64];
        snprintf(toggle_lbl, sizeof(toggle_lbl), "▼ Show %d earlier messages", earlier_count);
        cg->toggle_btn = gtk_button_new_with_label(toggle_lbl);
        gtk_style_context_add_class(gtk_widget_get_style_context(cg->toggle_btn), "btn-expand");
        g_signal_connect(cg->toggle_btn, "clicked", G_CALLBACK(toggle_expand), cg);
        gtk_box_pack_start(GTK_BOX(card), cg->toggle_btn, FALSE, FALSE, 0);

        /* Latest 5 messages */
        GList *latest_start = g_list_nth(cg->messages, earlier_count);
        for (GList *l = latest_start; l != NULL; l = l->next) {
            MessageItem *m = (MessageItem *)l->data;
            const char *clean_b = clean_message_body_sender_prefix(m->body, m->sender);
            char *esc_sender = safe_markup_escape(m->sender);
            char *esc_body = safe_markup_escape(clean_b);
            char *line_str = NULL;
            if (m->sender && strlen(m->sender) > 0 && g_ascii_strcasecmp(m->sender, cg->app) != 0) {
                line_str = g_strdup_printf("• <span foreground='#89b4fa'><b>%s:</b></span> %s",
                                           esc_sender, esc_body);
            } else {
                line_str = g_strdup_printf("• %s", esc_body);
            }
            g_free(esc_sender);
            g_free(esc_body);

            GtkWidget *lbl = gtk_label_new(NULL);
            gtk_label_set_markup(GTK_LABEL(lbl), line_str);
            gtk_label_set_line_wrap(GTK_LABEL(lbl), TRUE);
            gtk_label_set_line_wrap_mode(GTK_LABEL(lbl), PANGO_WRAP_WORD_CHAR);
            gtk_label_set_xalign(GTK_LABEL(lbl), 0.0);
            gtk_box_pack_start(GTK_BOX(card), lbl, FALSE, FALSE, 0);
            g_free(line_str);
        }
    } else {
        /* All messages shown directly inside this single block without truncation */
        for (GList *l = cg->messages; l != NULL; l = l->next) {
            MessageItem *m = (MessageItem *)l->data;
            const char *clean_b = clean_message_body_sender_prefix(m->body, m->sender);
            char *esc_sender = safe_markup_escape(m->sender);
            char *esc_body = safe_markup_escape(clean_b);
            char *line_str = NULL;
            if (m->sender && strlen(m->sender) > 0 && g_ascii_strcasecmp(m->sender, cg->app) != 0) {
                line_str = g_strdup_printf("• <span foreground='#89b4fa'><b>%s:</b></span> %s",
                                           esc_sender, esc_body);
            } else {
                line_str = g_strdup_printf("• %s", esc_body);
            }
            g_free(esc_sender);
            g_free(esc_body);

            GtkWidget *lbl = gtk_label_new(NULL);
            gtk_label_set_markup(GTK_LABEL(lbl), line_str);
            gtk_label_set_line_wrap(GTK_LABEL(lbl), TRUE);
            gtk_label_set_line_wrap_mode(GTK_LABEL(lbl), PANGO_WRAP_WORD_CHAR);
            gtk_label_set_xalign(GTK_LABEL(lbl), 0.0);
            gtk_box_pack_start(GTK_BOX(card), lbl, FALSE, FALSE, 0);
            g_free(line_str);
        }
    }

    g_signal_connect(event_box, "button-press-event", G_CALLBACK(on_card_button_press), cg);
    cg->card_widget = event_box;

    return event_box;
}

/* --------------------------------------------------------------------------
 * Main Window Creation
 * -------------------------------------------------------------------------- */
int main(int argc, char *argv[]) {
    /* Fast toggle check: if an instance is already running, toggle close */
    const char *lock_file = "/tmp/sys_notif_center.pid";
    FILE *pf = fopen(lock_file, "r");
    if (pf) {
        pid_t existing_pid = 0;
        if (fscanf(pf, "%d", &existing_pid) == 1 && existing_pid > 0) {
            if (kill(existing_pid, 0) == 0 && existing_pid != getpid()) {
                kill(existing_pid, SIGTERM);
                fclose(pf);
                unlink(lock_file);
                return 0;
            }
        }
        fclose(pf);
    }

    pf = fopen(lock_file, "w");
    if (pf) {
        fprintf(pf, "%d\n", getpid());
        fclose(pf);
    }

    gtk_init(&argc, &argv);

    /* Load CSS */
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(provider, STYLE_CSS, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );

    /* Create Centered Modal Window */
    main_window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(main_window), "Notification Center");
    g_set_prgname("sys-notif-center");
    gtk_window_set_role(GTK_WINDOW(main_window), "sys-notif-center");
    gtk_window_set_type_hint(GTK_WINDOW(main_window), GDK_WINDOW_TYPE_HINT_DIALOG);
    gtk_window_set_default_size(GTK_WINDOW(main_window), 680, 520);
    gtk_window_set_position(GTK_WINDOW(main_window), GTK_WIN_POS_CENTER_ALWAYS);
    gtk_window_set_decorated(GTK_WINDOW(main_window), FALSE);
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(main_window), TRUE);
    gtk_window_set_skip_pager_hint(GTK_WINDOW(main_window), TRUE);
    gtk_window_set_keep_above(GTK_WINDOW(main_window), TRUE);

    GtkStyleContext *win_ctx = gtk_widget_get_style_context(main_window);
    gtk_style_context_add_class(win_ctx, "center-modal");

    GtkWidget *root_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(main_window), root_box);

    /* 1. Header Bar */
    GtkWidget *header_bar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_style_context_add_class(gtk_widget_get_style_context(header_bar), "header-bar");

    GtkWidget *lbl_header = gtk_label_new("󰂚 Notifications");
    gtk_style_context_add_class(gtk_widget_get_style_context(lbl_header), "header-title");
    gtk_box_pack_start(GTK_BOX(header_bar), lbl_header, FALSE, FALSE, 0);

    unread_badge = gtk_label_new("");
    gtk_style_context_add_class(gtk_widget_get_style_context(unread_badge), "header-badge");
    gtk_box_pack_start(GTK_BOX(header_bar), unread_badge, FALSE, FALSE, 0);

    /* Clear All button */
    GtkWidget *btn_clear = gtk_button_new_with_label("󰎟 Clear All");
    gtk_style_context_add_class(gtk_widget_get_style_context(btn_clear), "btn-clear");
    g_signal_connect(btn_clear, "clicked", G_CALLBACK(on_clear_all_clicked), NULL);
    gtk_box_pack_end(GTK_BOX(header_bar), btn_clear, FALSE, FALSE, 0);

    /* Close button ✕ */
    GtkWidget *btn_close = gtk_button_new_with_label("✕");
    gtk_style_context_add_class(gtk_widget_get_style_context(btn_close), "btn-close");
    g_signal_connect_swapped(btn_close, "clicked", G_CALLBACK(gtk_main_quit), NULL);
    gtk_box_pack_end(GTK_BOX(header_bar), btn_close, FALSE, FALSE, 4);

    gtk_box_pack_start(GTK_BOX(root_box), header_bar, FALSE, FALSE, 0);

    /* 2. Scrollable Body */
    GtkWidget *scrolled = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scrolled), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_vexpand(scrolled, TRUE);

    cards_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_style_context_add_class(gtk_widget_get_style_context(cards_box), "cards-container");
    gtk_container_add(GTK_CONTAINER(scrolled), cards_box);
    gtk_box_pack_start(GTK_BOX(root_box), scrolled, TRUE, TRUE, 0);

    /* Load history */
    load_history_groups();

    /* Reverse to show newest conversation on top */
    group_list = g_list_reverse(group_list);

    int total_unread = g_list_length(group_list);
    if (total_unread > 0) {
        char badge_buf[32];
        snprintf(badge_buf, sizeof(badge_buf), "%d unread", total_unread);
        gtk_label_set_text(GTK_LABEL(unread_badge), badge_buf);
        gtk_widget_show(unread_badge);

        for (GList *l = group_list; l != NULL; l = l->next) {
            ConversationGroup *cg = (ConversationGroup *)l->data;
            GtkWidget *card = create_conversation_card(cg);
            gtk_box_pack_start(GTK_BOX(cards_box), card, FALSE, FALSE, 0);
        }
    } else {
        gtk_widget_hide(unread_badge);

        /* Empty state */
        GtkWidget *empty_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
        gtk_style_context_add_class(gtk_widget_get_style_context(empty_box), "empty-state");
        gtk_widget_set_halign(empty_box, GTK_ALIGN_CENTER);
        gtk_widget_set_valign(empty_box, GTK_ALIGN_CENTER);

        GtkWidget *lbl_icon = gtk_label_new("󰂛");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_icon), "empty-icon");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_icon, FALSE, FALSE, 0);

        GtkWidget *lbl_txt = gtk_label_new("No missed notifications");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_txt), "empty-label");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_txt, FALSE, FALSE, 0);

        GtkWidget *lbl_sub = gtk_label_new("You're all caught up!");
        gtk_style_context_add_class(gtk_widget_get_style_context(lbl_sub), "empty-sub");
        gtk_box_pack_start(GTK_BOX(empty_box), lbl_sub, FALSE, FALSE, 0);

        gtk_box_pack_start(GTK_BOX(cards_box), empty_box, TRUE, TRUE, 20);
    }

    g_signal_connect(main_window, "key-press-event", G_CALLBACK(on_key_press), NULL);
    g_signal_connect(main_window, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    gtk_widget_show_all(main_window);
    gtk_main();

    unlink(lock_file);
    return 0;
}
