#define _GNU_SOURCE
#include <gtk/gtk.h>
#include <gdk/gdk.h>
#include <gdk/gdkx.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <json-glib/json-glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/timerfd.h>
#include <time.h>
#include <dirent.h>
#include <signal.h>
#include <math.h>

#define ACTIVE_ALARM_FILE   "/tmp/sys-alarm.active"
#define SNOOZE_STATE_FILE   "/tmp/sys-alarm.snooze"
#define DEFAULT_SINK_HINT   "alsa_output.pci-0000_00_1b.0.analog-stereo"

static const char *get_config_dir(void) {
    static char *dir = NULL;
    if (!dir) {
        dir = g_build_filename(g_get_user_config_dir(), "sys-alarm", NULL);
    }
    return dir;
}

static const char *get_config_file(void) {
    static char *file = NULL;
    if (!file) {
        file = g_build_filename(get_config_dir(), "config.json", NULL);
    }
    return file;
}

static const char *get_music_dir(void) {
    static char *music = NULL;
    if (!music) {
        const char *special = g_get_user_special_dir(G_USER_DIRECTORY_MUSIC);
        if (special && special[0] != '\0') {
            music = g_strdup(special);
        } else {
            music = g_build_filename(g_get_home_dir(), "Music", NULL);
        }
    }
    return music;
}

static char *get_fallback_alarm_file(void) {
    /* 1. Dynamic check for user Downloads/nuclear_alarm.mp3 */
    const char *dl_dir = g_get_user_special_dir(G_USER_DIRECTORY_DOWNLOAD);
    char *user_dl = dl_dir ? g_build_filename(dl_dir, "nuclear_alarm.mp3", NULL)
                           : g_build_filename(g_get_home_dir(), "Downloads", "nuclear_alarm.mp3", NULL);
    if (g_file_test(user_dl, G_FILE_TEST_EXISTS)) {
        return user_dl;
    }
    g_free(user_dl);

    /* 2. Standard freedesktop system sound files in priority order */
    static const char * const freedesktop_fallbacks[] = {
        "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
        "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        NULL
    };

    for (int i = 0; freedesktop_fallbacks[i] != NULL; i++) {
        if (g_file_test(freedesktop_fallbacks[i], G_FILE_TEST_EXISTS)) {
            return g_strdup(freedesktop_fallbacks[i]);
        }
    }

    return NULL;
}

#define CONFIG_DIR          (get_config_dir())
#define CONFIG_FILE         (get_config_file())
#define DEFAULT_MUSIC_DIR   (get_music_dir())

typedef enum {
    REPEAT_DAILY = 0,
    REPEAT_WEEKDAYS = 1,
    REPEAT_WEEKENDS = 2,
    REPEAT_ONCE = 3,
    REPEAT_CUSTOM = 4
} RepeatMode;

typedef enum {
    SOUND_RANDOM_MUSIC = 0,
    SOUND_FOLDER = 1,
    SOUND_FILE = 2
} SoundType;

typedef struct {
    char *id;
    char *name;
    int hour;              /* 0 - 23 */
    int minute;            /* 0 - 59 */
    gboolean enabled;
    RepeatMode repeat_mode;
    int custom_days_mask;  /* bit 1=Mon, 2=Tue, ..., 7=Sun */
    SoundType sound_type;
    char *sound_path;
    int volume;            /* e.g. 150 */
    int snooze_min;        /* e.g. 5 */
} Alarm;

typedef struct {
    char *default_speaker_sink;
    int default_volume;
    int default_snooze_min;
    GList *alarms;         /* List of Alarm* */
    time_t snooze_timestamp;
    char *snooze_alarm_id;
} AlarmConfig;

/* --------------------------------------------------------------------------
 * CSS Styling (Catppuccin Mocha / TokyoNight palette)
 * -------------------------------------------------------------------------- */
static const char *STYLE_CSS =
"window.alarm-window, window.popup-window {\n"
"    background-color: rgba(30, 30, 46, 0.96);\n"
"    border: 1.5px solid rgba(137, 180, 250, 0.7);\n"
"    border-radius: 16px;\n"
"}\n"
"\n"
"window.popup-window {\n"
"    border: 2px solid #f38ba8;\n"
"    background-color: rgba(24, 24, 37, 0.98);\n"
"}\n"
"\n"
".header-bar {\n"
"    padding: 14px 18px 12px 18px;\n"
"    border-bottom: 1px solid rgba(49, 50, 68, 0.75);\n"
"}\n"
"\n"
".header-title {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 15pt;\n"
"    font-weight: 800;\n"
"    color: #cdd6f4;\n"
"}\n"
"\n"
".header-clock {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', monospace;\n"
"    font-size: 18pt;\n"
"    font-weight: 900;\n"
"    color: #89b4fa;\n"
"}\n"
"\n"
".header-badge {\n"
"    background-color: rgba(166, 227, 161, 0.18);\n"
"    color: #a6e3a1;\n"
"    font-family: 'JetBrains Mono', monospace;\n"
"    font-size: 9pt;\n"
"    font-weight: bold;\n"
"    padding: 4px 10px;\n"
"    border-radius: 12px;\n"
"    border: 1px solid rgba(166, 227, 161, 0.35);\n"
"}\n"
"\n"
".alarm-card {\n"
"    background-color: rgba(24, 24, 37, 0.85);\n"
"    border: 1px solid rgba(49, 50, 68, 0.8);\n"
"    border-radius: 12px;\n"
"    padding: 14px 18px;\n"
"    margin: 6px 12px;\n"
"    transition: all 150ms ease;\n"
"}\n"
".alarm-card:hover {\n"
"    background-color: rgba(49, 50, 68, 0.55);\n"
"    border-color: rgba(137, 180, 250, 0.6);\n"
"}\n"
".alarm-card.disabled {\n"
"    opacity: 0.55;\n"
"}\n"
"\n"
".alarm-time {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', monospace;\n"
"    font-size: 26pt;\n"
"    font-weight: 900;\n"
"    color: #cdd6f4;\n"
"}\n"
"\n"
".alarm-name {\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 11pt;\n"
"    font-weight: bold;\n"
"    color: #f5e0dc;\n"
"}\n"
"\n"
".alarm-meta {\n"
"    font-family: 'JetBrains Mono', sans-serif;\n"
"    font-size: 8.5pt;\n"
"    color: #a6adc8;\n"
"}\n"
"\n"
".btn-primary {\n"
"    background-color: rgba(137, 180, 250, 0.22);\n"
"    color: #89b4fa;\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 9.5pt;\n"
"    font-weight: bold;\n"
"    padding: 6px 14px;\n"
"    border-radius: 8px;\n"
"    border: 1px solid rgba(137, 180, 250, 0.45);\n"
"}\n"
".btn-primary:hover {\n"
"    background-color: rgba(137, 180, 250, 0.4);\n"
"    color: #ffffff;\n"
"}\n"
"\n"
".btn-danger {\n"
"    background-color: rgba(243, 139, 168, 0.2);\n"
"    color: #f38ba8;\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 9.5pt;\n"
"    font-weight: bold;\n"
"    padding: 6px 14px;\n"
"    border-radius: 8px;\n"
"    border: 1px solid rgba(243, 139, 168, 0.4);\n"
"}\n"
".btn-danger:hover {\n"
"    background-color: rgba(243, 139, 168, 0.4);\n"
"    color: #ffffff;\n"
"}\n"
"\n"
".btn-dismiss {\n"
"    background-color: #f38ba8;\n"
"    color: #11111b;\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 14pt;\n"
"    font-weight: 900;\n"
"    padding: 14px 28px;\n"
"    border-radius: 12px;\n"
"    border: none;\n"
"}\n"
".btn-dismiss:hover {\n"
"    background-color: #ff9fb8;\n"
"}\n"
"\n"
".btn-snooze {\n"
"    background-color: rgba(137, 180, 250, 0.25);\n"
"    color: #89b4fa;\n"
"    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', sans-serif;\n"
"    font-size: 13pt;\n"
"    font-weight: 800;\n"
"    padding: 12px 24px;\n"
"    border-radius: 12px;\n"
"    border: 1.5px solid rgba(137, 180, 250, 0.5);\n"
"}\n"
".btn-snooze:hover {\n"
"    background-color: rgba(137, 180, 250, 0.45);\n"
"    color: #ffffff;\n"
"}\n"
"\n"
".popup-time {\n"
"    font-family: 'JetBrainsMono Nerd Font', monospace;\n"
"    font-size: 46pt;\n"
"    font-weight: 900;\n"
"    color: #f38ba8;\n"
"}\n"
"\n"
".popup-title {\n"
"    font-family: 'JetBrainsMono Nerd Font', sans-serif;\n"
"    font-size: 18pt;\n"
"    font-weight: 900;\n"
"    color: #cdd6f4;\n"
"}\n"
"\n"
".popup-track {\n"
"    font-family: 'JetBrains Mono', sans-serif;\n"
"    font-size: 11pt;\n"
"    color: #fab387;\n"
"}\n"
"\n"
".popup-badge {\n"
"    background-color: rgba(243, 139, 168, 0.2);\n"
"    color: #f38ba8;\n"
"    font-family: 'JetBrains Mono', monospace;\n"
"    font-size: 10pt;\n"
"    font-weight: bold;\n"
"    padding: 6px 14px;\n"
"    border-radius: 10px;\n"
"    border: 1px solid rgba(243, 139, 168, 0.4);\n"
"}\n";

