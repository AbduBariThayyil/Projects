#include "ui.h"
#include <glob.h>

void ui_init(UiContext *ui, const ScreenGeometry *geom, bool fprint_available) {
    if (!ui) return;
    memset(ui, 0, sizeof(UiContext));
    ui->state = UI_STATE_IDLE;
    ui->pw_length = 0;
    ui->fprint_available = fprint_available;
    ui->shake_duration = 0.35;
    ui->is_shaking = false;

    if (geom) {
        ui->center_x = geom->center_x;
        ui->center_y = geom->center_y;
    } else {
        ui->center_x = 683;
        ui->center_y = 384;
    }

    if (fprint_available) {
        snprintf(ui->status_text, sizeof(ui->status_text), "󰈷 Swipe fingerprint or enter password");
    } else {
        snprintf(ui->status_text, sizeof(ui->status_text), "󰌾 Enter password to unlock");
    }
}

void ui_set_state(UiContext *ui, UiState state, const char *custom_msg) {
    if (!ui) return;
    ui->state = state;
    if (custom_msg && custom_msg[0] != '\0') {
        snprintf(ui->status_text, sizeof(ui->status_text), "%s", custom_msg);
    } else {
        switch (state) {
            case UI_STATE_IDLE:
            case UI_STATE_TYPING:
                if (ui->fprint_available) {
                    snprintf(ui->status_text, sizeof(ui->status_text), "󰈷 Swipe fingerprint or enter password");
                } else {
                    snprintf(ui->status_text, sizeof(ui->status_text), "󰌾 Enter password to unlock");
                }
                break;
            case UI_STATE_VERIFYING:
                snprintf(ui->status_text, sizeof(ui->status_text), "󰑮 Verifying...");
                break;
            case UI_STATE_AUTH_FAILED:
                snprintf(ui->status_text, sizeof(ui->status_text), "󰅙 Authentication Failed");
                break;
            case UI_STATE_FPRINT_MATCH:
                snprintf(ui->status_text, sizeof(ui->status_text), "󰈷 Fingerprint Recognized");
                break;
            case UI_STATE_FPRINT_WARNING:
                /* keep existing custom_msg */
                break;
        }
    }
}

void ui_set_pw_length(UiContext *ui, int len) {
    if (!ui) return;
    ui->pw_length = len;
    if (len > 0 && ui->state == UI_STATE_IDLE) {
        ui->state = UI_STATE_TYPING;
    } else if (len == 0 && ui->state == UI_STATE_TYPING) {
        ui->state = UI_STATE_IDLE;
    }
}

void ui_trigger_shake(UiContext *ui) {
    if (!ui) return;
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    ui->shake_start_time = ts.tv_sec + (ts.tv_nsec / 1e9);
    ui->is_shaking = true;
}

bool ui_update_shake(UiContext *ui, double current_time, double *out_offset_x) {
    if (!ui || !out_offset_x) return false;
    if (!ui->is_shaking) {
        *out_offset_x = 0.0;
        return false;
    }

    double elapsed = current_time - ui->shake_start_time;
    if (elapsed >= ui->shake_duration) {
        ui->is_shaking = false;
        *out_offset_x = 0.0;
        return false;
    }

    double progress = elapsed / ui->shake_duration;
    double decay = 1.0 - progress;
    *out_offset_x = sin(progress * 8.0 * M_PI) * decay * 18.0;
    return true;
}

int ui_get_battery_info(int *capacity, char *status_str, size_t status_len) {
    glob_t g;
    if (glob("/sys/class/power_supply/BAT*", 0, NULL, &g) != 0 || g.gl_pathc == 0) {
        globfree(&g);
        return -1;
    }

    char cap_path[MAX_PATH_LEN];
    char stat_path[MAX_PATH_LEN];
    snprintf(cap_path, sizeof(cap_path), "%s/capacity", g.gl_pathv[0]);
    snprintf(stat_path, sizeof(stat_path), "%s/status", g.gl_pathv[0]);
    globfree(&g);

    int cap = -1;
    FILE *fc = fopen(cap_path, "r");
    if (fc) {
        if (fscanf(fc, "%d", &cap) != 1) cap = -1;
        fclose(fc);
    }

    if (status_str && status_len > 0) {
        status_str[0] = '\0';
        FILE *fs = fopen(stat_path, "r");
        if (fs) {
            if (fgets(status_str, status_len, fs)) {
                size_t l = strlen(status_str);
                while (l > 0 && (status_str[l - 1] == '\n' || status_str[l - 1] == '\r')) {
                    status_str[--l] = '\0';
                }
            }
            fclose(fs);
        }
    }

    if (capacity) *capacity = cap;
    return (cap >= 0) ? 0 : -1;
}

