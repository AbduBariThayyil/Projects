/* =========================================================================
 * sys-launcher: Blazing-Fast Native C/GTK3 Application Launcher & Toggler
 * Unified dual-mode launcher replacing Rofi script sprawl with instant GIO
 * indexing, Catppuccin Mocha/Dracula styling, and sub-millisecond execution.
 * ========================================================================= */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <gio/gio.h>
#include <gio/gdesktopappinfo.h>
#include <gtk/gtk.h>
#include <gdk/gdk.h>

#define VERSION "1.2.0"

typedef struct {
    char *id;            /* Desktop ID, e.g. "firefox.desktop" */
    char *name;          /* Human readable name */
    char *comment;       /* Comment / Description */
    char *executable;    /* Exec binary / args */
    char *lower_name;    /* Cached lowercase for instant searching */
    char *lower_comment;
    char *lower_exec;
    char *lower_id;
    char *norm_name;     /* Cached alphanumeric lowercase for multi-token fuzzy search */
    char *norm_id;
    char *norm_exec;
    GIcon *icon;
    guint launch_count;  /* Frecency launch count */
    gboolean is_hidden;
    gboolean is_terminal;
    GAppInfo *info;
    GtkWidget *row_widget;
    GtkWidget *badge_label;
    GtkWidget *subtitle_label;
} AppItem;

typedef struct {
    gboolean is_toggle_mode;
    GtkWidget *window;
    GtkWidget *entry;
    GtkWidget *listbox;
    GtkWidget *scrolled_window;
    GtkWidget *footer_hint;
    GtkWidget *cmd_row;
    GtkWidget *cmd_title_label;
    GtkWidget *cmd_subtitle_label;
    GPtrArray *apps;
    char *current_query;
} LauncherState;

static LauncherState app_state = {0};
static gboolean is_quitting = FALSE;
static GHashTable *frecency_map = NULL;
static char *frecency_file_path = NULL;

/* -------------------------------------------------------------------------
 * Forward Declarations
 * ------------------------------------------------------------------------- */
static void safe_quit(void);
static void init_frecency(void);
static void save_frecency(void);
static void record_app_launch(const char *desktop_id);
static void free_frecency(void);
static void position_window_on_active_monitor(GtkWindow *window, int width, int height);
static void execute_shell_command(void);
static void populate_apps(void);
static void free_apps(void);
static gint compute_app_score(AppItem *app, const char *query);
static gboolean app_matches_query(AppItem *app, const char *query);
static GPtrArray *get_sorted_visible_apps(void);
static void select_first_visible_row(GtkListBox *box);
static void navigate_list(GtkListBox *box, int direction);
static gboolean set_desktop_file_visibility(const char *desktop_id, gboolean hide);
static void launch_app(AppItem *app);
static void launch_terminal_app(const char *cmdline, const char *fallback_exec);
static void toggle_app(AppItem *app, GtkListBox *box);
static void hide_app_from_launcher(AppItem *app, GtkListBox *box);

/* -------------------------------------------------------------------------
 * Clean Lifecycle & Quitting Helper
 * ------------------------------------------------------------------------- */
static void safe_quit(void) {
    if (is_quitting) return;
    is_quitting = TRUE;
    if (gtk_main_level() > 0) {
        gtk_main_quit();
    }
}

/* -------------------------------------------------------------------------
 * Frecency & Usage Tracking (~/.cache/sys-launcher/frecency.txt)
 * ------------------------------------------------------------------------- */
static void init_frecency(void) {
    char *cache_dir = g_build_filename(g_get_user_cache_dir(), "sys-launcher", NULL);
    g_mkdir_with_parents(cache_dir, 0755);
    frecency_file_path = g_build_filename(cache_dir, "frecency.txt", NULL);
    g_free(cache_dir);

    frecency_map = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);

    char *contents = NULL;
    gsize length = 0;
    if (g_file_get_contents(frecency_file_path, &contents, &length, NULL)) {
        char **lines = g_strsplit(contents, "\n", -1);
        for (int i = 0; lines[i]; i++) {
            char *line = g_strstrip(lines[i]);
            if (!*line || line[0] == '#') continue;
            char *space = strchr(line, ' ');
            if (space) {
                *space = '\0';
                char *id = g_strstrip(line);
                char *cnt_str = g_strstrip(space + 1);
                if (*id && *cnt_str) {
                    guint count = (guint)g_ascii_strtoull(cnt_str, NULL, 10);
                    g_hash_table_insert(frecency_map, g_strdup(id), GUINT_TO_POINTER(count));
                }
            }
        }
        g_strfreev(lines);
        g_free(contents);
    }
}

static void save_frecency(void) {
    if (!frecency_map || !frecency_file_path) return;

    GString *out = g_string_new("");
    GHashTableIter iter;
    gpointer key, value;
    g_hash_table_iter_init(&iter, frecency_map);
    while (g_hash_table_iter_next(&iter, &key, &value)) {
        const char *id = (const char *)key;
        guint count = GPOINTER_TO_UINT(value);
        if (count > 0) {
            g_string_append_printf(out, "%s %u\n", id, count);
        }
    }

    g_file_set_contents(frecency_file_path, out->str, (gssize)out->len, NULL);
    g_string_free(out, TRUE);
}

static void record_app_launch(const char *desktop_id) {
    if (!desktop_id || !*desktop_id) return;
    if (!frecency_map) {
        init_frecency();
    }

    gpointer val = g_hash_table_lookup(frecency_map, desktop_id);
    guint count = val ? GPOINTER_TO_UINT(val) + 1 : 1;
    g_hash_table_insert(frecency_map, g_strdup(desktop_id), GUINT_TO_POINTER(count));

    save_frecency();
}

static void free_frecency(void) {
    if (frecency_map) {
        g_hash_table_destroy(frecency_map);
        frecency_map = NULL;
    }
    g_free(frecency_file_path);
    frecency_file_path = NULL;
}

/* -------------------------------------------------------------------------
 * Active Monitor Centering
 * ------------------------------------------------------------------------- */
static void position_window_on_active_monitor(GtkWindow *window, int width, int height) {
    GdkDisplay *display = gdk_display_get_default();
    if (!display) return;

    gint px = 0, py = 0;
    GdkSeat *seat = gdk_display_get_default_seat(display);
    if (seat) {
        GdkDevice *pointer = gdk_seat_get_pointer(seat);
        if (pointer) {
            gdk_device_get_position(pointer, NULL, &px, &py);
        }
    }

    GdkMonitor *mon = gdk_display_get_monitor_at_point(display, px, py);
    if (!mon) {
        mon = gdk_display_get_primary_monitor(display);
    }
    if (!mon && gdk_display_get_n_monitors(display) > 0) {
        mon = gdk_display_get_monitor(display, 0);
    }

    GdkRectangle geo = {0, 0, 1920, 1080};
    if (mon) {
        gdk_monitor_get_geometry(mon, &geo);
    }

    gint win_x = geo.x + (geo.width - width) / 2;
    gint win_y = geo.y + (geo.height - height) / 2;

    gtk_window_move(window, win_x, win_y);
}

/* -------------------------------------------------------------------------
 * Dedicated Shell Command Execution (! or > Prefix)
 * ------------------------------------------------------------------------- */