/* --------------------------------------------------------------------------
 * Prototypes
 * -------------------------------------------------------------------------- */
static AlarmConfig *config_load(void);
static gboolean config_save(AlarmConfig *cfg);
static void config_free(AlarmConfig *cfg);
static void alarm_free(Alarm *a);
static time_t alarm_get_next_trigger(const Alarm *a, time_t now);
static Alarm *config_get_next_alarm(AlarmConfig *cfg, time_t now, time_t *out_trigger_time);
static void sync_system_timers(AlarmConfig *cfg);
static char *detect_speaker_sink(void);
static char *pick_audio_file(SoundType type, const char *path);
static int cmd_ring(const char *alarm_id_or_null);
static int cmd_dismiss(void);
static int cmd_snooze(int minutes);
static int cmd_list(void);
static int cmd_daemon(void);
static int cmd_test(void);
static void run_gui_app(int argc, char **argv);
static void run_popup_window(const char *alarm_name, const char *track_title, int volume);

/* --------------------------------------------------------------------------
 * Audio Sink & Song Picker Helpers
 * -------------------------------------------------------------------------- */
static char *detect_speaker_sink(void) {
    FILE *fp = popen("pactl list sinks 2>/dev/null", "r");
    if (!fp) {
        return g_strdup(DEFAULT_SINK_HINT);
    }

    char line[512];
    char current_name[256] = {0};
    char internal_candidate[256] = {0};
    gboolean is_internal = FALSE;

    while (fgets(line, sizeof(line), fp)) {
        if (g_str_has_prefix(line, "Sink #") || g_str_has_prefix(line, "\tName: ")) {
            if (current_name[0] && is_internal && !internal_candidate[0]) {
                g_strlcpy(internal_candidate, current_name, sizeof(internal_candidate));
            }
            if (g_str_has_prefix(line, "\tName: ")) {
                char *p = line + 7;
                g_strstrip(p);
                g_strlcpy(current_name, p, sizeof(current_name));
                is_internal = FALSE;
            }
        }
        if (strstr(line, "device.form_factor = \"internal\"") ||
            strstr(line, "alsa_output.pci") ||
            strstr(line, "analog-stereo")) {
            is_internal = TRUE;
        }
    }
    if (current_name[0] && is_internal && !internal_candidate[0]) {
        g_strlcpy(internal_candidate, current_name, sizeof(internal_candidate));
    }
    pclose(fp);

    if (internal_candidate[0]) {
        return g_strdup(internal_candidate);
    }
    return g_strdup(DEFAULT_SINK_HINT);
}

static void scan_audio_files_rec(const char *dir_path, GPtrArray *arr) {
    GDir *dir = g_dir_open(dir_path, 0, NULL);
    if (!dir) return;

    const char *entry;
    while ((entry = g_dir_read_name(dir)) != NULL) {
        if (entry[0] == '.') continue;
        char *full = g_build_filename(dir_path, entry, NULL);
        if (g_file_test(full, G_FILE_TEST_IS_DIR)) {
            scan_audio_files_rec(full, arr);
        } else if (g_file_test(full, G_FILE_TEST_IS_REGULAR)) {
            const char *dot = strrchr(entry, '.');
            if (dot) {
                if (g_ascii_strcasecmp(dot, ".mp3") == 0 ||
                    g_ascii_strcasecmp(dot, ".flac") == 0 ||
                    g_ascii_strcasecmp(dot, ".m4a") == 0 ||
                    g_ascii_strcasecmp(dot, ".wav") == 0 ||
                    g_ascii_strcasecmp(dot, ".ogg") == 0 ||
                    g_ascii_strcasecmp(dot, ".oga") == 0 ||
                    g_ascii_strcasecmp(dot, ".opus") == 0) {
                    g_ptr_array_add(arr, g_strdup(full));
                }
            }
        }
        g_free(full);
    }
    g_dir_close(dir);
}

static char *pick_audio_file(SoundType type, const char *path) {
    if (type == SOUND_FILE && path && g_file_test(path, G_FILE_TEST_EXISTS)) {
        return g_strdup(path);
    }

    const char *target_dir = DEFAULT_MUSIC_DIR;
    if (type == SOUND_FOLDER && path && g_file_test(path, G_FILE_TEST_IS_DIR)) {
        target_dir = path;
    }

    GPtrArray *arr = g_ptr_array_new_with_free_func(g_free);
    scan_audio_files_rec(target_dir, arr);

    if (arr->len == 0 && strcmp(target_dir, DEFAULT_MUSIC_DIR) != 0) {
        scan_audio_files_rec(DEFAULT_MUSIC_DIR, arr);
    }

    char *result = NULL;
    if (arr->len > 0) {
        guint idx = g_random_int_range(0, arr->len);
        result = g_strdup((char *)g_ptr_array_index(arr, idx));
    } else {
        /* Fallback check for nuclear alarm or freedesktop system sound files */
        result = get_fallback_alarm_file();
    }
    g_ptr_array_free(arr, TRUE);
    return result;
}

/* --------------------------------------------------------------------------
 * Config JSON Handling
 * -------------------------------------------------------------------------- */
static Alarm *alarm_create_default(const char *id, const char *name, int hour, int minute) {
    Alarm *a = g_new0(Alarm, 1);
    a->id = g_strdup(id);
    a->name = g_strdup(name);
    a->hour = hour;
    a->minute = minute;
    a->enabled = TRUE;
    a->repeat_mode = REPEAT_DAILY;
    a->custom_days_mask = 0x7F; /* All 7 days */
    a->sound_type = SOUND_RANDOM_MUSIC;
    a->sound_path = g_strdup(DEFAULT_MUSIC_DIR);
    a->volume = 150;
    a->snooze_min = 5;
    return a;
}

static void alarm_free(Alarm *a) {
    if (!a) return;
    g_free(a->id);
    g_free(a->name);
    g_free(a->sound_path);
    g_free(a);
}

static void config_free(AlarmConfig *cfg) {
    if (!cfg) return;
    g_free(cfg->default_speaker_sink);
    g_free(cfg->snooze_alarm_id);
    g_list_free_full(cfg->alarms, (GDestroyNotify)alarm_free);
    g_free(cfg);
}

static AlarmConfig *config_load(void) {
    AlarmConfig *cfg = g_new0(AlarmConfig, 1);
    cfg->default_volume = 150;
    cfg->default_snooze_min = 5;
    cfg->default_speaker_sink = detect_speaker_sink();

    if (!g_file_test(CONFIG_FILE, G_FILE_TEST_EXISTS)) {
        /* Initialize with requested 4:00 AM and 4:05 AM alarms */
        cfg->alarms = g_list_append(cfg->alarms,
            alarm_create_default("alarm_4am", "Morning Wake Up", 4, 0));
        cfg->alarms = g_list_append(cfg->alarms,
            alarm_create_default("alarm_405am", "Morning Backup Wake Up", 4, 5));
        config_save(cfg);
        return cfg;
    }

    JsonParser *parser = json_parser_new();
    GError *err = NULL;
    if (!json_parser_load_from_file(parser, CONFIG_FILE, &err)) {
        g_warning("Failed to parse config: %s", err ? err->message : "unknown");
        g_clear_error(&err);
        g_object_unref(parser);
        return cfg;
    }

    JsonNode *root = json_parser_get_root(parser);
    if (JSON_NODE_HOLDS_OBJECT(root)) {
        JsonObject *obj = json_node_get_object(root);
        if (json_object_has_member(obj, "default_speaker_sink")) {
            g_free(cfg->default_speaker_sink);
            cfg->default_speaker_sink = g_strdup(json_object_get_string_member(obj, "default_speaker_sink"));
        }
        if (json_object_has_member(obj, "default_volume")) {
            cfg->default_volume = (int)json_object_get_int_member(obj, "default_volume");
        }
        if (json_object_has_member(obj, "default_snooze_min")) {
            cfg->default_snooze_min = (int)json_object_get_int_member(obj, "default_snooze_min");
        }

        if (json_object_has_member(obj, "alarms")) {
            JsonArray *arr = json_object_get_array_member(obj, "alarms");
            guint len = json_array_get_length(arr);
            for (guint i = 0; i < len; i++) {
                JsonObject *aobj = json_array_get_object_element(arr, i);
                Alarm *a = g_new0(Alarm, 1);
                a->id = g_strdup(json_object_get_string_member(aobj, "id"));
                a->name = g_strdup(json_object_has_member(aobj, "name") ? json_object_get_string_member(aobj, "name") : "Alarm");
                a->hour = (int)json_object_get_int_member(aobj, "hour");
                a->minute = (int)json_object_get_int_member(aobj, "minute");
                a->enabled = json_object_has_member(aobj, "enabled") ? json_object_get_boolean_member(aobj, "enabled") : TRUE;
                a->repeat_mode = json_object_has_member(aobj, "repeat_mode") ? (RepeatMode)json_object_get_int_member(aobj, "repeat_mode") : REPEAT_DAILY;
                a->custom_days_mask = json_object_has_member(aobj, "custom_days_mask") ? (int)json_object_get_int_member(aobj, "custom_days_mask") : 0x7F;
                a->sound_type = json_object_has_member(aobj, "sound_type") ? (SoundType)json_object_get_int_member(aobj, "sound_type") : SOUND_RANDOM_MUSIC;
                a->sound_path = g_strdup(json_object_has_member(aobj, "sound_path") ? json_object_get_string_member(aobj, "sound_path") : DEFAULT_MUSIC_DIR);
                a->volume = json_object_has_member(aobj, "volume") ? (int)json_object_get_int_member(aobj, "volume") : 150;
                a->snooze_min = json_object_has_member(aobj, "snooze_min") ? (int)json_object_get_int_member(aobj, "snooze_min") : 5;
                cfg->alarms = g_list_append(cfg->alarms, a);
            }
        }
    }
    g_object_unref(parser);

    /* Check snooze file */
    if (g_file_test(SNOOZE_STATE_FILE, G_FILE_TEST_EXISTS)) {
        char *content = NULL;
        if (g_file_get_contents(SNOOZE_STATE_FILE, &content, NULL, NULL)) {
            time_t stime = 0;
            char sid[128] = {0};
            if (sscanf(content, "%ld %127s", &stime, sid) >= 1) {
                if (stime > time(NULL)) {
                    cfg->snooze_timestamp = stime;
                    cfg->snooze_alarm_id = g_strdup(sid);
                }
            }
            g_free(content);
        }
    }

    return cfg;
}

