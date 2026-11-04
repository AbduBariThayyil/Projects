#define _GNU_SOURCE
#include <gio/gio.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/file.h>
#include <sys/stat.h>

#define LAUNCH_CMD   "QtMusicLauncher"
#define CLOSE_CMD    "qt-music --quit 2>/dev/null || lyricview --quit 2>/dev/null || playerctl -p qt-music,lyricview,lollypop quit 2>/dev/null"
#define PLAYER_PARAM "qt-music,lyricview,lollypop"

#define FIFO_PATH    "/tmp/polybar_music.fifo"
#define LOCK_PATH    "/tmp/polybar_music.lock"

#define TITLE_MAX_CHARS  16
#define BAR_CHARS        8
#define TOTAL_WIDTH      54

static const char *FACES[] = {
    "(•‿•)",
    "(^‿^)",
    "(¬‿¬)",
    "(◕‿◕)",
    "(o_o)",
    "(°‿°)"
};
#define NUM_FACES (sizeof(FACES) / sizeof(FACES[0]))

static GMainLoop *main_loop = NULL;
static GDBusConnection *dbus_conn = NULL;
static guint watcher_qtmusic = 0;
static guint watcher_lyricview = 0;
static guint watcher_lollypop = 0;
static guint prop_sub_id = 0;
static guint seeked_sub_id = 0;
static guint tick_timer_id = 0;
static guint startup_timer_id = 0;
static int lock_fd = -1;

static char active_bus_name[128] = {0};
static gboolean is_player_active = FALSE;
static char current_status[32] = "Stopped";
static char current_title[256] = "Unknown";
static char current_artist[256] = "";
static gint64 current_pos_us = 0;
static gint64 current_len_us = 0;
static time_t last_sync_time = 0;
static int face_idx = 0;

static void notify_polybar(const char *action) {
    if (!action || !*action) return;
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "polybar-msg action \"%s\" >/dev/null 2>&1", action);
    g_spawn_command_line_async(cmd, NULL);
}

/* Clear the Polybar music output */
static void render_clear(void) {
    printf("\n");
    fflush(stdout);
}

/* Output the padded 'No Music' view */
static void render_no_music(void) {
    const char *txt = "(•‿•) No Music";
    int txt_len = g_utf8_strlen(txt, -1);
    int pad = TOTAL_WIDTH - txt_len;
    if (pad < 0) pad = 0;

    printf("%%{O45}%%{A1:%s:}%%{F#4c566a}%s%%{F-}%%{A}%*s\n", LAUNCH_CMD, txt, pad, "");
    fflush(stdout);
}

/* Render active playback view with progress bar and animations */
static void render_active_music(void) {
    if (!is_player_active || strcmp(current_status, "Stopped") == 0) {
        render_no_music();
        return;
    }

    gboolean is_playing = (strcmp(current_status, "Playing") == 0);
    const char *play_icon = is_playing ? "󰏤" : "󰐊";
    const char *face = is_playing ? FACES[face_idx % NUM_FACES] : "(•‿•)";

    /* Calculate current position taking elapsed time into account */
    gint64 pos_sec = current_pos_us / 1000000;
    if (is_playing && last_sync_time > 0) {
        time_t now = time(NULL);
        pos_sec += (now - last_sync_time);
    }
    gint64 total_sec = current_len_us / 1000000;
    if (total_sec > 0 && pos_sec > total_sec) {
        pos_sec = total_sec;
    }
    if (pos_sec < 0) pos_sec = 0;

    /* Build time string: 'MM:SS/MM:SS' */
    char time_str[64];
    snprintf(time_str, sizeof(time_str), "%2lld:%02lld/%2lld:%02lld",
             (long long)(pos_sec / 60), (long long)(pos_sec % 60),
             (long long)(total_sec / 60), (long long)(total_sec % 60));

    /* Build progress bar: e.g. ━━━───── */
    int filled = 0;
    if (total_sec > 0) {
        filled = (int)((pos_sec * BAR_CHARS) / total_sec);
        if (filled > BAR_CHARS) filled = BAR_CHARS;
    }
    char bar_str[64] = {0};
    for (int i = 0; i < BAR_CHARS; i++) {
        strcat(bar_str, (i < filled) ? "━" : "─");
    }

    /* Clean and truncate title in UTF-8 */
    char clean_title[256];
    g_strlcpy(clean_title, current_title, sizeof(clean_title));
    char *p = clean_title;
    while ((p = strstr(p, "%{")) != NULL) {
        *p = ' ';
    }
    g_strstrip(clean_title);

    int title_chars = g_utf8_strlen(clean_title, -1);
    char title_fixed[512] = {0};
    if (title_chars > TITLE_MAX_CHARS) {
        /* Truncate and add ellipsis */
        gchar *trunc = g_utf8_substring(clean_title, 0, TITLE_MAX_CHARS - 1);
        snprintf(title_fixed, sizeof(title_fixed), "%s…", trunc);
        g_free(trunc);
    } else {
        snprintf(title_fixed, sizeof(title_fixed), "%s", clean_title);
        int pad = TITLE_MAX_CHARS - title_chars;
        while (pad-- > 0 && strlen(title_fixed) < sizeof(title_fixed) - 2) {
            strcat(title_fixed, " ");
        }
    }

    /* Print fully formatted Polybar interactive line */
    printf("%%{O45}"
           "%%{A4:playerctl -p %s position 5+:}"
           "%%{A5:playerctl -p %s position 5-:}"
           "%%{A3:qt-music --toggle:}"
           "%%{A1:%s:}%%{F#bd93f9}%s%%{F-}  %%{F#f8f8f2}%s%%{F-}%%{A}  "
           "%%{F#50fa7b}%%{A1:playerctl -p %s play-pause:}%s%%{A}%%{F-} "
           "%%{F#8be9fd}%%{A1:playerctl -p %s previous:}󰒮%%{A}%%{F-} "
           "%%{A1:%s:}%%{F#bd93f9}%s%%{F-} %%{F#ff79c6}%s%%{F-}%%{A} "
           "%%{F#8be9fd}%%{A1:playerctl -p %s next:}󰒭%%{A}%%{F-}  "
           "%%{F#ff5555}%%{A1:%s:}󰅖%%{A}%%{F-}"
           "%%{A}%%{A}%%{A}\n",
           PLAYER_PARAM,
           PLAYER_PARAM,
           LAUNCH_CMD, face, title_fixed,
           PLAYER_PARAM, play_icon,
           PLAYER_PARAM,
           LAUNCH_CMD, time_str, bar_str,
           PLAYER_PARAM,
           CLOSE_CMD);
    fflush(stdout);
}