static void execute_shell_command(void) {
    const char *q = app_state.current_query;
    if (!q || (*q != '!' && *q != '>')) return;

    const char *cmd = q + 1;
    while (*cmd == ' ' || *cmd == '\t') cmd++;

    if (*cmd == '\0') {
        return;
    }

    char *argv[] = {
        (char *)"/bin/sh",
        (char *)"-c",
        (char *)cmd,
        NULL
    };

    GError *err = NULL;
    if (!g_spawn_async(NULL, argv, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, NULL, &err)) {
        if (err) {
            g_warning("Failed to execute shell command '%s': %s", cmd, err->message);
            g_error_free(err);
        }
    }

    safe_quit();
}

/* -------------------------------------------------------------------------
 * String Normalization & Fast Fuzzy / Word Matching
 * ------------------------------------------------------------------------- */
static char *normalize_str(const char *str) {
    if (!str) return NULL;
    GString *res = g_string_new("");
    for (const char *p = str; *p; p++) {
        if (g_ascii_isalnum(*p)) {
            g_string_append_c(res, g_ascii_tolower(*p));
        }
    }
    return g_string_free(res, FALSE);
}

static gboolean contains_token(const char *haystack, const char *token) {
    if (!haystack || !token || !*token) return FALSE;
    return (strstr(haystack, token) != NULL);
}

static gboolean word_has_prefix(const char *haystack, const char *prefix) {
    if (!haystack || !prefix || !*prefix) return FALSE;
    const char *p = haystack;
    gsize plen = strlen(prefix);
    gboolean at_word_start = TRUE;

    while (*p) {
        if (!g_ascii_isalnum(*p)) {
            at_word_start = TRUE;
            p++;
            continue;
        }
        if (at_word_start) {
            if (g_ascii_strncasecmp(p, prefix, plen) == 0) {
                return TRUE;
            }
            at_word_start = FALSE;
        }
        p++;
    }
    return FALSE;
}

static gboolean fuzzy_match_token(const char *haystack, const char *token) {
    if (!token || !*token) return TRUE;
    if (!haystack || !*haystack) return FALSE;
    while (*token && *haystack) {
        if (g_ascii_tolower(*token) == g_ascii_tolower(*haystack)) {
            token++;
        }
        haystack++;
    }
    return (*token == '\0');
}

static gboolean app_matches_query(AppItem *app, const char *query) {
    if (query && (*query == '!' || *query == '>')) {
        return FALSE;
    }
    if (!app_state.is_toggle_mode && app->is_hidden) {
        return FALSE;
    }
    if (!query || !*query) {
        return TRUE;
    }

    /* Fast path: normalized query substring match across name, exec, or id */
    char *norm_q = normalize_str(query);
    if (norm_q && *norm_q) {
        if ((app->norm_name && strstr(app->norm_name, norm_q)) ||
            (app->norm_exec && strstr(app->norm_exec, norm_q)) ||
            (app->norm_id && strstr(app->norm_id, norm_q)) ||
            (app->norm_name && fuzzy_match_token(app->norm_name, norm_q))) {
            g_free(norm_q);
            return TRUE;
        }
    }
    g_free(norm_q);

    char **tokens = g_strsplit_set(query, " \t\r\n", -1);
    gboolean all_matched = TRUE;
    for (int i = 0; tokens[i]; i++) {
        if (tokens[i][0] == '\0') continue;
        char *tok = g_ascii_strdown(tokens[i], -1);
        gboolean tok_match = FALSE;
        if (contains_token(app->lower_name, tok) ||
            contains_token(app->lower_comment, tok) ||
            contains_token(app->lower_exec, tok) ||
            contains_token(app->lower_id, tok) ||
            word_has_prefix(app->lower_name, tok) ||
            fuzzy_match_token(app->lower_name, tok)) {
            tok_match = TRUE;
        }
        g_free(tok);
        if (!tok_match) {
            all_matched = FALSE;
            break;
        }
    }
    g_strfreev(tokens);
    return all_matched;
}

static gint compute_app_score(AppItem *app, const char *query) {
    if (!query || !*query) return 0;
    char *q = g_ascii_strdown(query, -1);
    g_strstrip(q);
    if (!*q) {
        g_free(q);
        return 0;
    }

    gint score = 0;
    char *norm_q = normalize_str(q);

    /* 1. Whole query exact / prefix / substring matches */
    if (g_strcmp0(app->lower_name, q) == 0) {
        score += 30000;
    } else if (app->norm_name && norm_q && *norm_q && g_strcmp0(app->norm_name, norm_q) == 0) {
        /* Normalized exact match across word boundaries (e.g. "fire fox" -> "firefox", "code oss" -> "Code - OSS") */
        score += 25000;
    } else if (g_str_has_prefix(app->lower_name, q)) {
        score += 20000;
    } else if (app->norm_name && norm_q && *norm_q && g_str_has_prefix(app->norm_name, norm_q)) {
        score += 18000;
    } else if (strstr(app->lower_name, q)) {
        score += 15000;
    } else if (app->norm_name && norm_q && *norm_q && strstr(app->norm_name, norm_q)) {
        score += 12000;
    } else if (app->norm_exec && norm_q && *norm_q && g_strcmp0(app->norm_exec, norm_q) == 0) {
        score += 11000;
    } else if (app->norm_id && norm_q && *norm_q && strstr(app->norm_id, norm_q)) {
        score += 10000;
    } else if (app->norm_name && norm_q && *norm_q && fuzzy_match_token(app->norm_name, norm_q)) {
        score += 5000;
    }

    /* 2. Multi-token decomposition scoring */
    char **tokens = g_strsplit_set(q, " \t\r\n", -1);
    int token_count = 0;
    int tokens_in_name = 0;
    int tokens_matched = 0;

    for (int i = 0; tokens[i]; i++) {
        if (tokens[i][0] == '\0') continue;
        token_count++;
        const char *tok = tokens[i];

        if (g_strcmp0(app->lower_name, tok) == 0) {
            score += 6000;
            tokens_in_name++;
            tokens_matched++;
        } else if (word_has_prefix(app->lower_name, tok)) {
            score += 4500;
            tokens_in_name++;
            tokens_matched++;
        } else if (g_str_has_prefix(app->lower_name, tok)) {
            score += 3500;
            tokens_in_name++;
            tokens_matched++;
        } else if (strstr(app->lower_name, tok)) {
            score += 2500;
            tokens_in_name++;
            tokens_matched++;
        } else if (fuzzy_match_token(app->lower_name, tok)) {
            score += 1500;
            tokens_in_name++;
            tokens_matched++;
        } else if (word_has_prefix(app->lower_id, tok) || g_str_has_prefix(app->lower_id, tok)) {
            score += 1500;
            tokens_matched++;
        } else if (strstr(app->lower_id, tok)) {
            score += 1000;
            tokens_matched++;
        } else if (word_has_prefix(app->lower_exec, tok) || g_str_has_prefix(app->lower_exec, tok)) {
            score += 1200;
            tokens_matched++;
        } else if (strstr(app->lower_exec, tok)) {
            score += 800;
            tokens_matched++;
        } else if (strstr(app->lower_comment, tok)) {
            score += 600;
            tokens_matched++;
        } else if (fuzzy_match_token(app->lower_comment, tok)) {
            score += 300;
            tokens_matched++;
        }
    }

    if (token_count > 1) {
        if (tokens_in_name == token_count) {
            score += 12000; /* All tokens matched in app name! */
        } else if (tokens_matched == token_count) {
            score += 6000;  /* All tokens matched across fields! */
        }
    }

    /* 3. Frecency bonus (+ count * 150, capped at 6000) */
    if (score > 0 && app->launch_count > 0) {
        gint bonus = (gint)app->launch_count * 150;
        if (bonus > 6000) bonus = 6000;
        score += bonus;
    }

    g_strfreev(tokens);
    g_free(norm_q);
    g_free(q);

    return score;
}