static gboolean config_save(AlarmConfig *cfg) {
    g_mkdir_with_parents(CONFIG_DIR, 0755);

    JsonBuilder *builder = json_builder_new();
    json_builder_begin_object(builder);

    json_builder_set_member_name(builder, "default_speaker_sink");
    json_builder_add_string_value(builder, cfg->default_speaker_sink ? cfg->default_speaker_sink : DEFAULT_SINK_HINT);

    json_builder_set_member_name(builder, "default_volume");
    json_builder_add_int_value(builder, cfg->default_volume);

    json_builder_set_member_name(builder, "default_snooze_min");
    json_builder_add_int_value(builder, cfg->default_snooze_min);

    json_builder_set_member_name(builder, "alarms");
    json_builder_begin_array(builder);

    for (GList *l = cfg->alarms; l != NULL; l = l->next) {
        Alarm *a = (Alarm *)l->data;
        json_builder_begin_object(builder);
        json_builder_set_member_name(builder, "id");
        json_builder_add_string_value(builder, a->id);
        json_builder_set_member_name(builder, "name");
        json_builder_add_string_value(builder, a->name);
        json_builder_set_member_name(builder, "hour");
        json_builder_add_int_value(builder, a->hour);
        json_builder_set_member_name(builder, "minute");
        json_builder_add_int_value(builder, a->minute);
        json_builder_set_member_name(builder, "enabled");
        json_builder_add_boolean_value(builder, a->enabled);
        json_builder_set_member_name(builder, "repeat_mode");
        json_builder_add_int_value(builder, a->repeat_mode);
        json_builder_set_member_name(builder, "custom_days_mask");
        json_builder_add_int_value(builder, a->custom_days_mask);
        json_builder_set_member_name(builder, "sound_type");
        json_builder_add_int_value(builder, a->sound_type);
        json_builder_set_member_name(builder, "sound_path");
        json_builder_add_string_value(builder, a->sound_path ? a->sound_path : "");
        json_builder_set_member_name(builder, "volume");
        json_builder_add_int_value(builder, a->volume);
        json_builder_set_member_name(builder, "snooze_min");
        json_builder_add_int_value(builder, a->snooze_min);
        json_builder_end_object(builder);
    }
    json_builder_end_array(builder);
    json_builder_end_object(builder);

    JsonGenerator *gen = json_generator_new();
    JsonNode *root = json_builder_get_root(builder);
    json_generator_set_root(gen, root);
    json_generator_set_pretty(gen, TRUE);

    GError *err = NULL;
    gboolean ok = json_generator_to_file(gen, CONFIG_FILE, &err);
    if (!ok) {
        g_warning("Could not save config to %s: %s", CONFIG_FILE, err ? err->message : "unknown");
        g_clear_error(&err);
    }

    json_node_free(root);
    g_object_unref(gen);
    g_object_unref(builder);

    sync_system_timers(cfg);
    return ok;
}

/* --------------------------------------------------------------------------
 * Schedule & Timing Logic
 * -------------------------------------------------------------------------- */
static time_t alarm_get_next_trigger(const Alarm *a, time_t now) {
    if (!a || !a->enabled) return 0;

    struct tm now_tm;
    localtime_r(&now, &now_tm);

    /* Test day offset 0 through 7 */
    for (int day_offset = 0; day_offset <= 7; day_offset++) {
        struct tm cand_tm = now_tm;
        cand_tm.tm_mday += day_offset;
        cand_tm.tm_hour = a->hour;
        cand_tm.tm_min = a->minute;
        cand_tm.tm_sec = 0;
        cand_tm.tm_isdst = -1;

        time_t cand_time = mktime(&cand_tm);
        if (cand_time <= now) {
            continue; /* Already passed today */
        }

        /* Check day of week */
        /* tm_wday: 0 = Sun, 1 = Mon, ..., 6 = Sat */
        int iso_wday = (cand_tm.tm_wday == 0) ? 7 : cand_tm.tm_wday; /* 1..7 */

        gboolean day_matches = FALSE;
        switch (a->repeat_mode) {
            case REPEAT_DAILY:
                day_matches = TRUE;
                break;
            case REPEAT_WEEKDAYS:
                day_matches = (iso_wday >= 1 && iso_wday <= 5);
                break;
            case REPEAT_WEEKENDS:
                day_matches = (iso_wday == 6 || iso_wday == 7);
                break;
            case REPEAT_ONCE:
                day_matches = TRUE;
                break;
            case REPEAT_CUSTOM:
                day_matches = ((a->custom_days_mask & (1 << iso_wday)) != 0);
                break;
        }

        if (day_matches) {
            return cand_time;
        }
    }
    return 0;
}

static Alarm *config_get_next_alarm(AlarmConfig *cfg, time_t now, time_t *out_trigger_time) {
    Alarm *earliest_alarm = NULL;
    time_t earliest_time = 0;

    /* Check active snooze first */
    if (cfg->snooze_timestamp > now) {
        earliest_time = cfg->snooze_timestamp;
        for (GList *l = cfg->alarms; l != NULL; l = l->next) {
            Alarm *a = (Alarm *)l->data;
            if (cfg->snooze_alarm_id && strcmp(a->id, cfg->snooze_alarm_id) == 0) {
                earliest_alarm = a;
                break;
            }
        }
    }

    for (GList *l = cfg->alarms; l != NULL; l = l->next) {
        Alarm *a = (Alarm *)l->data;
        if (!a->enabled) continue;
        time_t next_t = alarm_get_next_trigger(a, now);
        if (next_t > now) {
            if (earliest_time == 0 || next_t < earliest_time) {
                earliest_time = next_t;
                earliest_alarm = a;
            }
        }
    }

    if (out_trigger_time) {
        *out_trigger_time = earliest_time;
    }
    return earliest_alarm;
}

/* --------------------------------------------------------------------------
 * Systemd Timers & RTC Wake Synchronization
 * -------------------------------------------------------------------------- */
static void sync_system_timers(AlarmConfig *cfg) {
    time_t now = time(NULL);
    time_t next_t = 0;
    Alarm *next_alarm = config_get_next_alarm(cfg, now, &next_t);

    char *timer_dir = g_build_filename(g_get_user_config_dir(), "systemd", "user", NULL);
    g_mkdir_with_parents(timer_dir, 0755);

    char *timer_file = g_build_filename(timer_dir, "sys-alarm-wake.timer", NULL);
    char *service_file = g_build_filename(timer_dir, "sys-alarm-wake.service", NULL);

    /* Write service file */
    char service_content[1024];
    snprintf(service_content, sizeof(service_content),
        "[Unit]\n"
        "Description=sys-alarm RTC Wake Service\n"
        "After=default.target sound.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "Environment=\"DISPLAY=:0\" \"XAUTHORITY=%s/.Xauthority\" \"XDG_RUNTIME_DIR=/run/user/%u\"\n"
        "ExecStart=%s/.local/bin/sys-alarm ring\n",
        g_get_home_dir(),
        (unsigned int)getuid(),
        g_get_home_dir()
    );
    g_file_set_contents(service_file, service_content, -1, NULL);

    if (next_alarm && next_t > now) {
        struct tm tm_info;
        localtime_r(&next_t, &tm_info);
        char date_str[64];
        strftime(date_str, sizeof(date_str), "%Y-%m-%d %H:%M:00", &tm_info);

        char timer_content[1024];
        snprintf(timer_content, sizeof(timer_content),
            "[Unit]\n"
            "Description=sys-alarm RTC Wake Timer\n"
            "\n"
            "[Timer]\n"
            "OnCalendar=%s\n"
            "WakeSystem=true\n"
            "AccuracySec=1s\n"
            "\n"
            "[Install]\n"
            "WantedBy=timers.target\n",
            date_str
        );
        g_file_set_contents(timer_file, timer_content, -1, NULL);

        /* Write ACPI RTC wakealarm if writable */
        int rtc_fd = open("/sys/class/rtc/rtc0/wakealarm", O_WRONLY);
        if (rtc_fd >= 0) {
            write(rtc_fd, "0\n", 2);
            char epoch_str[32];
            snprintf(epoch_str, sizeof(epoch_str), "%ld\n", (long)next_t);
            write(rtc_fd, epoch_str, strlen(epoch_str));
            close(rtc_fd);
        }

        /* Reload user systemd units and ensure timer is enabled across reboots */
        system("systemctl --user daemon-reload >/dev/null 2>&1");
        system("systemctl --user enable --now sys-alarm-wake.timer >/dev/null 2>&1");
        system("systemctl --user restart sys-alarm-wake.timer >/dev/null 2>&1");
    } else {
        /* No upcoming alarms, stop and disable timer */
        system("systemctl --user disable --now sys-alarm-wake.timer >/dev/null 2>&1");
    }

    g_free(timer_file);
    g_free(service_file);
    g_free(timer_dir);
}