/* 1-second tick when playing */
static gboolean on_play_tick(gpointer user_data) {
    (void)user_data;
    if (is_player_active && strcmp(current_status, "Playing") == 0) {
        face_idx++;
        render_active_music();
        return G_SOURCE_CONTINUE;
    }
    tick_timer_id = 0;
    return G_SOURCE_REMOVE;
}

static void sync_tick_timer(void) {
    if (is_player_active && strcmp(current_status, "Playing") == 0) {
        if (tick_timer_id == 0) {
            tick_timer_id = g_timeout_add_seconds(1, on_play_tick, NULL);
        }
    } else {
        if (tick_timer_id > 0) {
            g_source_remove(tick_timer_id);
            tick_timer_id = 0;
        }
    }
}

/* Parse MPRIS metadata dictionary */
static void parse_metadata(GVariant *dict) {
    if (!dict) return;

    GVariantIter iter;
    g_variant_iter_init(&iter, dict);
    const gchar *key;
    GVariant *val;

    while (g_variant_iter_next(&iter, "{&sv}", &key, &val)) {
        if (strcmp(key, "xesam:title") == 0) {
            const char *t = g_variant_get_string(val, NULL);
            if (t && *t) {
                g_strlcpy(current_title, t, sizeof(current_title));
            }
        } else if (strcmp(key, "xesam:artist") == 0) {
            if (g_variant_is_of_type(val, G_VARIANT_TYPE("as"))) {
                GVariantIter aiter;
                g_variant_iter_init(&aiter, val);
                const char *artist_item;
                if (g_variant_iter_next(&aiter, "&s", &artist_item)) {
                    g_strlcpy(current_artist, artist_item, sizeof(current_artist));
                }
            } else if (g_variant_is_of_type(val, G_VARIANT_TYPE_STRING)) {
                g_strlcpy(current_artist, g_variant_get_string(val, NULL), sizeof(current_artist));
            }
        } else if (strcmp(key, "mpris:length") == 0) {
            if (g_variant_is_of_type(val, G_VARIANT_TYPE_INT64)) {
                current_len_us = g_variant_get_int64(val);
            }
        }
        g_variant_unref(val);
    }
}