static gint compare_app_items(gconstpointer a, gconstpointer b) {
    AppItem *app_a = *(AppItem **)a;
    AppItem *app_b = *(AppItem **)b;
    if (app_state.current_query && *app_state.current_query) {
        gint score_a = compute_app_score(app_a, app_state.current_query);
        gint score_b = compute_app_score(app_b, app_state.current_query);
        if (score_a != score_b) {
            return score_b - score_a; /* Higher score first */
        }
        if (app_a->launch_count != app_b->launch_count) {
            return (gint)app_b->launch_count - (gint)app_a->launch_count;
        }
    } else {
        /* Empty query: sort by frecency (most used applications first), with alphabetical tie-breaking! */
        if (!app_state.is_toggle_mode) {
            if (app_a->launch_count != app_b->launch_count) {
                return (gint)app_b->launch_count - (gint)app_a->launch_count;
            }
        }
    }
    return g_utf8_collate(app_a->name ? app_a->name : app_a->id,
                          app_b->name ? app_b->name : app_b->id);
}

static GPtrArray *get_sorted_visible_apps(void) {
    GPtrArray *arr = g_ptr_array_new();
    if (!app_state.apps) return arr;

    const char *q = app_state.current_query;
    if (q && (*q == '!' || *q == '>')) {
        return arr;
    }

    for (guint i = 0; i < app_state.apps->len; i++) {
        AppItem *app = g_ptr_array_index(app_state.apps, i);
        if (app_matches_query(app, app_state.current_query)) {
            g_ptr_array_add(arr, app);
        }
    }
    g_ptr_array_sort(arr, compare_app_items);
    return arr;
}

static gint sort_func(GtkListBoxRow *row1, GtkListBoxRow *row2, gpointer user_data) {
    (void)user_data;
    if (app_state.cmd_row) {
        if (row1 == GTK_LIST_BOX_ROW(app_state.cmd_row)) return -1;
        if (row2 == GTK_LIST_BOX_ROW(app_state.cmd_row)) return 1;
    }

    AppItem *a = g_object_get_data(G_OBJECT(row1), "app_item");
    AppItem *b = g_object_get_data(G_OBJECT(row2), "app_item");
    if (!a && !b) return 0;
    if (!a) return 1;
    if (!b) return -1;

    if (app_state.current_query && *app_state.current_query) {
        gint score_a = compute_app_score(a, app_state.current_query);
        gint score_b = compute_app_score(b, app_state.current_query);
        if (score_a != score_b) {
            return score_b - score_a; /* Higher score first */
        }
        if (a->launch_count != b->launch_count) {
            return (gint)b->launch_count - (gint)a->launch_count;
        }
    } else {
        /* Empty query: sort by frecency (most used applications first), with alphabetical tie-breaking! */
        if (!app_state.is_toggle_mode) {
            if (a->launch_count != b->launch_count) {
                return (gint)b->launch_count - (gint)a->launch_count;
            }
        }
    }

    return g_utf8_collate(a->name ? a->name : a->id, b->name ? b->name : b->id);
}

static gboolean filter_func(GtkListBoxRow *row, gpointer user_data) {
    (void)user_data;
    const char *q = app_state.current_query;
    gboolean is_cmd = (q && (*q == '!' || *q == '>'));

    if (app_state.cmd_row && row == GTK_LIST_BOX_ROW(app_state.cmd_row)) {
        return is_cmd;
    }

    if (is_cmd) {
        return FALSE;
    }

    AppItem *app = g_object_get_data(G_OBJECT(row), "app_item");
    if (!app) return FALSE;
    return app_matches_query(app, q);
}

/* -------------------------------------------------------------------------
 * List Navigation & Selection
 * ------------------------------------------------------------------------- */
static void select_first_visible_row(GtkListBox *box) {
    const char *q = app_state.current_query;
    if (q && (*q == '!' || *q == '>')) {
        if (app_state.cmd_row) {
            gtk_list_box_select_row(box, GTK_LIST_BOX_ROW(app_state.cmd_row));
            if (app_state.scrolled_window) {
                GtkAdjustment *vadj = gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(app_state.scrolled_window));
                gtk_adjustment_set_value(vadj, 0.0);
            }
        }
        return;
    }

    GPtrArray *vis = get_sorted_visible_apps();
    if (vis->len > 0) {
        AppItem *first = g_ptr_array_index(vis, 0);
        gtk_list_box_select_row(box, GTK_LIST_BOX_ROW(first->row_widget));
        if (app_state.scrolled_window) {
            GtkAdjustment *vadj = gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(app_state.scrolled_window));
            gtk_adjustment_set_value(vadj, 0.0);
        }
    } else {
        gtk_list_box_unselect_all(box);
    }
    g_ptr_array_free(vis, TRUE);
}

static void navigate_list(GtkListBox *box, int direction) {
    const char *q = app_state.current_query;
    if (q && (*q == '!' || *q == '>')) {
        if (app_state.cmd_row) {
            gtk_list_box_select_row(box, GTK_LIST_BOX_ROW(app_state.cmd_row));
        }
        return;
    }

    GPtrArray *vis = get_sorted_visible_apps();
    if (vis->len == 0) {
        g_ptr_array_free(vis, TRUE);
        return;
    }

    GtkListBoxRow *cur_selected = gtk_list_box_get_selected_row(box);
    AppItem *cur_app = cur_selected ? g_object_get_data(G_OBJECT(cur_selected), "app_item") : NULL;
    gint cur_idx = -1;

    if (cur_app) {
        for (guint i = 0; i < vis->len; i++) {
            if (g_ptr_array_index(vis, i) == cur_app) {
                cur_idx = (gint)i;
                break;
            }
        }
    }

    gint target_idx;
    if (cur_idx < 0) {
        target_idx = (direction > 0) ? 0 : (gint)vis->len - 1;
    } else {
        target_idx = cur_idx + direction;
        if (target_idx < 0) target_idx = (gint)vis->len - 1;
        else if (target_idx >= (gint)vis->len) target_idx = 0;
    }

    AppItem *target_app = g_ptr_array_index(vis, target_idx);
    gtk_list_box_select_row(box, GTK_LIST_BOX_ROW(target_app->row_widget));

    if (app_state.scrolled_window) {
        GtkAdjustment *vadj = gtk_scrolled_window_get_vadjustment(GTK_SCROLLED_WINDOW(app_state.scrolled_window));
        GtkAllocation alloc;
        gtk_widget_get_allocation(target_app->row_widget, &alloc);
        gdouble cur_val = gtk_adjustment_get_value(vadj);
        gdouble page_sz = gtk_adjustment_get_page_size(vadj);

        if (alloc.y < cur_val) {
            gtk_adjustment_set_value(vadj, alloc.y);
        } else if (alloc.y + alloc.height > cur_val + page_sz) {
            gtk_adjustment_set_value(vadj, alloc.y + alloc.height - page_sz);
        }
    }

    g_ptr_array_free(vis, TRUE);
}

/* -------------------------------------------------------------------------
 * Desktop File Management (Visibility Toggling)
 * ------------------------------------------------------------------------- */