/* --------------------------------------------------------------------------
 * Audio Blaster & Ringer Engine
 * -------------------------------------------------------------------------- */
static void on_ring_sigterm(int signum) {
    (void)signum;
    cmd_dismiss();
    _exit(0);
}

static int cmd_ring(const char *alarm_id_or_null) {
    /* Clean termination on SIGINT/SIGTERM */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_ring_sigterm;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    AlarmConfig *cfg = config_load();
    Alarm *a = NULL;

    if (alarm_id_or_null) {
        for (GList *l = cfg->alarms; l != NULL; l = l->next) {
            Alarm *item = (Alarm *)l->data;
            if (strcmp(item->id, alarm_id_or_null) == 0) {
                a = item;
                break;
            }
        }
    }
    if (!a) {
        time_t next_t;
        a = config_get_next_alarm(cfg, time(NULL) - 60, &next_t);
    }
    if (!a && cfg->alarms) {
        a = (Alarm *)cfg->alarms->data;
    }

    const char *alarm_name = a ? a->name : "Wake Up!";
    int volume = (a && a->volume > 0) ? a->volume : 150;
    SoundType stype = a ? a->sound_type : SOUND_RANDOM_MUSIC;
    const char *spath = a ? a->sound_path : DEFAULT_MUSIC_DIR;
    char *sink = cfg->default_speaker_sink ? g_strdup(cfg->default_speaker_sink) : detect_speaker_sink();

    /* Clear snooze state upon ringing */
    unlink(SNOOZE_STATE_FILE);

    /* 1. Unmute speaker and boost volume on BOTH candidate sink and @DEFAULT_SINK@ */
    char cmd[512];
    if (sink && g_strcmp0(sink, "@DEFAULT_SINK@") != 0) {
        snprintf(cmd, sizeof(cmd), "pactl set-sink-mute %s 0; pactl set-sink-volume %s %d%% 2>/dev/null", sink, sink, volume);
        system(cmd);
        snprintf(cmd, sizeof(cmd), "pactl set-sink-port %s analog-output-speaker 2>/dev/null", sink);
        system(cmd);
    }
    snprintf(cmd, sizeof(cmd), "pactl set-sink-mute @DEFAULT_SINK@ 0; pactl set-sink-volume @DEFAULT_SINK@ %d%% 2>/dev/null", volume);
    system(cmd);

    /* 2. Pick audio track */
    char *song_file = pick_audio_file(stype, spath);
    if (!song_file) {
        song_file = get_fallback_alarm_file();
    }

    char *track_name = song_file ? g_path_get_basename(song_file) : g_strdup("Default Alarm Track");

    /* 3. Fork audio player process */
    pid_t audio_pid = fork();
    if (audio_pid == 0) {
        /* In child: reset signals so kill from cmd_dismiss terminates cleanly */
        signal(SIGINT, SIG_DFL);
        signal(SIGTERM, SIG_DFL);

        /* Play audio continuously */
        while (1) {
            char opt_vol[64];
            snprintf(opt_vol, sizeof(opt_vol), "--volume=%d", volume);
            char opt_dev[512];
            if (sink && sink[0]) {
                snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse/%s", sink);
            } else {
                snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse");
            }

            if (!song_file) {
                song_file = get_fallback_alarm_file();
            }

            pid_t mpv_pid = fork();
            if (mpv_pid == 0) {
                if (song_file) {
                    execlp("mpv", "mpv",
                           "--no-config",
                           "--no-video",
                           "--loop-file=inf",
                           opt_vol,
                           opt_dev,
                           song_file,
                           NULL);
                }
                _exit(1);
            }
            int status;
            waitpid(mpv_pid, &status, 0);
            /* If mpv finished or failed, re-pick another track and keep blasting */
            char *next_song = pick_audio_file(stype, spath);
            if (next_song) {
                g_free(song_file);
                song_file = next_song;
            } else if (!song_file) {
                song_file = get_fallback_alarm_file();
            }
            sleep(1);
        }
        _exit(0);
    }

    /* 4. Write active alarm state */
    char active_info[512];
    snprintf(active_info, sizeof(active_info),
        "PID=%d\nALARM_ID=%s\nNAME=%s\nSONG=%s\nVOLUME=%d\nSNOOZE_MIN=%d\nSINK=%s\n",
        audio_pid,
        a ? a->id : "unknown",
        alarm_name,
        song_file ? song_file : "none",
        volume,
        a ? a->snooze_min : 5,
        sink ? sink : "default"
    );
    g_file_set_contents(ACTIVE_ALARM_FILE, active_info, -1, NULL);

    /* 5. If alarm was REPEAT_ONCE, mark disabled */
    if (a && a->repeat_mode == REPEAT_ONCE) {
        a->enabled = FALSE;
        config_save(cfg);
    }

    /* 6. Launch snooze/dismiss popup */
    run_popup_window(alarm_name, track_name, volume);

    g_free(sink);
    g_free(song_file);
    g_free(track_name);
    config_free(cfg);
    return 0;
}

static int cmd_dismiss(void) {
    if (!g_file_test(ACTIVE_ALARM_FILE, G_FILE_TEST_EXISTS)) {
        printf("No alarm currently ringing.\n");
        return 0;
    }

    char *content = NULL;
    if (g_file_get_contents(ACTIVE_ALARM_FILE, &content, NULL, NULL)) {
        int pid = 0;
        if (sscanf(content, "PID=%d", &pid) == 1 && pid > 0) {
            kill(pid, SIGTERM);
            kill(pid, SIGKILL);
        }
        g_free(content);
    }
    unlink(ACTIVE_ALARM_FILE);
    system("pkill -f 'mpv.*--volume' >/dev/null 2>&1");
    system("pkill -f 'sys-alarm popup' >/dev/null 2>&1");

    AlarmConfig *cfg = config_load();
    sync_system_timers(cfg);
    config_free(cfg);

    printf("Alarm dismissed successfully.\n");
    return 0;
}

static int cmd_snooze(int minutes) {
    if (!g_file_test(ACTIVE_ALARM_FILE, G_FILE_TEST_EXISTS)) {
        printf("No active alarm ringing to snooze.\n");
        return 0;
    }

    char *content = NULL;
    char alarm_id[128] = "alarm";
    int default_snooze = 5;

    if (g_file_get_contents(ACTIVE_ALARM_FILE, &content, NULL, NULL)) {
        int pid = 0;
        char *id_ptr = strstr(content, "ALARM_ID=");
        if (id_ptr) sscanf(id_ptr + 9, "%127s", alarm_id);
        char *snooze_ptr = strstr(content, "SNOOZE_MIN=");
        if (snooze_ptr) sscanf(snooze_ptr + 11, "%d", &default_snooze);

        if (sscanf(content, "PID=%d", &pid) == 1 && pid > 0) {
            kill(pid, SIGTERM);
            kill(pid, SIGKILL);
        }
        g_free(content);
    }
    unlink(ACTIVE_ALARM_FILE);
    system("pkill -f 'mpv.*--volume' >/dev/null 2>&1");
    system("pkill -f 'sys-alarm popup' >/dev/null 2>&1");

    int final_min = (minutes > 0) ? minutes : default_snooze;
    time_t snooze_target = time(NULL) + (final_min * 60);

    char snooze_str[256];
    snprintf(snooze_str, sizeof(snooze_str), "%ld %s\n", (long)snooze_target, alarm_id);
    g_file_set_contents(SNOOZE_STATE_FILE, snooze_str, -1, NULL);

    AlarmConfig *cfg = config_load();
    sync_system_timers(cfg);
    config_free(cfg);

    printf("Alarm snoozed for %d minutes (ringing at %ld).\n", final_min, (long)snooze_target);
    return 0;
}