/* Fetch complete player state over D-Bus */
static void fetch_player_state(void) {
    if (!dbus_conn || active_bus_name[0] == '\0') return;

    GError *err = NULL;
    GVariant *res = g_dbus_connection_call_sync(
        dbus_conn,
        active_bus_name,
        "/org/mpris/MediaPlayer2",
        "org.freedesktop.DBus.Properties",
        "GetAll",
        g_variant_new("(s)", "org.mpris.MediaPlayer2.Player"),
        G_VARIANT_TYPE("(a{sv})"),
        G_DBUS_CALL_FLAGS_NONE,
        500,
        NULL,
        &err
    );

    if (err) {
        g_clear_error(&err);
        return;
    }

    GVariant *dict = g_variant_get_child_value(res, 0);
    GVariantIter iter;
    g_variant_iter_init(&iter, dict);
    const gchar *prop_name;
    GVariant *prop_val;

    while (g_variant_iter_next(&iter, "{&sv}", &prop_name, &prop_val)) {
        if (strcmp(prop_name, "PlaybackStatus") == 0) {
            g_strlcpy(current_status, g_variant_get_string(prop_val, NULL), sizeof(current_status));
        } else if (strcmp(prop_name, "Position") == 0) {
            current_pos_us = g_variant_get_int64(prop_val);
            last_sync_time = time(NULL);
        } else if (strcmp(prop_name, "Metadata") == 0) {
            parse_metadata(prop_val);
        }
        g_variant_unref(prop_val);
    }

    g_variant_unref(dict);
    g_variant_unref(res);

    sync_tick_timer();
    render_active_music();
}

/* Handle D-Bus PropertiesChanged signal */
static void on_properties_changed(GDBusConnection *connection,
                                  const gchar *sender_name,
                                  const gchar *object_path,
                                  const gchar *interface_name,
                                  const gchar *signal_name,
                                  GVariant *parameters,
                                  gpointer user_data) {
    (void)connection; (void)sender_name; (void)object_path;
    (void)interface_name; (void)signal_name; (void)user_data;

    const gchar *iface;
    GVariant *changed_props;
    g_variant_get(parameters, "(&s@a{sv}^as)", &iface, &changed_props, NULL);

    if (strcmp(iface, "org.mpris.MediaPlayer2.Player") != 0) {
        g_variant_unref(changed_props);
        return;
    }

    GVariantIter iter;
    g_variant_iter_init(&iter, changed_props);
    const gchar *key;
    GVariant *val;

    while (g_variant_iter_next(&iter, "{&sv}", &key, &val)) {
        if (strcmp(key, "PlaybackStatus") == 0) {
            g_strlcpy(current_status, g_variant_get_string(val, NULL), sizeof(current_status));
        } else if (strcmp(key, "Metadata") == 0) {
            parse_metadata(val);
        } else if (strcmp(key, "Position") == 0) {
            current_pos_us = g_variant_get_int64(val);
            last_sync_time = time(NULL);
        }
        g_variant_unref(val);
    }
    g_variant_unref(changed_props);

    sync_tick_timer();
    render_active_music();
}

/* Handle Seeked signal */
static void on_seeked_signal(GDBusConnection *connection,
                             const gchar *sender_name,
                             const gchar *object_path,
                             const gchar *interface_name,
                             const gchar *signal_name,
                             GVariant *parameters,
                             gpointer user_data) {
    (void)connection; (void)sender_name; (void)object_path;
    (void)interface_name; (void)signal_name; (void)user_data;

    gint64 pos = 0;
    g_variant_get(parameters, "(x)", &pos);
    current_pos_us = pos;
    last_sync_time = time(NULL);

    render_active_music();
}

/* Startup grace period timeout: if no player appeared, exit cleanly */
static gboolean on_startup_timeout(gpointer user_data) {
    (void)user_data;
    startup_timer_id = 0;
    if (!is_player_active) {
        if (main_loop && g_main_loop_is_running(main_loop)) {
            g_main_loop_quit(main_loop);
        }
    }
    return G_SOURCE_REMOVE;
}

/* Player appeared on D-Bus */
static void on_player_appeared(GDBusConnection *conn,
                               const gchar *name,
                               const gchar *name_owner,
                               gpointer user_data) {
    (void)conn; (void)name_owner; (void)user_data;

    if (startup_timer_id > 0) {
        g_source_remove(startup_timer_id);
        startup_timer_id = 0;
    }

    g_strlcpy(active_bus_name, name, sizeof(active_bus_name));
    is_player_active = TRUE;

    if (prop_sub_id == 0) {
        prop_sub_id = g_dbus_connection_signal_subscribe(
            dbus_conn,
            active_bus_name,
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            "/org/mpris/MediaPlayer2",
            NULL,
            G_DBUS_SIGNAL_FLAGS_NONE,
            on_properties_changed,
            NULL,
            NULL
        );
    }

    if (seeked_sub_id == 0) {
        seeked_sub_id = g_dbus_connection_signal_subscribe(
            dbus_conn,
            active_bus_name,
            "org.mpris.MediaPlayer2.Player",
            "Seeked",
            "/org/mpris/MediaPlayer2",
            NULL,
            G_DBUS_SIGNAL_FLAGS_NONE,
            on_seeked_signal,
            NULL,
            NULL
        );
    }

    notify_polybar("#music_center.module_show");
    fetch_player_state();
}