static gboolean set_desktop_file_visibility(const char *desktop_id, gboolean hide) {
    if (!desktop_id || !*desktop_id) return FALSE;

    char *user_dir = g_build_filename(g_get_user_data_dir(), "applications", NULL);
    g_mkdir_with_parents(user_dir, 0755);
    char *user_file = g_build_filename(user_dir, desktop_id, NULL);
    char *sys_file = g_build_filename("/usr/share/applications", desktop_id, NULL);

    gboolean has_user = g_file_test(user_file, G_FILE_TEST_EXISTS);
    gboolean has_sys = g_file_test(sys_file, G_FILE_TEST_EXISTS);

    if (hide) {
        GKeyFile *kf = g_key_file_new();
        gboolean loaded = FALSE;
        if (has_user) {
            loaded = g_key_file_load_from_file(kf, user_file,
                                                G_KEY_FILE_KEEP_COMMENTS | G_KEY_FILE_KEEP_TRANSLATIONS,
                                                NULL);
        } else if (has_sys) {
            loaded = g_key_file_load_from_file(kf, sys_file,
                                                G_KEY_FILE_KEEP_COMMENTS | G_KEY_FILE_KEEP_TRANSLATIONS,
                                                NULL);
        }

        if (!loaded) {
            g_key_file_set_string(kf, "Desktop Entry", "Type", "Application");
            g_key_file_set_string(kf, "Desktop Entry", "Name", desktop_id);
        }

        g_key_file_set_boolean(kf, "Desktop Entry", "NoDisplay", TRUE);
        g_key_file_save_to_file(kf, user_file, NULL);
        g_key_file_free(kf);
    } else {
        /* Unhide / Show */
        if (has_user) {
            gboolean sys_nodisplay = FALSE;
            if (has_sys) {
                GKeyFile *skf = g_key_file_new();
                if (g_key_file_load_from_file(skf, sys_file, G_KEY_FILE_NONE, NULL)) {
                    sys_nodisplay = g_key_file_get_boolean(skf, "Desktop Entry", "NoDisplay", NULL);
                }
                g_key_file_free(skf);
            }

            if (has_sys && !sys_nodisplay) {
                /* System default is visible. Check if user copy has no custom diffs */
                gboolean only_nodisplay_diff = TRUE;
                char *u_content = NULL, *s_content = NULL;
                if (g_file_get_contents(user_file, &u_content, NULL, NULL) &&
                    g_file_get_contents(sys_file, &s_content, NULL, NULL)) {
                    char **u_lines = g_strsplit(u_content, "\n", -1);
                    char **s_lines = g_strsplit(s_content, "\n", -1);
                    GString *u_clean = g_string_new("");
                    GString *s_clean = g_string_new("");

                    for (int i = 0; u_lines[i]; i++) {
                        char *t = g_strstrip(u_lines[i]);
                        if (t[0] && !g_ascii_strncasecmp(t, "nodisplay=", 10)) continue;
                        if (t[0]) g_string_append_printf(u_clean, "%s\n", t);
                    }
                    for (int i = 0; s_lines[i]; i++) {
                        char *t = g_strstrip(s_lines[i]);
                        if (t[0] && !g_ascii_strncasecmp(t, "nodisplay=", 10)) continue;
                        if (t[0]) g_string_append_printf(s_clean, "%s\n", t);
                    }

                    if (g_strcmp0(u_clean->str, s_clean->str) != 0) {
                        only_nodisplay_diff = FALSE;
                    }

                    g_string_free(u_clean, TRUE);
                    g_string_free(s_clean, TRUE);
                    g_strfreev(u_lines);
                    g_strfreev(s_lines);
                    g_free(u_content);
                    g_free(s_content);
                } else {
                    only_nodisplay_diff = FALSE;
                    g_free(u_content);
                    g_free(s_content);
                }

                if (only_nodisplay_diff) {
                    g_unlink(user_file);
                } else {
                    GKeyFile *kf = g_key_file_new();
                    if (g_key_file_load_from_file(kf, user_file,
                                                  G_KEY_FILE_KEEP_COMMENTS | G_KEY_FILE_KEEP_TRANSLATIONS,
                                                  NULL)) {
                        g_key_file_set_boolean(kf, "Desktop Entry", "NoDisplay", FALSE);
                        g_key_file_save_to_file(kf, user_file, NULL);
                    }
                    g_key_file_free(kf);
                }
            } else {
                /* User file is standalone or sys file has NoDisplay=true */
                GKeyFile *kf = g_key_file_new();
                if (g_key_file_load_from_file(kf, user_file,
                                              G_KEY_FILE_KEEP_COMMENTS | G_KEY_FILE_KEEP_TRANSLATIONS,
                                              NULL)) {
                    g_key_file_set_boolean(kf, "Desktop Entry", "NoDisplay", FALSE);
                    g_key_file_save_to_file(kf, user_file, NULL);
                }
                g_key_file_free(kf);
            }
        } else if (has_sys) {
            /* Sys file has NoDisplay=true and user file doesn't exist yet */
            GKeyFile *kf = g_key_file_new();
            if (g_key_file_load_from_file(kf, sys_file,
                                          G_KEY_FILE_KEEP_COMMENTS | G_KEY_FILE_KEEP_TRANSLATIONS,
                                          NULL)) {
                g_key_file_set_boolean(kf, "Desktop Entry", "NoDisplay", FALSE);
                g_key_file_save_to_file(kf, user_file, NULL);
            }
            g_key_file_free(kf);
        }
    }

    g_free(user_dir);
    g_free(user_file);
    g_free(sys_file);
    return TRUE;
}

/* -------------------------------------------------------------------------
 * Application Launch & Action Callbacks
 * ------------------------------------------------------------------------- */
static void launch_terminal_app(const char *cmdline, const char *fallback_exec) {
    gint argc = 0;
    gchar **argv = NULL;
    const char *src = (cmdline && *cmdline) ? cmdline : fallback_exec;
    if (!src || !*src) return;

    if (!g_shell_parse_argv(src, &argc, &argv, NULL)) {
        char *cmd = g_strdup_printf("alacritty -e %s &", src);
        g_spawn_command_line_async(cmd, NULL);
        g_free(cmd);
        return;
    }

    GPtrArray *clean_args = g_ptr_array_new();
    for (int i = 0; i < argc; i++) {
        if (argv[i][0] == '%' && strlen(argv[i]) <= 2) continue;
        g_ptr_array_add(clean_args, argv[i]);
    }
    if (clean_args->len > 0 && strcmp((char *)g_ptr_array_index(clean_args, clean_args->len - 1), "--") == 0) {
        g_ptr_array_remove_index(clean_args, clean_args->len - 1);
    }

    if (clean_args->len == 0) {
        if (fallback_exec && *fallback_exec) {
            g_ptr_array_add(clean_args, (gpointer)fallback_exec);
        } else {
            g_ptr_array_free(clean_args, TRUE);
            g_strfreev(argv);
            return;
        }
    }

    const char *first = (const char *)g_ptr_array_index(clean_args, 0);
    gboolean already_terminal = (strstr(first, "alacritty") != NULL ||
                                 strstr(first, "kitty") != NULL ||
                                 strstr(first, "xterm") != NULL);

    GPtrArray *final_argv = g_ptr_array_new();
    if (!already_terminal) {
        g_ptr_array_add(final_argv, (gpointer)"alacritty");
        g_ptr_array_add(final_argv, (gpointer)"-e");
    }
    for (guint i = 0; i < clean_args->len; i++) {
        g_ptr_array_add(final_argv, g_ptr_array_index(clean_args, i));
    }
    g_ptr_array_add(final_argv, NULL);

    g_spawn_async(NULL, (gchar **)final_argv->pdata, NULL,
                  G_SPAWN_SEARCH_PATH, NULL, NULL, NULL, NULL);

    g_ptr_array_free(final_argv, TRUE);
    g_ptr_array_free(clean_args, TRUE);
    g_strfreev(argv);
}