static int cmd_test(void) {
    printf("Testing alarm sound on built-in speaker at 150%% volume (4 seconds)...\n");
    AlarmConfig *cfg = config_load();
    char *sink = cfg->default_speaker_sink ? g_strdup(cfg->default_speaker_sink) : detect_speaker_sink();
    char *song = pick_audio_file(SOUND_RANDOM_MUSIC, DEFAULT_MUSIC_DIR);
    if (!song) song = get_fallback_alarm_file();

    /* Unmute and set 150% on candidate sink AND @DEFAULT_SINK@ */
    char cmd[512];
    if (sink && g_strcmp0(sink, "@DEFAULT_SINK@") != 0) {
        snprintf(cmd, sizeof(cmd), "pactl set-sink-mute %s 0 2>/dev/null; pactl set-sink-volume %s 150%% 2>/dev/null; pactl set-sink-port %s analog-output-speaker 2>/dev/null", sink, sink, sink);
        system(cmd);
    }
    snprintf(cmd, sizeof(cmd), "pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null; pactl set-sink-volume @DEFAULT_SINK@ 150%% 2>/dev/null");
    system(cmd);

    char opt_vol[64];
    snprintf(opt_vol, sizeof(opt_vol), "--volume=150");
    char opt_dev[512];
    if (sink && sink[0]) {
        snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse/%s", sink);
    } else {
        snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse");
    }

    pid_t pid = fork();
    if (pid == 0) {
        if (song) {
            execlp("mpv", "mpv",
                   "--no-config",
                   "--no-video",
                   "--loop-file=inf",
                   opt_vol,
                   opt_dev,
                   song,
                   NULL);
        }
        _exit(1);
    }

    sleep(4);
    kill(pid, SIGTERM);
    kill(pid, SIGKILL);
    g_free(sink);
    g_free(song);
    config_free(cfg);
    printf("Test complete!\n");
    return 0;
}

static int cmd_list(void) {
    AlarmConfig *cfg = config_load();
    time_t now = time(NULL);
    time_t next_t = 0;
    Alarm *next_a = config_get_next_alarm(cfg, now, &next_t);

    printf("\n⏰ sys-alarm — Active Configured Alarms\n");
    printf("========================================================================\n");
    printf("%-12s | %-8s | %-10s | %-12s | %-6s | %s\n",
           "ID", "TIME", "STATUS", "REPEAT", "VOL", "NAME / SOUND");
    printf("------------------------------------------------------------------------\n");

    for (GList *l = cfg->alarms; l != NULL; l = l->next) {
        Alarm *a = (Alarm *)l->data;
        char time_str[16];
        snprintf(time_str, sizeof(time_str), "%02d:%02d", a->hour, a->minute);

        const char *rep_str = "Daily";
        if (a->repeat_mode == REPEAT_WEEKDAYS) rep_str = "Weekdays";
        else if (a->repeat_mode == REPEAT_WEEKENDS) rep_str = "Weekends";
        else if (a->repeat_mode == REPEAT_ONCE) rep_str = "Once";
        else if (a->repeat_mode == REPEAT_CUSTOM) rep_str = "Custom";

        printf("%-12s | %-8s | %-10s | %-12s | %3d%%  | %s (%s)\n",
               a->id,
               time_str,
               a->enabled ? "ENABLED" : "DISABLED",
               rep_str,
               a->volume,
               a->name,
               (a->sound_type == SOUND_RANDOM_MUSIC) ? "Random ~/Music" :
               (a->sound_type == SOUND_FOLDER) ? "Folder" : "File");
    }
    printf("========================================================================\n");
    if (next_a && next_t > now) {
        struct tm ntm;
        localtime_r(&next_t, &ntm);
        char buf[64];
        strftime(buf, sizeof(buf), "%a %b %d %H:%M:%S", &ntm);
        long diff = (long)(next_t - now);
        int hours = diff / 3600;
        int mins = (diff % 3600) / 60;
        printf("▶ Next Alarm: %s at %s (in %dh %dm)\n\n", next_a->name, buf, hours, mins);
    } else {
        printf("No active alarms scheduled.\n\n");
    }

    config_free(cfg);
    return 0;
}

/* --------------------------------------------------------------------------
 * Daemon Loop
 * -------------------------------------------------------------------------- */
static int cmd_daemon(void) {
    printf("[sys-alarm] Starting daemon loop...\n");
    while (1) {
        AlarmConfig *cfg = config_load();
        time_t now = time(NULL);
        time_t next_t = 0;
        Alarm *next_a = config_get_next_alarm(cfg, now, &next_t);

        if (!next_a || next_t <= now) {
            config_free(cfg);
            sleep(30);
            continue;
        }

        long sleep_secs = (long)(next_t - now);
        if (sleep_secs > 0) {
            /* Sync timers and sleep */
            sync_system_timers(cfg);
            config_free(cfg);
            if (sleep_secs > 10) {
                sleep(sleep_secs - 1);
            } else {
                sleep(sleep_secs);
            }
        } else {
            /* Time to ring! */
            char *aid = g_strdup(next_a->id);
            config_free(cfg);
            cmd_ring(aid);
            g_free(aid);
            sleep(5);
        }
    }
    return 0;
}

/* --------------------------------------------------------------------------
 * Ringing Snooze/Dismiss Popup Window
 * -------------------------------------------------------------------------- */
static gboolean on_popup_key_press(GtkWidget *widget, GdkEventKey *event, gpointer user_data) {
    (void)widget;
    (void)user_data;
    if (event->keyval == GDK_KEY_Escape ||
        event->keyval == GDK_KEY_Return ||
        event->keyval == GDK_KEY_KP_Enter ||
        event->keyval == GDK_KEY_space) {
        cmd_dismiss();
        gtk_main_quit();
        return TRUE;
    } else if (event->keyval == GDK_KEY_s || event->keyval == GDK_KEY_S) {
        cmd_snooze(5);
        gtk_main_quit();
        return TRUE;
    }
    return FALSE;
}

static void on_popup_dismiss_clicked(GtkButton *btn, gpointer user_data) {
    (void)btn;
    (void)user_data;
    cmd_dismiss();
    gtk_main_quit();
}

static void on_popup_snooze_clicked(GtkButton *btn, gpointer user_data) {
    (void)btn;
    (void)user_data;
    cmd_snooze(5);
    gtk_main_quit();
}

static gboolean on_popup_delete_event(GtkWidget *widget, GdkEvent *event, gpointer user_data) {
    (void)widget;
    (void)event;
    (void)user_data;
    cmd_dismiss();
    return FALSE;
}

static void run_popup_window(const char *alarm_name, const char *track_title, int volume) {
    if (!gtk_init_check(NULL, NULL) || gdk_display_get_default() == NULL || gdk_screen_get_default() == NULL) {
        g_warning("sys-alarm: Headless environment or display unavailable (gdk_display_get_default() is NULL). Running audio ringer in headless mode.");
        /* Keep process alive while alarm is ringing so child audio playback continues */
        while (g_file_test(ACTIVE_ALARM_FILE, G_FILE_TEST_EXISTS)) {
            g_usleep(500000);
        }
        return;
    }

    g_set_prgname("sys-alarm-popup");

    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css, STYLE_CSS, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(css),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );

    GtkWidget *win = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(win), "⏰ WAKE UP - sys-alarm");
    gtk_window_set_role(GTK_WINDOW(win), "sys-alarm-popup");
    gtk_window_set_default_size(GTK_WINDOW(win), 580, 420);
    gtk_window_set_position(GTK_WINDOW(win), GTK_WIN_POS_CENTER_ALWAYS);
    gtk_window_set_keep_above(GTK_WINDOW(win), TRUE);

    GtkStyleContext *ctx = gtk_widget_get_style_context(win);
    gtk_style_context_add_class(ctx, "popup-window");

    g_signal_connect(win, "key-press-event", G_CALLBACK(on_popup_key_press), NULL);
    g_signal_connect(win, "delete-event", G_CALLBACK(on_popup_delete_event), NULL);
    g_signal_connect(win, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    GtkWidget *vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16);
    gtk_container_set_border_width(GTK_CONTAINER(vbox), 28);
    gtk_container_add(GTK_CONTAINER(win), vbox);

    /* Time display */
    time_t now = time(NULL);
    struct tm tm_info;
    localtime_r(&now, &tm_info);
    char cur_time[32];
    strftime(cur_time, sizeof(cur_time), "%I:%M %p", &tm_info);

    GtkWidget *lbl_time = gtk_label_new(cur_time);
    GtkStyleContext *t_ctx = gtk_widget_get_style_context(lbl_time);
    gtk_style_context_add_class(t_ctx, "popup-time");
    gtk_box_pack_start(GTK_BOX(vbox), lbl_time, FALSE, FALSE, 0);

    /* Title & Name */
    GtkWidget *lbl_title = gtk_label_new(alarm_name);
    GtkStyleContext *title_ctx = gtk_widget_get_style_context(lbl_title);
    gtk_style_context_add_class(title_ctx, "popup-title");
    gtk_box_pack_start(GTK_BOX(vbox), lbl_title, FALSE, FALSE, 0);

    /* Blasting details */
    char badge_buf[256];
    snprintf(badge_buf, sizeof(badge_buf), "🔊 Blasting Built-in Speakers @ %d%% Volume", volume);
    GtkWidget *lbl_badge = gtk_label_new(badge_buf);
    GtkStyleContext *b_ctx = gtk_widget_get_style_context(lbl_badge);
    gtk_style_context_add_class(b_ctx, "popup-badge");
    gtk_box_pack_start(GTK_BOX(vbox), lbl_badge, FALSE, FALSE, 0);

    /* Track Name */
    char track_buf[512];
    snprintf(track_buf, sizeof(track_buf), "🎵 %s", track_title ? track_title : "Random Music Track");
    GtkWidget *lbl_track = gtk_label_new(track_buf);
    gtk_label_set_ellipsize(GTK_LABEL(lbl_track), PANGO_ELLIPSIZE_MIDDLE);
    GtkStyleContext *tr_ctx = gtk_widget_get_style_context(lbl_track);
    gtk_style_context_add_class(tr_ctx, "popup-track");
    gtk_box_pack_start(GTK_BOX(vbox), lbl_track, FALSE, FALSE, 0);

    /* Buttons Box */
    GtkWidget *btn_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 16);
    gtk_widget_set_halign(btn_box, GTK_ALIGN_CENTER);
    gtk_widget_set_margin_top(btn_box, 16);
    gtk_box_pack_start(GTK_BOX(vbox), btn_box, FALSE, FALSE, 0);

    /* Dismiss Button */
    GtkWidget *btn_dismiss = gtk_button_new_with_label("🛑 DISMISS ALARM (Space)");
    GtkStyleContext *d_ctx = gtk_widget_get_style_context(btn_dismiss);
    gtk_style_context_add_class(d_ctx, "btn-dismiss");
    g_signal_connect(btn_dismiss, "clicked", G_CALLBACK(on_popup_dismiss_clicked), NULL);
    gtk_box_pack_start(GTK_BOX(btn_box), btn_dismiss, FALSE, FALSE, 0);

    /* Snooze Button */
    GtkWidget *btn_snooze = gtk_button_new_with_label("💤 SNOOZE 5 MIN (S)");
    GtkStyleContext *s_ctx = gtk_widget_get_style_context(btn_snooze);
    gtk_style_context_add_class(s_ctx, "btn-snooze");
    g_signal_connect(btn_snooze, "clicked", G_CALLBACK(on_popup_snooze_clicked), NULL);
    gtk_box_pack_start(GTK_BOX(btn_box), btn_snooze, FALSE, FALSE, 0);

    gtk_widget_show_all(win);
    gtk_main();
}