/* Player vanished from D-Bus */
static void on_player_vanished(GDBusConnection *conn,
                               const gchar *name,
                               gpointer user_data) {
    (void)conn; (void)user_data;
    if (is_player_active && strcmp(active_bus_name, name) == 0) {
        is_player_active = FALSE;
        active_bus_name[0] = '\0';
        g_strlcpy(current_status, "Stopped", sizeof(current_status));
        sync_tick_timer();

        if (prop_sub_id > 0) {
            g_dbus_connection_signal_unsubscribe(dbus_conn, prop_sub_id);
            prop_sub_id = 0;
        }
        if (seeked_sub_id > 0) {
            g_dbus_connection_signal_unsubscribe(dbus_conn, seeked_sub_id);
            seeked_sub_id = 0;
        }

        render_clear();
        notify_polybar("#music_center.module_hide");

        /* Zero-RAM lifecycle: Player is gone, exit PolybarMusic immediately */
        if (main_loop && g_main_loop_is_running(main_loop)) {
            g_main_loop_quit(main_loop);
        }
    }
}

int main(int argc, char **argv) {
    gboolean use_fifo = FALSE;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fifo") == 0) {
            use_fifo = TRUE;
        }
    }

    /* Singleton lock check: ensure only one PolybarMusic process runs */
    lock_fd = open(LOCK_PATH, O_CREAT | O_RDWR, 0600);
    if (lock_fd >= 0) {
        if (flock(lock_fd, LOCK_EX | LOCK_NB) != 0) {
            /* Another instance is already actively streaming; exit cleanly */
            close(lock_fd);
            return 0;
        }
    }

    /* Handle FIFO streaming if requested or when FIFO exists */
    if (use_fifo) {
        struct stat st;
        if (stat(FIFO_PATH, &st) != 0 || !S_ISFIFO(st.st_mode)) {
            unlink(FIFO_PATH);
            mkfifo(FIFO_PATH, 0666);
        }
        int fifo_fd = open(FIFO_PATH, O_WRONLY | O_NONBLOCK);
        if (fifo_fd >= 0) {
            int flags = fcntl(fifo_fd, F_GETFL);
            if (flags != -1) {
                fcntl(fifo_fd, F_SETFL, flags & ~O_NONBLOCK);
            }
            dup2(fifo_fd, STDOUT_FILENO);
            close(fifo_fd);
        }
    }

    /* Set line buffering on stdout for streaming */
    setvbuf(stdout, NULL, _IOLBF, 0);

    GError *err = NULL;
    dbus_conn = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, &err);
    if (!dbus_conn) {
        if (err) g_error_free(err);
        if (lock_fd >= 0) { flock(lock_fd, LOCK_UN); close(lock_fd); }
        return 1;
    }

    /* Set 1.5s startup timeout: if player is not currently running, exit */
    startup_timer_id = g_timeout_add(1500, on_startup_timeout, NULL);

    /* Monitor target players */
    watcher_qtmusic = g_bus_watch_name(
        G_BUS_TYPE_SESSION,
        "org.mpris.MediaPlayer2.qt-music",
        G_BUS_NAME_WATCHER_FLAGS_NONE,
        on_player_appeared,
        on_player_vanished,
        NULL,
        NULL
    );

    watcher_lyricview = g_bus_watch_name(
        G_BUS_TYPE_SESSION,
        "org.mpris.MediaPlayer2.lyricview",
        G_BUS_NAME_WATCHER_FLAGS_NONE,
        on_player_appeared,
        on_player_vanished,
        NULL,
        NULL
    );

    watcher_lollypop = g_bus_watch_name(
        G_BUS_TYPE_SESSION,
        "org.mpris.MediaPlayer2.lollypop",
        G_BUS_NAME_WATCHER_FLAGS_NONE,
        on_player_appeared,
        on_player_vanished,
        NULL,
        NULL
    );

    main_loop = g_main_loop_new(NULL, FALSE);
    g_main_loop_run(main_loop);

    /* Cleanup */
    if (startup_timer_id > 0) {
        g_source_remove(startup_timer_id);
        startup_timer_id = 0;
    }
    if (tick_timer_id > 0) {
        g_source_remove(tick_timer_id);
        tick_timer_id = 0;
    }
    if (prop_sub_id > 0) {
        g_dbus_connection_signal_unsubscribe(dbus_conn, prop_sub_id);
        prop_sub_id = 0;
    }
    if (seeked_sub_id > 0) {
        g_dbus_connection_signal_unsubscribe(dbus_conn, seeked_sub_id);
        seeked_sub_id = 0;
    }

    g_bus_unwatch_name(watcher_qtmusic);
    g_bus_unwatch_name(watcher_lyricview);
    g_bus_unwatch_name(watcher_lollypop);
    g_object_unref(dbus_conn);

    if (main_loop) {
        g_main_loop_unref(main_loop);
        main_loop = NULL;
    }

    if (lock_fd >= 0) {
        flock(lock_fd, LOCK_UN);
        close(lock_fd);
        lock_fd = -1;
    }

    return 0;
}