static const char *get_battery_icon(int capacity, const char *status) {
    if (status && strcasecmp(status, "Charging") == 0) {
        return "󰂄";
    }
    if (capacity >= 95) return "󰁹";
    if (capacity >= 85) return "󰂂";
    if (capacity >= 75) return "󰂁";
    if (capacity >= 65) return "󰂀";
    if (capacity >= 55) return "󰁿";
    if (capacity >= 45) return "󰁾";
    if (capacity >= 35) return "󰁽";
    if (capacity >= 25) return "󰁼";
    if (capacity >= 15) return "󰁻";
    return "󰁺";
}

void ui_render(UiContext *ui, cairo_t *cr, cairo_surface_t *bg_surface,
               int win_w, int win_h, double current_time) {
    if (!ui || !cr) return;

    /* 1. Paint cached background surface or fallback */
    if (bg_surface) {
        cairo_set_source_surface(cr, bg_surface, 0, 0);
        cairo_paint(cr);
    } else {
        cairo_set_source_rgb(cr, COLOR_BASE_R, COLOR_BASE_G, COLOR_BASE_B);
        cairo_paint(cr);
    }

    int cx = ui->center_x;
    int cy = ui->center_y;
    if (cx <= 0 || cx >= win_w) cx = win_w / 2;
    if (cy <= 0 || cy >= win_h) cy = win_h / 2;

    /* 2. Format Current Time & Date */
    time_t raw_time = time(NULL);
    struct tm tm_info;
    localtime_r(&raw_time, &tm_info);

    char time_str[32];
    char date_str[64];
    strftime(time_str, sizeof(time_str), "%H:%M", &tm_info);
    strftime(date_str, sizeof(date_str), "%A, %B %d", &tm_info);

    /* 3. Query Battery */
    int bat_cap = -1;
    char bat_status[32] = {0};
    bool has_bat = (ui_get_battery_info(&bat_cap, bat_status, sizeof(bat_status)) == 0);
    char bat_display[64] = {0};
    if (has_bat) {
        const char *icon = get_battery_icon(bat_cap, bat_status);
        if (strcasecmp(bat_status, "Charging") == 0) {
            snprintf(bat_display, sizeof(bat_display), "%s %d%% (Charging)", icon, bat_cap);
        } else {
            snprintf(bat_display, sizeof(bat_display), "%s %d%%", icon, bat_cap);
        }
    }

    /* Pango Setup */
    PangoLayout *layout = pango_cairo_create_layout(cr);
    PangoFontDescription *desc = NULL;

    /* Render Digital Clock */
    desc = pango_font_description_from_string("JetBrainsMono NF Bold 72");
    pango_layout_set_font_description(layout, desc);
    pango_layout_set_text(layout, time_str, -1);
    pango_layout_set_alignment(layout, PANGO_ALIGN_CENTER);
    pango_font_description_free(desc);

    int text_w, text_h;
    pango_layout_get_pixel_size(layout, &text_w, &text_h);

    int clock_y = cy - 140;
    cairo_set_source_rgb(cr, COLOR_TEXT_R, COLOR_TEXT_G, COLOR_TEXT_B);
    cairo_move_to(cr, cx - (text_w / 2.0), clock_y);
    pango_cairo_show_layout(cr, layout);

    /* Render Date */
    desc = pango_font_description_from_string("JetBrainsMono NF 20");
    pango_layout_set_font_description(layout, desc);
    pango_layout_set_text(layout, date_str, -1);
    pango_font_description_free(desc);

    pango_layout_get_pixel_size(layout, &text_w, &text_h);
    int date_y = clock_y + 105;
    cairo_set_source_rgb(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B);
    cairo_move_to(cr, cx - (text_w / 2.0), date_y);
    pango_cairo_show_layout(cr, layout);

    /* Render Battery if available */
    if (has_bat) {
        desc = pango_font_description_from_string("JetBrainsMono NF 14");
        pango_layout_set_font_description(layout, desc);
        pango_layout_set_text(layout, bat_display, -1);
        pango_font_description_free(desc);

        pango_layout_get_pixel_size(layout, &text_w, &text_h);
        int bat_y = date_y + 36;
        if (bat_cap <= 15 && strcasecmp(bat_status, "Charging") != 0) {
            cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
        } else {
            cairo_set_source_rgb(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B);
        }
        cairo_move_to(cr, cx - (text_w / 2.0), bat_y);
        pango_cairo_show_layout(cr, layout);
    }

    /* 4. Password dots & Status Label with Shake Animation */
    double shake_offset = 0.0;
    ui_update_shake(ui, current_time, &shake_offset);

    cairo_save(cr);
    cairo_translate(cr, shake_offset, 0);

    int indicator_y = cy + 70;

    /* Draw Password Bullets or subtle ring */
    if (ui->pw_length > 0) {
        const double dot_radius = 6.0;
        const double dot_spacing = 20.0;
        int count = ui->pw_length;
        if (count > 24) count = 24; /* cap visual dots */

        double total_w = (count - 1) * dot_spacing;
        double start_x = cx - (total_w / 2.0);

        for (int i = 0; i < count; i++) {
            double dot_x = start_x + (i * dot_spacing);

            /* Outer glow / soft ring in Lavender */
            cairo_set_source_rgba(cr, COLOR_LAVENDER_R, COLOR_LAVENDER_G, COLOR_LAVENDER_B, 0.35);
            cairo_arc(cr, dot_x, indicator_y, dot_radius + 2.5, 0, 2 * M_PI);
            cairo_fill(cr);

            /* Inner dot in Mauve */
            cairo_set_source_rgb(cr, COLOR_MAUVE_R, COLOR_MAUVE_G, COLOR_MAUVE_B);
            cairo_arc(cr, dot_x, indicator_y, dot_radius, 0, 2 * M_PI);
            cairo_fill(cr);
        }
    } else {
        /* Elegant subtle ring when empty */
        cairo_set_source_rgba(cr, COLOR_MAUVE_R, COLOR_MAUVE_G, COLOR_MAUVE_B, 0.50);
        cairo_set_line_width(cr, 2.0);
        cairo_arc(cr, cx, indicator_y, 8.0, 0, 2 * M_PI);
        cairo_stroke(cr);
    }

    /* Status Label */
    desc = pango_font_description_from_string("JetBrainsMono NF 15");
    pango_layout_set_font_description(layout, desc);
    pango_layout_set_text(layout, ui->status_text, -1);
    pango_font_description_free(desc);

    pango_layout_get_pixel_size(layout, &text_w, &text_h);
    int status_y = indicator_y + 35;

    switch (ui->state) {
        case UI_STATE_VERIFYING:
            cairo_set_source_rgb(cr, COLOR_YELLOW_R, COLOR_YELLOW_G, COLOR_YELLOW_B);
            break;
        case UI_STATE_AUTH_FAILED:
            cairo_set_source_rgb(cr, COLOR_RED_R, COLOR_RED_G, COLOR_RED_B);
            break;
        case UI_STATE_FPRINT_MATCH:
            cairo_set_source_rgb(cr, COLOR_GREEN_R, COLOR_GREEN_G, COLOR_GREEN_B);
            break;
        case UI_STATE_FPRINT_WARNING:
            cairo_set_source_rgb(cr, COLOR_PEACH_R, COLOR_PEACH_G, COLOR_PEACH_B);
            break;
        case UI_STATE_IDLE:
        case UI_STATE_TYPING:
        default:
            cairo_set_source_rgb(cr, COLOR_SUBTEXT_R, COLOR_SUBTEXT_G, COLOR_SUBTEXT_B);
            break;
    }

    cairo_move_to(cr, cx - (text_w / 2.0), status_y);
    pango_cairo_show_layout(cr, layout);

    cairo_restore(cr);
    g_object_unref(layout);
}