/* --------------------------------------------------------------------------
 * Main GTK Clock Application GUI
 * -------------------------------------------------------------------------- */
typedef struct {
    GtkWidget *window;
    GtkWidget *alarm_list_box;
    GtkWidget *lbl_clock;
    GtkWidget *lbl_next_alarm;
    GtkWidget *btn_test;
    AlarmConfig *cfg;
} GuiApp;

static pid_t test_audio_pid = 0;
static guint test_timeout_id = 0;

static void refresh_alarm_list(GuiApp *app);

static gboolean on_clock_tick(gpointer user_data) {
    GuiApp *app = (GuiApp *)user_data;
    time_t now = time(NULL);
    struct tm tm_info;
    localtime_r(&now, &tm_info);

    char time_str[32];
    strftime(time_str, sizeof(time_str), "%H:%M:%S", &tm_info);
    gtk_label_set_text(GTK_LABEL(app->lbl_clock), time_str);

    time_t next_t = 0;
    Alarm *next_a = config_get_next_alarm(app->cfg, now, &next_t);
    if (next_a && next_t > now) {
        long diff = (long)(next_t - now);
        int h = diff / 3600;
        int m = (diff % 3600) / 60;
        char next_str[128];
        snprintf(next_str, sizeof(next_str), "Next: %02d:%02d (in %dh %dm)",
                 next_a->hour, next_a->minute, h, m);
        gtk_label_set_text(GTK_LABEL(app->lbl_next_alarm), next_str);
    } else {
        gtk_label_set_text(GTK_LABEL(app->lbl_next_alarm), "No active alarms");
    }
    return TRUE;
}

static void on_alarm_toggle(GtkSwitch *sw, gboolean state, gpointer user_data) {
    (void)sw;
    Alarm *a = (Alarm *)user_data;
    a->enabled = state;
    AlarmConfig *cfg = config_load();
    for (GList *l = cfg->alarms; l != NULL; l = l->next) {
        Alarm *item = (Alarm *)l->data;
        if (strcmp(item->id, a->id) == 0) {
            item->enabled = state;
            break;
        }
    }
    config_save(cfg);
    config_free(cfg);
}

static void on_alarm_delete_clicked(GtkButton *btn, gpointer user_data) {
    (void)btn;
    GtkWidget *dialog;
    Alarm *a = (Alarm *)user_data;
    GuiApp *app = g_object_get_data(G_OBJECT(btn), "app");

    dialog = gtk_message_dialog_new(GTK_WINDOW(app->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        GTK_MESSAGE_QUESTION,
        GTK_BUTTONS_YES_NO,
        "Are you sure you want to delete alarm '%s' (%02d:%02d)?",
        a->name, a->hour, a->minute);

    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_YES) {
        for (GList *l = app->cfg->alarms; l != NULL; l = l->next) {
            if (l->data == a) {
                app->cfg->alarms = g_list_delete_link(app->cfg->alarms, l);
                alarm_free(a);
                break;
            }
        }
        config_save(app->cfg);
        refresh_alarm_list(app);
    }
    gtk_widget_destroy(dialog);
}

static void open_edit_dialog(GuiApp *app, Alarm *existing_alarm) {
    GtkWidget *dlg = gtk_dialog_new_with_buttons(
        existing_alarm ? "Edit Alarm" : "Add New Alarm",
        GTK_WINDOW(app->window),
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "_Cancel", GTK_RESPONSE_CANCEL,
        "_Save", GTK_RESPONSE_ACCEPT,
        NULL
    );
    gtk_window_set_default_size(GTK_WINDOW(dlg), 420, 360);

    GtkWidget *content = gtk_dialog_get_content_area(GTK_DIALOG(dlg));
    GtkWidget *grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(grid), 12);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 14);
    gtk_container_set_border_width(GTK_CONTAINER(grid), 18);
    gtk_container_add(GTK_CONTAINER(content), grid);

    /* Time inputs */
    GtkWidget *lbl_time = gtk_label_new("Alarm Time:");
    gtk_grid_attach(GTK_GRID(grid), lbl_time, 0, 0, 1, 1);

    GtkWidget *time_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    GtkAdjustment *adj_h = gtk_adjustment_new(existing_alarm ? existing_alarm->hour : 4, 0, 23, 1, 1, 0);
    GtkWidget *spin_h = gtk_spin_button_new(adj_h, 1, 0);
    GtkWidget *colon = gtk_label_new(":");
    GtkAdjustment *adj_m = gtk_adjustment_new(existing_alarm ? existing_alarm->minute : 0, 0, 59, 1, 5, 0);
    GtkWidget *spin_m = gtk_spin_button_new(adj_m, 1, 0);

    gtk_box_pack_start(GTK_BOX(time_box), spin_h, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(time_box), colon, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(time_box), spin_m, FALSE, FALSE, 0);
    gtk_grid_attach(GTK_GRID(grid), time_box, 1, 0, 1, 1);

    /* Name input */
    GtkWidget *lbl_name = gtk_label_new("Alarm Label:");
    gtk_grid_attach(GTK_GRID(grid), lbl_name, 0, 1, 1, 1);
    GtkWidget *entry_name = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(entry_name), existing_alarm ? existing_alarm->name : "Morning Wake Up");
    gtk_grid_attach(GTK_GRID(grid), entry_name, 1, 1, 1, 1);

    /* Repeat combo */
    GtkWidget *lbl_rep = gtk_label_new("Repeat:");
    gtk_grid_attach(GTK_GRID(grid), lbl_rep, 0, 2, 1, 1);
    GtkWidget *combo_rep = gtk_combo_box_text_new();
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_rep), "Daily");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_rep), "Weekdays (Mon-Fri)");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_rep), "Weekends (Sat-Sun)");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_rep), "Once");
    gtk_combo_box_set_active(GTK_COMBO_BOX(combo_rep), existing_alarm ? existing_alarm->repeat_mode : 0);
    gtk_grid_attach(GTK_GRID(grid), combo_rep, 1, 2, 1, 1);

    /* Sound source combo */
    GtkWidget *lbl_snd = gtk_label_new("Sound Source:");
    gtk_grid_attach(GTK_GRID(grid), lbl_snd, 0, 3, 1, 1);
    GtkWidget *combo_snd = gtk_combo_box_text_new();
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_snd), "Random Track from ~/Music");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_snd), "Specific Folder");
    gtk_combo_box_text_append_text(GTK_COMBO_BOX_TEXT(combo_snd), "Specific Audio File");
    gtk_combo_box_set_active(GTK_COMBO_BOX(combo_snd), existing_alarm ? existing_alarm->sound_type : 0);
    gtk_grid_attach(GTK_GRID(grid), combo_snd, 1, 3, 1, 1);

    /* Sound path chooser */
    GtkWidget *lbl_path = gtk_label_new("Custom Path:");
    gtk_grid_attach(GTK_GRID(grid), lbl_path, 0, 4, 1, 1);
    GtkWidget *btn_file = gtk_file_chooser_button_new("Select Audio File / Folder", GTK_FILE_CHOOSER_ACTION_OPEN);
    if (existing_alarm && existing_alarm->sound_path) {
        gtk_file_chooser_set_filename(GTK_FILE_CHOOSER(btn_file), existing_alarm->sound_path);
    }
    gtk_grid_attach(GTK_GRID(grid), btn_file, 1, 4, 1, 1);

    /* Volume scale (up to 150%) */
    GtkWidget *lbl_vol = gtk_label_new("Volume (%):");
    gtk_grid_attach(GTK_GRID(grid), lbl_vol, 0, 5, 1, 1);
    GtkAdjustment *adj_vol = gtk_adjustment_new(existing_alarm ? existing_alarm->volume : 150, 0, 150, 5, 10, 0);
    GtkWidget *scale_vol = gtk_scale_new(GTK_ORIENTATION_HORIZONTAL, adj_vol);
    gtk_scale_set_value_pos(GTK_SCALE(scale_vol), GTK_POS_RIGHT);
    gtk_grid_attach(GTK_GRID(grid), scale_vol, 1, 5, 1, 1);

    gtk_widget_show_all(dlg);

    if (gtk_dialog_run(GTK_DIALOG(dlg)) == GTK_RESPONSE_ACCEPT) {
        Alarm *a = existing_alarm;
        if (!a) {
            char new_id[32];
            snprintf(new_id, sizeof(new_id), "alarm_%ld", (long)time(NULL));
            a = g_new0(Alarm, 1);
            a->id = g_strdup(new_id);
            a->enabled = TRUE;
            a->snooze_min = 5;
            app->cfg->alarms = g_list_append(app->cfg->alarms, a);
        }

        g_free(a->name);
        a->name = g_strdup(gtk_entry_get_text(GTK_ENTRY(entry_name)));
        a->hour = gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(spin_h));
        a->minute = gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(spin_m));
        a->repeat_mode = (RepeatMode)gtk_combo_box_get_active(GTK_COMBO_BOX(combo_rep));
        a->sound_type = (SoundType)gtk_combo_box_get_active(GTK_COMBO_BOX(combo_snd));
        a->volume = (int)gtk_range_get_value(GTK_RANGE(scale_vol));

        char *chosen = gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(btn_file));
        g_free(a->sound_path);
        a->sound_path = chosen ? chosen : g_strdup(DEFAULT_MUSIC_DIR);

        config_save(app->cfg);
        refresh_alarm_list(app);
    }
    gtk_widget_destroy(dlg);
}