static void launch_app(AppItem *app) {
    if (!app) return;

    app->launch_count++;
    record_app_launch(app->id);

    if (app->is_terminal) {
        const char *cmdline = app->info ? g_app_info_get_commandline(app->info) : NULL;
        launch_terminal_app(cmdline, app->executable);
        safe_quit();
        return;
    }

    GError *err = NULL;
    GdkDisplay *disp = gdk_display_get_default();
    GdkAppLaunchContext *ctx = gdk_display_get_app_launch_context(disp);

    if (app->info && !g_app_info_launch(app->info, NULL, G_APP_LAUNCH_CONTEXT(ctx), &err)) {
        if (app->executable) {
            const char *cmdline = g_app_info_get_commandline(app->info);
            launch_terminal_app(cmdline, app->executable);
        }
        if (err) g_error_free(err);
    }
    if (ctx) g_object_unref(ctx);
    safe_quit();
}

static void toggle_app(AppItem *app, GtkListBox *box) {
    (void)box;
    if (!app) return;
    app->is_hidden = !app->is_hidden;
    set_desktop_file_visibility(app->id, app->is_hidden);

    /* Asynchronously update desktop database */
    g_spawn_command_line_async("update-desktop-database ~/.local/share/applications", NULL);

    /* Update UI badge */
    if (app->badge_label) {
        gtk_label_set_text(GTK_LABEL(app->badge_label), app->is_hidden ? "󰈉 Hidden" : "󰈈 Visible");
        GtkStyleContext *sc = gtk_widget_get_style_context(app->badge_label);
        if (app->is_hidden) {
            gtk_style_context_remove_class(sc, "badge-visible");
            gtk_style_context_add_class(sc, "badge-hidden");
        } else {
            gtk_style_context_remove_class(sc, "badge-hidden");
            gtk_style_context_add_class(sc, "badge-visible");
        }
    }
}

static void hide_app_from_launcher(AppItem *app, GtkListBox *box) {
    if (!app) return;
    app->is_hidden = TRUE;
    set_desktop_file_visibility(app->id, TRUE);

    /* Notification feedback */
    char *cmd = g_strdup_printf("sys-notif 'Launcher' 'Hidden %s from launcher' 2>/dev/null || notify-send -a sys-launcher 'Launcher' 'Hidden %s from launcher' 2>/dev/null &",
                                app->name ? app->name : app->id,
                                app->name ? app->name : app->id);
    g_spawn_command_line_async(cmd, NULL);
    g_free(cmd);

    g_spawn_command_line_async("update-desktop-database ~/.local/share/applications", NULL);

    gtk_list_box_invalidate_filter(box);
    select_first_visible_row(box);
}

static void on_search_changed(GtkSearchEntry *entry, gpointer user_data) {
    (void)user_data;
    g_free(app_state.current_query);
    app_state.current_query = g_strdup(gtk_entry_get_text(GTK_ENTRY(entry)));

    const char *q = app_state.current_query;
    if (q && (*q == '!' || *q == '>')) {
        const char *cmd = q + 1;
        while (*cmd == ' ' || *cmd == '\t') cmd++;
        char *title = g_strdup_printf("Execute: %s", cmd);
        gtk_label_set_text(GTK_LABEL(app_state.cmd_title_label), title);
        g_free(title);
        if (app_state.footer_hint) {
            gtk_label_set_text(GTK_LABEL(app_state.footer_hint), "↵ Execute in shell   •   Esc Close");
        }
    } else {
        if (app_state.footer_hint) {
            gtk_label_set_text(GTK_LABEL(app_state.footer_hint),
                app_state.is_toggle_mode ?
                "↵ / Space Toggle Visibility   •   Esc Close" :
                "↵ Launch   •   Tab Hide   •   Esc Close");
        }
    }

    gtk_list_box_invalidate_filter(GTK_LIST_BOX(app_state.listbox));
    gtk_list_box_invalidate_sort(GTK_LIST_BOX(app_state.listbox));
    select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
}

static void on_row_activated(GtkListBox *box, GtkListBoxRow *row, gpointer user_data) {
    (void)user_data;
    if (app_state.cmd_row && row == GTK_LIST_BOX_ROW(app_state.cmd_row)) {
        execute_shell_command();
        return;
    }
    AppItem *app = g_object_get_data(G_OBJECT(row), "app_item");
    if (!app) return;
    if (app_state.is_toggle_mode) {
        toggle_app(app, box);
    } else {
        launch_app(app);
    }
}

static void on_entry_activate(GtkEntry *entry, gpointer user_data) {
    (void)entry;
    (void)user_data;
    const char *q = app_state.current_query;
    if (q && (*q == '!' || *q == '>')) {
        execute_shell_command();
        return;
    }
    GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
    AppItem *app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
    if (!app || !app_matches_query(app, app_state.current_query)) {
        select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
        row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
        app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
    }
    if (app) {
        if (app_state.is_toggle_mode) {
            toggle_app(app, GTK_LIST_BOX(app_state.listbox));
        } else {
            launch_app(app);
        }
    }
}

static gboolean on_row_enter_notify(GtkWidget *widget, GdkEventCrossing *event, gpointer user_data) {
    (void)event;
    GtkListBox *box = GTK_LIST_BOX(user_data);
    gtk_list_box_select_row(box, GTK_LIST_BOX_ROW(widget));
    return GDK_EVENT_PROPAGATE;
}

static gboolean on_window_focus_out(GtkWidget *widget, GdkEventFocus *event, gpointer user_data) {
    (void)widget;
    (void)event;
    (void)user_data;
    safe_quit();
    return GDK_EVENT_STOP;
}

static gboolean on_window_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    (void)widget;
    (void)user_data;
    guint keyval = event->keyval;
    guint state = event->state & (GDK_CONTROL_MASK | GDK_SHIFT_MASK | GDK_MOD1_MASK);

    if (keyval == GDK_KEY_Escape) {
        safe_quit();
        return GDK_EVENT_STOP;
    }

    /* Down / Ctrl+N */
    if (keyval == GDK_KEY_Down || (keyval == GDK_KEY_n && (state & GDK_CONTROL_MASK))) {
        navigate_list(GTK_LIST_BOX(app_state.listbox), 1);
        return GDK_EVENT_STOP;
    }

    /* Up / Ctrl+P */
    if (keyval == GDK_KEY_Up || (keyval == GDK_KEY_p && (state & GDK_CONTROL_MASK))) {
        navigate_list(GTK_LIST_BOX(app_state.listbox), -1);
        return GDK_EVENT_STOP;
    }

    /* Enter / KP_Enter */
    if (keyval == GDK_KEY_Return || keyval == GDK_KEY_KP_Enter) {
        const char *q = app_state.current_query;
        if (q && (*q == '!' || *q == '>')) {
            execute_shell_command();
            return GDK_EVENT_STOP;
        }
        GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
        AppItem *app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
        if (!app || !app_matches_query(app, app_state.current_query)) {
            select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
            row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
            app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
        }
        if (app) {
            if (app_state.is_toggle_mode) {
                toggle_app(app, GTK_LIST_BOX(app_state.listbox));
            } else {
                launch_app(app);
            }
        }
        return GDK_EVENT_STOP;
    }

    /* Space in toggle mode */
    if (app_state.is_toggle_mode && (keyval == GDK_KEY_space || keyval == GDK_KEY_KP_Space)) {
        const char *q = app_state.current_query;
        if (q && (*q == '!' || *q == '>')) {
            return GDK_EVENT_PROPAGATE;
        }
        const char *text = gtk_entry_get_text(GTK_ENTRY(app_state.entry));
        gboolean entry_focused = gtk_widget_has_focus(GTK_WIDGET(app_state.entry));
        if (!entry_focused || !text || text[0] == '\0' || (state & GDK_CONTROL_MASK)) {
            GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
            AppItem *app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
            if (!app || !app_matches_query(app, app_state.current_query)) {
                select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
                row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
                app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
            }
            if (app) {
                toggle_app(app, GTK_LIST_BOX(app_state.listbox));
            }
            return GDK_EVENT_STOP;
        }
    }

    /* Tab in launcher mode */
    if (!app_state.is_toggle_mode && keyval == GDK_KEY_Tab) {
        const char *q = app_state.current_query;
        if (q && (*q == '!' || *q == '>')) {
            return GDK_EVENT_STOP;
        }
        GtkListBoxRow *row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
        AppItem *app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
        if (!app || !app_matches_query(app, app_state.current_query)) {
            select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
            row = gtk_list_box_get_selected_row(GTK_LIST_BOX(app_state.listbox));
            app = row ? g_object_get_data(G_OBJECT(row), "app_item") : NULL;
        }
        if (app) {
            hide_app_from_launcher(app, GTK_LIST_BOX(app_state.listbox));
        }
        return GDK_EVENT_STOP;
    }

    return GDK_EVENT_PROPAGATE;
}

/* -------------------------------------------------------------------------
 * Embedded CSS Styling (Catppuccin Mocha / Dracula Palette)
 * ------------------------------------------------------------------------- */