static void on_alarm_edit_clicked(GtkButton *btn, gpointer user_data) {
    Alarm *a = (Alarm *)user_data;
    GuiApp *app = g_object_get_data(G_OBJECT(btn), "app");
    open_edit_dialog(app, a);
}

static void on_add_alarm_clicked(GtkButton *btn, gpointer user_data) {
    (void)btn;
    GuiApp *app = (GuiApp *)user_data;
    open_edit_dialog(app, NULL);
}

static gboolean on_test_timeout(gpointer user_data) {
    GuiApp *app = (GuiApp *)user_data;
    if (test_audio_pid > 0) {
        kill(test_audio_pid, SIGTERM);
        kill(test_audio_pid, SIGKILL);
        test_audio_pid = 0;
    }
    test_timeout_id = 0;
    if (app && app->btn_test) {
        gtk_button_set_label(GTK_BUTTON(app->btn_test), "🔔 Test Audio (150%)");
    }
    return G_SOURCE_REMOVE;
}

static void on_test_alarm_clicked(GtkButton *btn, gpointer user_data) {
    GuiApp *app = (GuiApp *)user_data;

    if (test_audio_pid > 0) {
        /* Already playing: stop immediately */
        if (test_timeout_id > 0) {
            g_source_remove(test_timeout_id);
            test_timeout_id = 0;
        }
        kill(test_audio_pid, SIGTERM);
        kill(test_audio_pid, SIGKILL);
        test_audio_pid = 0;
        gtk_button_set_label(btn, "🔔 Test Audio (150%)");
        return;
    }

    AlarmConfig *cfg = app->cfg;
    char *sink = cfg->default_speaker_sink ? g_strdup(cfg->default_speaker_sink) : detect_speaker_sink();
    char *song = pick_audio_file(SOUND_RANDOM_MUSIC, DEFAULT_MUSIC_DIR);
    if (!song) song = get_fallback_alarm_file();

    /* Unmute speaker and set 150% asynchronously on candidate sink AND @DEFAULT_SINK@ */
    char cmd[512];
    if (sink && g_strcmp0(sink, "@DEFAULT_SINK@") != 0) {
        snprintf(cmd, sizeof(cmd), "pactl set-sink-mute %s 0 2>/dev/null; pactl set-sink-volume %s 150%% 2>/dev/null; pactl set-sink-port %s analog-output-speaker 2>/dev/null", sink, sink, sink);
        system(cmd);
    }
    snprintf(cmd, sizeof(cmd), "pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null; pactl set-sink-volume @DEFAULT_SINK@ 150%% 2>/dev/null");
    system(cmd);

    char opt_vol[64];
    snprintf(opt_vol, sizeof(opt_vol), "--volume=150");
    char opt_dev[512];
    if (sink && sink[0]) {
        snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse/%s", sink);
    } else {
        snprintf(opt_dev, sizeof(opt_dev), "--audio-device=pulse");
    }

    test_audio_pid = fork();
    if (test_audio_pid == 0) {
        if (song) {
            execlp("mpv", "mpv",
                   "--no-config",
                   "--no-video",
                   "--loop-file=inf",
                   opt_vol,
                   opt_dev,
                   song,
                   NULL);
        }
        _exit(1);
    }

    g_free(sink);
    g_free(song);

    gtk_button_set_label(btn, "⏹️ Stop Test Audio");
    test_timeout_id = g_timeout_add_seconds(5, on_test_timeout, app);
}

static void refresh_alarm_list(GuiApp *app) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(app->alarm_list_box));
    for (GList *l = children; l != NULL; l = l->next) {
        gtk_widget_destroy(GTK_WIDGET(l->data));
    }
    g_list_free(children);

    for (GList *l = app->cfg->alarms; l != NULL; l = l->next) {
        Alarm *a = (Alarm *)l->data;

        GtkWidget *card = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 14);
        GtkStyleContext *card_ctx = gtk_widget_get_style_context(card);
        gtk_style_context_add_class(card_ctx, "alarm-card");
        if (!a->enabled) {
            gtk_style_context_add_class(card_ctx, "disabled");
        }

        /* Left side: Time & Details */
        GtkWidget *left_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);

        char time_str[32];
        snprintf(time_str, sizeof(time_str), "%02d:%02d", a->hour, a->minute);
        GtkWidget *lbl_time = gtk_label_new(time_str);
        gtk_widget_set_halign(lbl_time, GTK_ALIGN_START);
        GtkStyleContext *t_ctx = gtk_widget_get_style_context(lbl_time);
        gtk_style_context_add_class(t_ctx, "alarm-time");
        gtk_box_pack_start(GTK_BOX(left_box), lbl_time, FALSE, FALSE, 0);

        GtkWidget *lbl_name = gtk_label_new(a->name);
        gtk_widget_set_halign(lbl_name, GTK_ALIGN_START);
        GtkStyleContext *n_ctx = gtk_widget_get_style_context(lbl_name);
        gtk_style_context_add_class(n_ctx, "alarm-name");
        gtk_box_pack_start(GTK_BOX(left_box), lbl_name, FALSE, FALSE, 0);

        const char *rep_str = "Daily";
        if (a->repeat_mode == REPEAT_WEEKDAYS) rep_str = "Weekdays (Mon-Fri)";
        else if (a->repeat_mode == REPEAT_WEEKENDS) rep_str = "Weekends (Sat-Sun)";
        else if (a->repeat_mode == REPEAT_ONCE) rep_str = "Once";
        else if (a->repeat_mode == REPEAT_CUSTOM) rep_str = "Custom Days";

        const char *snd_str = (a->sound_type == SOUND_RANDOM_MUSIC) ? "Random ~/Music" :
                              (a->sound_type == SOUND_FOLDER) ? "Custom Folder" : "Audio Track";

        char meta_buf[256];
        snprintf(meta_buf, sizeof(meta_buf), "%s • %s • 🔊 %d%%", rep_str, snd_str, a->volume);
        GtkWidget *lbl_meta = gtk_label_new(meta_buf);
        gtk_widget_set_halign(lbl_meta, GTK_ALIGN_START);
        GtkStyleContext *m_ctx = gtk_widget_get_style_context(lbl_meta);
        gtk_style_context_add_class(m_ctx, "alarm-meta");
        gtk_box_pack_start(GTK_BOX(left_box), lbl_meta, FALSE, FALSE, 0);

        gtk_box_pack_start(GTK_BOX(card), left_box, TRUE, TRUE, 0);

        /* Right side: Switch, Edit, Delete */
        GtkWidget *right_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
        gtk_widget_set_valign(right_box, GTK_ALIGN_CENTER);

        GtkWidget *sw = gtk_switch_new();
        gtk_switch_set_active(GTK_SWITCH(sw), a->enabled);
        g_signal_connect(sw, "state-set", G_CALLBACK(on_alarm_toggle), a);
        gtk_box_pack_start(GTK_BOX(right_box), sw, FALSE, FALSE, 0);

        GtkWidget *btn_edit = gtk_button_new_with_label("✏️");
        GtkStyleContext *e_ctx = gtk_widget_get_style_context(btn_edit);
        gtk_style_context_add_class(e_ctx, "btn-primary");
        g_object_set_data(G_OBJECT(btn_edit), "app", app);
        g_signal_connect(btn_edit, "clicked", G_CALLBACK(on_alarm_edit_clicked), a);
        gtk_box_pack_start(GTK_BOX(right_box), btn_edit, FALSE, FALSE, 0);

        GtkWidget *btn_del = gtk_button_new_with_label("🗑️");
        GtkStyleContext *d_ctx = gtk_widget_get_style_context(btn_del);
        gtk_style_context_add_class(d_ctx, "btn-danger");
        g_object_set_data(G_OBJECT(btn_del), "app", app);
        g_signal_connect(btn_del, "clicked", G_CALLBACK(on_alarm_delete_clicked), a);
        gtk_box_pack_start(GTK_BOX(right_box), btn_del, FALSE, FALSE, 0);

        gtk_box_pack_start(GTK_BOX(card), right_box, FALSE, FALSE, 0);
        gtk_box_pack_start(GTK_BOX(app->alarm_list_box), card, FALSE, FALSE, 0);
    }
    gtk_widget_show_all(app->alarm_list_box);
}