static void load_css(void) {
    GtkCssProvider *provider = gtk_css_provider_new();
    const char *css =
        "window {\n"
        "  background-color: #1e1e2e;\n"
        "  border: 1.5px solid #bd93f9;\n"
        "  border-radius: 12px;\n"
        "}\n"
        "#main-box {\n"
        "  padding: 12px;\n"
        "}\n"
        "entry {\n"
        "  background-color: #282a36;\n"
        "  border: 1px solid #44475a;\n"
        "  border-radius: 8px;\n"
        "  color: #f8f8f2;\n"
        "  font-family: 'JetBrainsMono Nerd Font', monospace;\n"
        "  font-size: 12pt;\n"
        "  padding: 8px 12px;\n"
        "  margin-bottom: 8px;\n"
        "}\n"
        "entry:focus {\n"
        "  border-color: #bd93f9;\n"
        "}\n"
        "scrolledwindow {\n"
        "  background-color: transparent;\n"
        "  border: none;\n"
        "}\n"
        "list {\n"
        "  background-color: transparent;\n"
        "}\n"
        "row {\n"
        "  border-radius: 6px;\n"
        "  padding: 6px 10px;\n"
        "  margin: 2px 0px;\n"
        "  background-color: transparent;\n"
        "  color: #f8f8f2;\n"
        "}\n"
        "row:hover {\n"
        "  background-color: #282a36;\n"
        "}\n"
        "row:selected, row:selected:focus {\n"
        "  background-color: #bd93f9;\n"
        "  color: #1e1e2e;\n"
        "}\n"
        ".app-title {\n"
        "  font-weight: bold;\n"
        "  font-size: 11pt;\n"
        "  color: #f8f8f2;\n"
        "}\n"
        "row:selected .app-title {\n"
        "  color: #1e1e2e;\n"
        "}\n"
        ".app-subtitle {\n"
        "  font-size: 9pt;\n"
        "  color: #6272a4;\n"
        "}\n"
        "row:selected .app-subtitle {\n"
        "  color: #44475a;\n"
        "}\n"
        ".badge-visible {\n"
        "  font-size: 10pt;\n"
        "  color: #50fa7b;\n"
        "  font-weight: bold;\n"
        "  padding: 2px 8px;\n"
        "}\n"
        "row:selected .badge-visible {\n"
        "  color: #1e1e2e;\n"
        "}\n"
        ".badge-hidden {\n"
        "  font-size: 10pt;\n"
        "  color: #ff5555;\n"
        "  font-weight: bold;\n"
        "  padding: 2px 8px;\n"
        "}\n"
        "row:selected .badge-hidden {\n"
        "  color: #44475a;\n"
        "}\n"
        ".footer-bar {\n"
        "  border-top: 1px solid #282a36;\n"
        "  padding-top: 6px;\n"
        "  margin-top: 6px;\n"
        "}\n"
        ".footer-hint {\n"
        "  font-size: 8.5pt;\n"
        "  color: #6272a4;\n"
        "  font-family: 'JetBrainsMono Nerd Font', monospace;\n"
        "}\n"
        "scrollbar slider {\n"
        "  background-color: #44475a;\n"
        "  border-radius: 4px;\n"
        "  min-width: 5px;\n"
        "  min-height: 5px;\n"
        "}\n"
        "scrollbar slider:hover {\n"
        "  background-color: #bd93f9;\n"
        "}\n"
        "scrollbar trough {\n"
        "  background-color: transparent;\n"
        "}\n";

    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    GdkScreen *screen = gdk_screen_get_default();
    gtk_style_context_add_provider_for_screen(screen,
                                              GTK_STYLE_PROVIDER(provider),
                                              GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(provider);
}

/* -------------------------------------------------------------------------
 * Memory Cleanup
 * ------------------------------------------------------------------------- */
static void free_app_item(AppItem *app) {
    if (!app) return;
    g_free(app->id);
    g_free(app->name);
    g_free(app->comment);
    g_free(app->executable);
    g_free(app->lower_name);
    g_free(app->lower_comment);
    g_free(app->lower_exec);
    g_free(app->lower_id);
    g_free(app->norm_name);
    g_free(app->norm_id);
    g_free(app->norm_exec);
    if (app->icon) {
        g_object_unref(app->icon);
        app->icon = NULL;
    }
    if (app->info) {
        g_object_unref(app->info);
        app->info = NULL;
    }
    g_free(app);
}

static void free_apps(void) {
    if (app_state.apps) {
        for (guint i = 0; i < app_state.apps->len; i++) {
            AppItem *app = g_ptr_array_index(app_state.apps, i);
            free_app_item(app);
        }
        g_ptr_array_free(app_state.apps, TRUE);
        app_state.apps = NULL;
    }
    g_free(app_state.current_query);
    app_state.current_query = NULL;
}

/* -------------------------------------------------------------------------
 * Application Model Population
 * ------------------------------------------------------------------------- */
static void populate_apps(void) {
    app_state.apps = g_ptr_array_new();
    GList *all = g_app_info_get_all();

    for (GList *l = all; l != NULL; l = l->next) {
        GAppInfo *info = G_APP_INFO(l->data);
        if (!info) continue;

        const char *id = g_app_info_get_id(info);
        if (!id || !*id) continue;

        const char *name = g_app_info_get_name(info);
        if (!name || !*name) name = id;

        const char *desc = g_app_info_get_description(info);
        const char *exec = g_app_info_get_executable(info);
        GIcon *icon = g_app_info_get_icon(info);
        gboolean should_show = g_app_info_should_show(info);
        gboolean is_nodisplay = FALSE;
        gboolean is_hidden_field = FALSE;
        gboolean is_terminal = FALSE;

        if (G_IS_DESKTOP_APP_INFO(info)) {
            GDesktopAppInfo *dinfo = G_DESKTOP_APP_INFO(info);
            is_nodisplay = g_desktop_app_info_get_nodisplay(dinfo);
            is_hidden_field = g_desktop_app_info_get_is_hidden(dinfo);
            is_terminal = g_desktop_app_info_get_boolean(dinfo, "Terminal");
            if (!is_terminal) {
                char *term_val = g_desktop_app_info_get_string(dinfo, "Terminal");
                if (term_val) {
                    if (g_ascii_strcasecmp(term_val, "true") == 0 || g_ascii_strcasecmp(term_val, "1") == 0) {
                        is_terminal = TRUE;
                    }
                    g_free(term_val);
                }
            }
        }

        gboolean is_hidden = (!should_show || is_nodisplay || is_hidden_field);

        /* In launcher mode, omit hidden applications */
        if (!app_state.is_toggle_mode && is_hidden) {
            continue;
        }

        AppItem *app = g_new0(AppItem, 1);
        app->id = g_strdup(id);
        gpointer f_val = frecency_map ? g_hash_table_lookup(frecency_map, id) : NULL;
        app->launch_count = f_val ? GPOINTER_TO_UINT(f_val) : 0;
        app->name = g_strdup(name);
        app->comment = g_strdup(desc ? desc : "");
        app->executable = g_strdup(exec ? exec : "");
        app->lower_name = g_ascii_strdown(app->name, -1);
        app->lower_comment = g_ascii_strdown(app->comment, -1);
        app->lower_exec = g_ascii_strdown(app->executable, -1);
        app->lower_id = g_ascii_strdown(app->id, -1);
        app->norm_name = normalize_str(app->lower_name);
        app->norm_exec = normalize_str(app->lower_exec);
        app->norm_id = normalize_str(app->lower_id);
        app->is_hidden = is_hidden;
        app->is_terminal = is_terminal;
        app->info = g_object_ref(info);
        if (icon) app->icon = g_object_ref(icon);

        /* Create UI Row */
        GtkWidget *row = gtk_list_box_row_new();
        GtkWidget *hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);

        /* Icon (32x32) */
        GtkWidget *icon_img;
        if (app->icon) {
            icon_img = gtk_image_new_from_gicon(app->icon, GTK_ICON_SIZE_DND);
        } else {
            icon_img = gtk_image_new_from_icon_name("application-x-executable", GTK_ICON_SIZE_DND);
        }
        gtk_image_set_pixel_size(GTK_IMAGE(icon_img), 32);
        gtk_box_pack_start(GTK_BOX(hbox), icon_img, FALSE, FALSE, 0);

        /* Text Box */
        GtkWidget *vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
        GtkWidget *title_lbl = gtk_label_new(app->name);
        gtk_label_set_xalign(GTK_LABEL(title_lbl), 0.0);
        gtk_label_set_ellipsize(GTK_LABEL(title_lbl), PANGO_ELLIPSIZE_END);
        gtk_style_context_add_class(gtk_widget_get_style_context(title_lbl), "app-title");
        gtk_box_pack_start(GTK_BOX(vbox), title_lbl, FALSE, FALSE, 0);

        const char *sub = (app->comment && *app->comment) ? app->comment :
                          ((app->executable && *app->executable) ? app->executable : app->id);
        GtkWidget *sub_lbl = gtk_label_new(sub);
        gtk_label_set_xalign(GTK_LABEL(sub_lbl), 0.0);
        gtk_label_set_ellipsize(GTK_LABEL(sub_lbl), PANGO_ELLIPSIZE_END);
        gtk_style_context_add_class(gtk_widget_get_style_context(sub_lbl), "app-subtitle");
        gtk_box_pack_start(GTK_BOX(vbox), sub_lbl, FALSE, FALSE, 0);
        app->subtitle_label = sub_lbl;

        gtk_box_pack_start(GTK_BOX(hbox), vbox, TRUE, TRUE, 0);

        /* Badge for Toggle Mode */
        if (app_state.is_toggle_mode) {
            GtkWidget *badge = gtk_label_new(app->is_hidden ? "󰈉 Hidden" : "󰈈 Visible");
            gtk_style_context_add_class(gtk_widget_get_style_context(badge),
                                        app->is_hidden ? "badge-hidden" : "badge-visible");
            gtk_box_pack_end(GTK_BOX(hbox), badge, FALSE, FALSE, 4);
            app->badge_label = badge;
        }

        gtk_container_add(GTK_CONTAINER(row), hbox);
        app->row_widget = row;
        g_object_set_data(G_OBJECT(row), "app_item", app);

        /* Hover selection */
        gtk_widget_add_events(row, GDK_ENTER_NOTIFY_MASK);
        g_signal_connect(row, "enter-notify-event", G_CALLBACK(on_row_enter_notify), app_state.listbox);

        gtk_list_box_insert(GTK_LIST_BOX(app_state.listbox), row, -1);
        g_ptr_array_add(app_state.apps, app);
    }

    g_list_free_full(all, g_object_unref);
}

static gboolean on_window_map(GtkWidget *widget, GdkEvent *event, gpointer user_data) {
    (void)event;
    (void)user_data;
    position_window_on_active_monitor(GTK_WINDOW(widget), 480, 420);
    return GDK_EVENT_PROPAGATE;
}

/* -------------------------------------------------------------------------
 * UI Initialization
 * ------------------------------------------------------------------------- */