static void run_gui_app(int argc, char **argv) {
    if (!gtk_init_check(&argc, &argv) || gdk_display_get_default() == NULL || gdk_screen_get_default() == NULL) {
        fprintf(stderr, "sys-alarm: Cannot open display. Running in headless mode or DISPLAY is not set.\n");
        return;
    }

    GuiApp *app = g_new0(GuiApp, 1);
    app->cfg = config_load();

    g_set_prgname("sys-alarm");

    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css, STYLE_CSS, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(css),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );

    app->window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(app->window), "⏰ sys-alarm");
    gtk_window_set_role(GTK_WINDOW(app->window), "sys-alarm");
    gtk_window_set_default_size(GTK_WINDOW(app->window), 540, 620);
    gtk_window_set_position(GTK_WINDOW(app->window), GTK_WIN_POS_CENTER);

    GtkStyleContext *w_ctx = gtk_widget_get_style_context(app->window);
    gtk_style_context_add_class(w_ctx, "alarm-window");

    g_signal_connect(app->window, "destroy", G_CALLBACK(gtk_main_quit), NULL);

    GtkWidget *main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(app->window), main_box);

    /* Header Bar */
    GtkWidget *header = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    GtkStyleContext *h_ctx = gtk_widget_get_style_context(header);
    gtk_style_context_add_class(h_ctx, "header-bar");

    GtkWidget *lbl_app = gtk_label_new("⏰ sys-alarm");
    GtkStyleContext *app_ctx = gtk_widget_get_style_context(lbl_app);
    gtk_style_context_add_class(app_ctx, "header-title");
    gtk_box_pack_start(GTK_BOX(header), lbl_app, FALSE, FALSE, 0);

    app->lbl_clock = gtk_label_new("00:00:00");
    GtkStyleContext *clk_ctx = gtk_widget_get_style_context(app->lbl_clock);
    gtk_style_context_add_class(clk_ctx, "header-clock");
    gtk_box_pack_start(GTK_BOX(header), app->lbl_clock, TRUE, TRUE, 0);

    app->lbl_next_alarm = gtk_label_new("Loading next alarm...");
    GtkStyleContext *b_ctx = gtk_widget_get_style_context(app->lbl_next_alarm);
    gtk_style_context_add_class(b_ctx, "header-badge");
    gtk_box_pack_start(GTK_BOX(header), app->lbl_next_alarm, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(main_box), header, FALSE, FALSE, 0);

    /* Actions Toolbar */
    GtkWidget *tools = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(tools), 12);

    GtkWidget *btn_add = gtk_button_new_with_label("➕ Add Alarm");
    GtkStyleContext *add_ctx = gtk_widget_get_style_context(btn_add);
    gtk_style_context_add_class(add_ctx, "btn-primary");
    g_signal_connect(btn_add, "clicked", G_CALLBACK(on_add_alarm_clicked), app);
    gtk_box_pack_start(GTK_BOX(tools), btn_add, FALSE, FALSE, 0);

    GtkWidget *btn_test = gtk_button_new_with_label("🔔 Test Audio (150%)");
    app->btn_test = btn_test;
    GtkStyleContext *t_ctx = gtk_widget_get_style_context(btn_test);
    gtk_style_context_add_class(t_ctx, "btn-danger");
    g_signal_connect(btn_test, "clicked", G_CALLBACK(on_test_alarm_clicked), app);
    gtk_box_pack_start(GTK_BOX(tools), btn_test, FALSE, FALSE, 0);

    gtk_box_pack_start(GTK_BOX(main_box), tools, FALSE, FALSE, 0);

    /* Scrolled List Container */
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_box_pack_start(GTK_BOX(main_box), scroll, TRUE, TRUE, 0);

    app->alarm_list_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(scroll), app->alarm_list_box);

    refresh_alarm_list(app);
    on_clock_tick(app);
    g_timeout_add_seconds(1, on_clock_tick, app);

    gtk_widget_show_all(app->window);
    gtk_main();
}

/* --------------------------------------------------------------------------
 * Main Entry Point
 * -------------------------------------------------------------------------- */
int main(int argc, char **argv) {
    if (argc > 1 && (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0 || strcmp(argv[1], "help") == 0)) {
        printf("Usage: sys-alarm [command]\n\n"
               "Lightweight GTK3 & RTC wake alarm clock for Arch Linux / BSPWM.\n\n"
               "Available commands:\n"
               "  gui              Open interactive Clock GUI (default)\n"
               "  ring [alarm_id]  Trigger alarm ring and launch modal popup\n"
               "  dismiss          Dismiss currently ringing alarm\n"
               "  snooze [mins]    Snooze currently ringing alarm (default 5m)\n"
               "  list             View active configured alarms and next trigger countdown\n"
               "  daemon           Run zero-overhead daemon monitor loop\n"
               "  test             Test audio blast and speaker routing (4s test)\n"
               "  sync             Synchronize systemd RTC wake timer\n"
               "  add <HH:MM> [name] [repeat: daily|weekdays|weekends|once]\n"
               "  --help, -h       Display this help message\n");
        return 0;
    }

    if (argc <= 1 || strcmp(argv[1], "gui") == 0) {
        run_gui_app(argc, argv);
        return 0;
    }

    if (strcmp(argv[1], "ring") == 0) {
        const char *aid = (argc >= 3) ? argv[2] : NULL;
        return cmd_ring(aid);
    }
    if (strcmp(argv[1], "dismiss") == 0) {
        return cmd_dismiss();
    }
    if (strcmp(argv[1], "snooze") == 0) {
        int mins = (argc >= 3) ? atoi(argv[2]) : 5;
        return cmd_snooze(mins);
    }
    if (strcmp(argv[1], "list") == 0) {
        return cmd_list();
    }
    if (strcmp(argv[1], "daemon") == 0) {
        return cmd_daemon();
    }
    if (strcmp(argv[1], "test") == 0) {
        return cmd_test();
    }
    if (strcmp(argv[1], "sync") == 0) {
        AlarmConfig *cfg = config_load();
        sync_system_timers(cfg);
        config_free(cfg);
        printf("System timers and RTC wakealarm synced.\n");
        return 0;
    }
    if (strcmp(argv[1], "add") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: sys-alarm add <HH:MM> [name] [repeat: daily|weekdays|weekends|once]\n");
            return 1;
        }
        int h = 0, m = 0;
        if (sscanf(argv[2], "%d:%d", &h, &m) != 2) {
            fprintf(stderr, "Invalid time format. Use HH:MM (e.g. 04:00)\n");
            return 1;
        }
        const char *name = (argc >= 4) ? argv[3] : "Wake Up";
        RepeatMode rep = REPEAT_DAILY;
        if (argc >= 5) {
            if (strcasecmp(argv[4], "weekdays") == 0) rep = REPEAT_WEEKDAYS;
            else if (strcasecmp(argv[4], "weekends") == 0) rep = REPEAT_WEEKENDS;
            else if (strcasecmp(argv[4], "once") == 0) rep = REPEAT_ONCE;
        }
        AlarmConfig *cfg = config_load();
        char new_id[32];
        snprintf(new_id, sizeof(new_id), "alarm_%ld", (long)time(NULL));
        Alarm *a = alarm_create_default(new_id, name, h, m);
        a->repeat_mode = rep;
        cfg->alarms = g_list_append(cfg->alarms, a);
        config_save(cfg);
        printf("Added alarm %s at %02d:%02d\n", name, h, m);
        config_free(cfg);
        return 0;
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    fprintf(stderr, "Available commands: gui, ring, dismiss, snooze, list, daemon, test, sync, add\n");
    return 1;
}