static void build_ui(void) {
    load_css();

    app_state.window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(app_state.window),
                         app_state.is_toggle_mode ? "sys-launcher --toggle" : "sys-launcher");
    gtk_window_set_decorated(GTK_WINDOW(app_state.window), FALSE);
    gtk_window_set_position(GTK_WINDOW(app_state.window), GTK_WIN_POS_NONE);
    gtk_window_set_default_size(GTK_WINDOW(app_state.window), 480, 420);
    gtk_widget_set_size_request(app_state.window, 480, 420);
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(app_state.window), TRUE);
    gtk_window_set_skip_pager_hint(GTK_WINDOW(app_state.window), TRUE);
    gtk_window_set_type_hint(GTK_WINDOW(app_state.window), GDK_WINDOW_TYPE_HINT_DIALOG);

    GdkScreen *screen = gtk_widget_get_screen(app_state.window);
    GdkVisual *visual = gdk_screen_get_rgba_visual(screen);
    if (visual && gdk_screen_is_composited(screen)) {
        gtk_widget_set_visual(app_state.window, visual);
    }
    gtk_widget_set_app_paintable(app_state.window, TRUE);

    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_widget_set_name(main_box, "main-box");
    gtk_container_add(GTK_CONTAINER(app_state.window), main_box);

    /* Search entry */
    app_state.entry = gtk_search_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(app_state.entry),
        app_state.is_toggle_mode ? "Search apps to toggle (Enter/Space toggles)..." : "Search applications or !/> for shell...");
    gtk_box_pack_start(GTK_BOX(main_box), app_state.entry, FALSE, FALSE, 0);

    /* Scrolled Window & ListBox */
    app_state.scrolled_window = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(app_state.scrolled_window),
                                   GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_vexpand(app_state.scrolled_window, TRUE);
    gtk_box_pack_start(GTK_BOX(main_box), app_state.scrolled_window, TRUE, TRUE, 0);

    app_state.listbox = gtk_list_box_new();
    gtk_list_box_set_selection_mode(GTK_LIST_BOX(app_state.listbox), GTK_SELECTION_BROWSE);
    gtk_list_box_set_activate_on_single_click(GTK_LIST_BOX(app_state.listbox), TRUE);
    gtk_container_add(GTK_CONTAINER(app_state.scrolled_window), app_state.listbox);

    gtk_list_box_set_filter_func(GTK_LIST_BOX(app_state.listbox), filter_func, NULL, NULL);
    gtk_list_box_set_sort_func(GTK_LIST_BOX(app_state.listbox), sort_func, NULL, NULL);

    /* Dedicated dynamic custom row for shell commands (! or >) */
    GtkWidget *cmd_row = gtk_list_box_row_new();
    GtkWidget *cmd_hbox = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);

    GtkIconTheme *theme = gtk_icon_theme_get_default();
    const char *icon_name = (theme && gtk_icon_theme_has_icon(theme, "utilities-terminal")) ?
                            "utilities-terminal" : "terminal";
    GtkWidget *cmd_icon_img = gtk_image_new_from_icon_name(icon_name, GTK_ICON_SIZE_DND);
    gtk_image_set_pixel_size(GTK_IMAGE(cmd_icon_img), 32);
    gtk_box_pack_start(GTK_BOX(cmd_hbox), cmd_icon_img, FALSE, FALSE, 0);

    GtkWidget *cmd_vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 2);
    app_state.cmd_title_label = gtk_label_new("Execute: ");
    gtk_label_set_xalign(GTK_LABEL(app_state.cmd_title_label), 0.0);
    gtk_label_set_ellipsize(GTK_LABEL(app_state.cmd_title_label), PANGO_ELLIPSIZE_END);
    gtk_style_context_add_class(gtk_widget_get_style_context(app_state.cmd_title_label), "app-title");
    gtk_box_pack_start(GTK_BOX(cmd_vbox), app_state.cmd_title_label, FALSE, FALSE, 0);

    app_state.cmd_subtitle_label = gtk_label_new("Run in system shell");
    gtk_label_set_xalign(GTK_LABEL(app_state.cmd_subtitle_label), 0.0);
    gtk_label_set_ellipsize(GTK_LABEL(app_state.cmd_subtitle_label), PANGO_ELLIPSIZE_END);
    gtk_style_context_add_class(gtk_widget_get_style_context(app_state.cmd_subtitle_label), "app-subtitle");
    gtk_box_pack_start(GTK_BOX(cmd_vbox), app_state.cmd_subtitle_label, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(cmd_hbox), cmd_vbox, TRUE, TRUE, 0);
    gtk_container_add(GTK_CONTAINER(cmd_row), cmd_hbox);

    app_state.cmd_row = cmd_row;
    gtk_widget_add_events(cmd_row, GDK_ENTER_NOTIFY_MASK);
    g_signal_connect(cmd_row, "enter-notify-event", G_CALLBACK(on_row_enter_notify), app_state.listbox);

    gtk_list_box_insert(GTK_LIST_BOX(app_state.listbox), cmd_row, -1);

    /* Footer hints */
    GtkWidget *footer = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_style_context_add_class(gtk_widget_get_style_context(footer), "footer-bar");
    app_state.footer_hint = gtk_label_new(
        app_state.is_toggle_mode ?
        "↵ / Space Toggle Visibility   •   Esc Close" :
        "↵ Launch   •   Tab Hide   •   Esc Close"
    );
    gtk_style_context_add_class(gtk_widget_get_style_context(app_state.footer_hint), "footer-hint");
    gtk_box_pack_start(GTK_BOX(footer), app_state.footer_hint, TRUE, TRUE, 0);
    gtk_box_pack_end(GTK_BOX(main_box), footer, FALSE, FALSE, 0);

    /* Populate list */
    populate_apps();

    /* Signal handlers */
    g_signal_connect(app_state.entry, "search-changed", G_CALLBACK(on_search_changed), NULL);
    g_signal_connect(app_state.entry, "activate", G_CALLBACK(on_entry_activate), NULL);
    g_signal_connect(app_state.window, "key-press-event", G_CALLBACK(on_window_key_press), NULL);
    g_signal_connect(app_state.listbox, "row-activated", G_CALLBACK(on_row_activated), NULL);
    g_signal_connect(app_state.window, "map-event", G_CALLBACK(on_window_map), NULL);
    g_signal_connect(app_state.window, "destroy", G_CALLBACK(safe_quit), NULL);

    /* Focus-Out Auto-Dismiss */
    gtk_widget_add_events(app_state.window, GDK_FOCUS_CHANGE_MASK);
    g_signal_connect(app_state.window, "focus-out-event", G_CALLBACK(on_window_focus_out), NULL);

    position_window_on_active_monitor(GTK_WINDOW(app_state.window), 480, 420);
    gtk_widget_show_all(app_state.window);
    position_window_on_active_monitor(GTK_WINDOW(app_state.window), 480, 420);

    gtk_widget_grab_focus(app_state.entry);
    select_first_visible_row(GTK_LIST_BOX(app_state.listbox));
}

/* -------------------------------------------------------------------------
 * Usage and Entry Point
 * ------------------------------------------------------------------------- */
static void print_usage(void) {
    printf("sys-launcher %s - High-Performance Native C/GTK3 Application Launcher\n\n", VERSION);
    printf("Usage:\n");
    printf("  sys-launcher [OPTIONS]\n\n");
    printf("Options:\n");
    printf("  -t, --toggle    Launch in App Toggle Manager mode (list all apps & toggle NoDisplay)\n");
    printf("  -h, --help      Display this help message and exit\n");
    printf("  -v, --version   Display version information and exit\n\n");
    printf("Keybindings:\n");
    printf("  <Up> / <Down>   Navigate results (also <Ctrl+P> / <Ctrl+N>)\n");
    printf("  <Enter>         Launch selected app (or execute shell command with ! or >)\n");
    printf("  <Space>         Toggle visibility in --toggle mode\n");
    printf("  <Tab>           Hide application from launcher (in default launcher mode)\n");
    printf("  <Escape>        Close launcher immediately\n\n");
    printf("Shell Command Execution:\n");
    printf("  !<command>      Execute shell command (e.g. !reboot, !alacritty)\n");
    printf("  ><command>      Execute shell command (e.g. >pkill firefox)\n");
}

#ifndef SYS_LAUNCHER_TEST
int main(int argc, char **argv) {
    if (argc >= 2) {
        if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
            print_usage();
            return 0;
        }
        if (strcmp(argv[1], "--version") == 0 || strcmp(argv[1], "-v") == 0) {
            printf("sys-launcher %s\n", VERSION);
            return 0;
        }
        if (strcmp(argv[1], "--toggle") == 0 || strcmp(argv[1], "-t") == 0) {
            app_state.is_toggle_mode = TRUE;
        }
    }

    gtk_init(&argc, &argv);
    init_frecency();
    build_ui();
    gtk_main();
    free_apps();
    free_frecency();

    return 0;
}
#endif
