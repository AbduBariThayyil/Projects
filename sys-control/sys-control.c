/* =============================================================
 * sys-control: Unified High-Speed System Controller for BSPWM
 * High performance C binary replacing bash script sprawl
 * Sub-2ms hotkey latency, native Xlib client traversal,
 * direct sysfs backlight control, audio OSD synchronization
 * ============================================================= */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <time.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <glib.h>

/* Execute a shell command synchronously and get its trimmed output */
static int exec_cmd_output(const char *cmd, char *out, size_t out_sz) {
    if (!out || out_sz == 0) return -1;
    out[0] = '\0';
    FILE *f = popen(cmd, "r");
    if (!f) return -1;
    if (fgets(out, out_sz, f)) {
        g_strstrip(out);
    }
    return pclose(f);
}

/* Spawn a detached background process cleanly */
static void spawn_async(const char *cmd) {
    if (!cmd || !*cmd) return;

    /* Check for shell metacharacters: |, &, ;, >, <, $, ` */
    int has_meta = (strpbrk(cmd, "|&;><$`") != NULL);
    gchar **argv = NULL;
    gint argc = 0;

    if (!has_meta) {
        if (!g_shell_parse_argv(cmd, &argc, &argv, NULL) || !argv || !argv[0]) {
            if (argv) {
                g_strfreev(argv);
                argv = NULL;
            }
            has_meta = 1;
        }
    }

    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }

        if (!has_meta && argv) {
            execvp(argv[0], argv);
            /* Fallback to shell if execvp fails */
            execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
            _exit(127);
        } else {
            execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
            _exit(127);
        }
    }

    if (argv) {
        g_strfreev(argv);
    }
}

/* -------------------------------------------------------------
 * 1. Volume & Audio Control (pamixer & playerctl)
 * ------------------------------------------------------------- */
static void trigger_vol_osd(int vol, int muted) {
    char cmd[128];
    if (muted) {
        snprintf(cmd, sizeof(cmd), "sys-notif --osd volume 0 muted");
    } else {
        snprintf(cmd, sizeof(cmd), "sys-notif --osd volume %d", vol);
    }
    spawn_async(cmd);
}

static void ctl_volume(const char *action, const char *step_str) {
    int step = step_str ? atoi(step_str) : 5;
    if (step <= 0) step = 5;

    char cmd[256];
    char out[64] = {0};

    if (strcmp(action, "inc") == 0 || strcmp(action, "--vol-inc") == 0 || strcmp(action, "vol-inc") == 0 || strcmp(action, "up") == 0) {
        snprintf(cmd, sizeof(cmd), "pamixer --allow-boost --set-limit 150 -u -i %d --get-volume 2>/dev/null", step);
        exec_cmd_output(cmd, out, sizeof(out));
        int v = atoi(out);
        trigger_vol_osd(v, 0);
    }
    else if (strcmp(action, "dec") == 0 || strcmp(action, "--vol-dec") == 0 || strcmp(action, "vol-dec") == 0 || strcmp(action, "down") == 0) {
        snprintf(cmd, sizeof(cmd), "pamixer --allow-boost --set-limit 150 -u -d %d --get-volume 2>/dev/null", step);
        exec_cmd_output(cmd, out, sizeof(out));
        int v = atoi(out);
        trigger_vol_osd(v, 0);
    }
    else if (strcmp(action, "toggle") == 0 || strcmp(action, "--vol-toggle") == 0 || strcmp(action, "vol-toggle") == 0 || strcmp(action, "mute") == 0 || strcmp(action, "mute-toggle") == 0) {
        exec_cmd_output("pamixer -t --get-volume-human 2>/dev/null", out, sizeof(out));
        if (strstr(out, "muted") != NULL) {
            trigger_vol_osd(0, 1);
        } else {
            int v = atoi(out);
            trigger_vol_osd(v, 0);
        }
    }
    else if (strcmp(action, "get") == 0 || strcmp(action, "--get-vol") == 0 || strcmp(action, "--vol-get") == 0) {
        exec_cmd_output("pamixer --get-volume 2>/dev/null", out, sizeof(out));
        printf("%s\n", out);
    }
    else if (strcmp(action, "status") == 0 || strcmp(action, "--vol-status") == 0) {
        exec_cmd_output("pamixer --get-volume-human 2>/dev/null", out, sizeof(out));
        printf("%s\n", out);
    }
}

static void ctl_media(const char *action) {
    if (strcmp(action, "previous") == 0 || strcmp(action, "--previous") == 0 || strcmp(action, "prev") == 0) {
        spawn_async("playerctl previous");
    } else if (strcmp(action, "next") == 0 || strcmp(action, "--next") == 0) {
        spawn_async("playerctl next");
    } else if (strcmp(action, "toggle") == 0 || strcmp(action, "--toggle") == 0 || strcmp(action, "play-pause") == 0) {
        spawn_async("playerctl play-pause");
    } else if (strcmp(action, "play") == 0 || strcmp(action, "--play") == 0) {
        spawn_async("playerctl play");
    } else if (strcmp(action, "pause") == 0 || strcmp(action, "--pause") == 0) {
        spawn_async("playerctl pause");
    } else if (strcmp(action, "stop") == 0 || strcmp(action, "--stop") == 0) {
        spawn_async("playerctl stop");
    } else if (strcmp(action, "status") == 0 || strcmp(action, "--status") == 0) {
        char out[64] = {0};
        exec_cmd_output("playerctl status 2>/dev/null", out, sizeof(out));
        printf("%s\n", out[0] ? out : "Stopped");
    } else if (strcmp(action, "title") == 0 || strcmp(action, "--title") == 0) {
        char out[256] = {0};
        exec_cmd_output("playerctl metadata --format '{{title}}' 2>/dev/null", out, sizeof(out));
        printf("%s\n", out[0] ? out : "No Music");
    } else if (strcmp(action, "artist") == 0 || strcmp(action, "--artist") == 0) {
        char out[256] = {0};
        exec_cmd_output("playerctl metadata --format '{{artist}}' 2>/dev/null", out, sizeof(out));
        printf("%s\n", out[0] ? out : "No Artist");
    }
}

/* -------------------------------------------------------------
 * 2. Backlight Control (Direct sysfs with brightnessctl fallback)
 * ------------------------------------------------------------- */
static int get_backlight_dir(char *buf, size_t sz) {
    if (!buf || sz == 0) return -1;
    buf[0] = '\0';
    DIR *d = opendir("/sys/class/backlight");
    if (!d) return -1;
    struct dirent *de;
    while ((de = readdir(d))) {
        if (de->d_name[0] != '.') {
            snprintf(buf, sz, "/sys/class/backlight/%s", de->d_name);
            break;
        }
    }
    closedir(d);
    return (buf[0] != '\0') ? 0 : -1;
}

static int get_sysfs_brightness_raw(int *cur_val, int *max_val, char *bri_path, size_t bri_sz) {
    char bl_dir[512];
    if (get_backlight_dir(bl_dir, sizeof(bl_dir)) != 0) return -1;

    char cur_path[600], max_path[600];
    snprintf(cur_path, sizeof(cur_path), "%s/actual_brightness", bl_dir);
    snprintf(max_path, sizeof(max_path), "%s/max_brightness", bl_dir);
    if (bri_path && bri_sz > 0) {
        snprintf(bri_path, bri_sz, "%s/brightness", bl_dir);
    }

    int max = 0;
    FILE *f = fopen(max_path, "r");
    if (f) {
        if (fscanf(f, "%d", &max) != 1) max = 0;
        fclose(f);
    }
    if (max <= 0) return -1;

    int cur = -1;
    f = fopen(cur_path, "r");
    if (f) {
        if (fscanf(f, "%d", &cur) != 1) cur = -1;
        fclose(f);
    }
    /* If actual_brightness was 0 or unreadable, check brightness file */
    if (cur <= 0) {
        char bri_p[600];
        snprintf(bri_p, sizeof(bri_p), "%s/brightness", bl_dir);
        f = fopen(bri_p, "r");
        if (f) {
            if (fscanf(f, "%d", &cur) != 1) cur = -1;
            fclose(f);
        }
    }
    if (cur < 0) cur = 0;

    if (cur_val) *cur_val = cur;
    if (max_val) *max_val = max;
    return 0;
}

static int get_sysfs_brightness_pct(void) {
    int cur = 0, max = 1;
    if (get_sysfs_brightness_raw(&cur, &max, NULL, 0) != 0) return -1;
    if (max <= 0) return 0;
    return (int)(((double)cur / (double)max) * 100.0 + 0.5);
}

static void trigger_bri_osd(int pct) {
    char cmd[128];
    snprintf(cmd, sizeof(cmd), "sys-notif --osd brightness %d", pct);
    spawn_async(cmd);
}

static void ctl_brightness(const char *action, const char *step_str) {
    int step = step_str ? atoi(step_str) : 5;
    if (step <= 0) step = 5;

    int is_up = (strcmp(action, "up") == 0 || strcmp(action, "--bri-up") == 0 ||
                 strcmp(action, "bri-up") == 0 || strcmp(action, "--bri-inc") == 0 ||
                 strcmp(action, "brightness-up") == 0);
    int is_down = (strcmp(action, "down") == 0 || strcmp(action, "--bri-down") == 0 ||
                   strcmp(action, "bri-down") == 0 || strcmp(action, "--bri-dec") == 0 ||
                   strcmp(action, "brightness-down") == 0);
    int is_get = (strcmp(action, "get") == 0 || strcmp(action, "--get-bri") == 0 ||
                  strcmp(action, "--bri-get") == 0 || strcmp(action, "get-bri") == 0);

    if (is_get) {
        int pct = get_sysfs_brightness_pct();
        printf("%d%%\n", pct >= 0 ? pct : 0);
        return;
    }

    if (is_up || is_down) {
        int cur = 0, max = 0;
        char bri_path[600] = {0};
        int direct_written = 0;

        if (get_sysfs_brightness_raw(&cur, &max, bri_path, sizeof(bri_path)) == 0 && max > 0) {
            int delta = (step * max + 50) / 100;
            if (delta < 1) delta = 1;
            int new_val = is_up ? (cur + delta) : (cur - delta);
            if (new_val < 1) new_val = 1;
            if (new_val > max) new_val = max;

            int fd = open(bri_path, O_WRONLY);
            if (fd >= 0) {
                char val_str[32];
                int len = snprintf(val_str, sizeof(val_str), "%d\n", new_val);
                if (write(fd, val_str, len) == len) {
                    direct_written = 1;
                    int pct = (int)(((double)new_val / (double)max) * 100.0 + 0.5);
                    trigger_bri_osd(pct);
                }
                close(fd);
            }
        }

        if (!direct_written) {
            char cmd[128];
            if (is_up) {
                snprintf(cmd, sizeof(cmd), "brightnessctl set +%d%% >/dev/null 2>&1", step);
            } else {
                snprintf(cmd, sizeof(cmd), "brightnessctl set %d%%- >/dev/null 2>&1", step);
            }
            system(cmd);
            int pct = get_sysfs_brightness_pct();
            trigger_bri_osd(pct);
        }
    }
}

/* -------------------------------------------------------------
 * 3. Hider Control (Fast Native Node Hide, Study Panic & Bar)
 * ------------------------------------------------------------- */
static int x11_nonfatal_err(Display *dpy, XErrorEvent *ev) {
    (void)dpy;
    (void)ev;
    return 0;
}

static int run_argv_sync(const char *const argv[]) {
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }
        execvp(argv[0], (char *const *)argv);
        _exit(127);
    }
    int status = 0;
    if (waitpid(pid, &status, 0) < 0) return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : -1;
}

static void spawn_argv_detached(const char *const argv[], const char *workdir) {
    pid_t pid = fork();
    if (pid != 0) return;

    setsid();
    if (workdir && *workdir) {
        if (chdir(workdir) != 0) {
            /* keep current directory if chdir fails */
        }
    }
    int devnull = open("/dev/null", O_RDWR);
    if (devnull >= 0) {
        dup2(devnull, STDIN_FILENO);
        dup2(devnull, STDOUT_FILENO);
        dup2(devnull, STDERR_FILENO);
        if (devnull > 2) close(devnull);
    }
    execvp(argv[0], (char *const *)argv);
    _exit(127);
}

static int query_bspc_lines(const char *cmd, char lines[][32], int max_lines) {
    FILE *f = popen(cmd, "r");
    if (!f) return 0;
    int count = 0;
    char buf[64];
    while (count < max_lines && fgets(buf, sizeof(buf), f)) {
        g_strstrip(buf);
        if (buf[0] != '\0') {
            g_strlcpy(lines[count], buf, 32);
            count++;
        }
    }
    pclose(f);
    return count;
}

static int list_contains(const char *wid, char list[][32], int count) {
    for (int i = 0; i < count; i++) {
        if (strcmp(wid, list[i]) == 0) return 1;
    }
    return 0;
}

static void save_node_meta_and_hide(const char *wid_str, const char *desktop_hint, int capture_thumb) {
    if (!wid_str || !*wid_str) return;

    const char *thumb_dir = "/tmp/Minimize_thumbs";
    const char *meta_dir = "/tmp/Minimize_meta";
    g_mkdir_with_parents(thumb_dir, 0755);
    g_mkdir_with_parents(meta_dir, 0755);

    char desktop[64] = {0};
    if (desktop_hint && *desktop_hint) {
        g_strlcpy(desktop, desktop_hint, sizeof(desktop));
    } else {
        char qcmd[128];
        snprintf(qcmd, sizeof(qcmd), "bspc query -D -n %s --names 2>/dev/null", wid_str);
        exec_cmd_output(qcmd, desktop, sizeof(desktop));
    }

    char tree_json[4096] = {0};
    char tcmd[128];
    snprintf(tcmd, sizeof(tcmd), "bspc query -T -n %s 2>/dev/null", wid_str);
    FILE *tf = popen(tcmd, "r");
    if (tf) {
        size_t n = fread(tree_json, 1, sizeof(tree_json) - 1, tf);
        tree_json[n] = '\0';
        pclose(tf);
    }

    const char *state = "tiled";
    if (strstr(tree_json, "\"state\":\"floating\"") != NULL) {
        state = "floating";
    } else if (strstr(tree_json, "\"state\":\"fullscreen\"") != NULL) {
        state = "fullscreen";
    } else if (strstr(tree_json, "\"state\":\"pseudo_tiled\"") != NULL) {
        state = "pseudo_tiled";
    }

    char path[256];
    if (desktop[0] != '\0') {
        snprintf(path, sizeof(path), "%s/%s.desktop", meta_dir, wid_str);
        FILE *df = fopen(path, "w");
        if (df) {
            fprintf(df, "%s\n", desktop);
            fclose(df);
        }
    }

    snprintf(path, sizeof(path), "%s/%s.state", meta_dir, wid_str);
    FILE *sf = fopen(path, "w");
    if (sf) {
        fprintf(sf, "%s\n", state);
        fclose(sf);
    }

    if (capture_thumb) {
        char thumb_path[256];
        snprintf(thumb_path, sizeof(thumb_path), "%s/%s.jpg", thumb_dir, wid_str);
        const char *maim_argv[] = { "maim", "-i", wid_str, thumb_path, NULL };
        run_argv_sync(maim_argv);
    }

    const char *hide_argv[] = { "bspc", "node", wid_str, "-g", "hidden=on", NULL };
    run_argv_sync(hide_argv);
}

static void ctl_hider_node(const char *target_wid) {
    char wid[32] = {0};
    if (target_wid && *target_wid) {
        g_strlcpy(wid, target_wid, sizeof(wid));
    } else {
        exec_cmd_output("bspc query -N -n focused 2>/dev/null", wid, sizeof(wid));
    }
    if (wid[0] == '\0') return;
    save_node_meta_and_hide(wid, NULL, 1);
}

static void ctl_hider(const char *target) {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "/home/vibecoder/.config/bspwm/bin/Hider %s", target ? target : "");
    spawn_async(cmd);
}

static void read_x11_window_info(Display *dpy, Window w, char *res_name, size_t rn_sz,
                                 char *res_class, size_t rc_sz, char *title, size_t title_sz) {
    res_name[0] = '\0';
    res_class[0] = '\0';
    title[0] = '\0';
    if (!dpy || w == None) return;

    XClassHint ch = {0};
    if (XGetClassHint(dpy, w, &ch)) {
        if (ch.res_name) {
            g_strlcpy(res_name, ch.res_name, rn_sz);
            XFree(ch.res_name);
        }
        if (ch.res_class) {
            g_strlcpy(res_class, ch.res_class, rc_sz);
            XFree(ch.res_class);
        }
    }

    Atom net_wm_name = XInternAtom(dpy, "_NET_WM_NAME", False);
    Atom utf8 = XInternAtom(dpy, "UTF8_STRING", False);
    Atom actual_type = None;
    int actual_format = 0;
    unsigned long nitems = 0, bytes_after = 0;
    unsigned char *prop = NULL;
    if (XGetWindowProperty(dpy, w, net_wm_name, 0, 256, False, utf8,
                           &actual_type, &actual_format, &nitems, &bytes_after, &prop) == Success && prop) {
        g_strlcpy(title, (const char *)prop, title_sz);
        XFree(prop);
    } else {
        char *wm_name = NULL;
        if (XFetchName(dpy, w, &wm_name) && wm_name) {
            g_strlcpy(title, wm_name, title_sz);
            XFree(wm_name);
        }
    }
}

static int str_eq_any_ci(const char *s, const char *const *candidates, size_t n) {
    if (!s || !*s) return 0;
    for (size_t i = 0; i < n; i++) {
        if (strcasecmp(s, candidates[i]) == 0) return 1;
    }
    return 0;
}

static int is_terminal_window(Display *dpy, const char *wid_str) {
    if (!dpy || !wid_str || !*wid_str) return 0;
    unsigned long val = strtoul(wid_str, NULL, 16);
    if (val == 0) return 0;

    char res_name[128], res_class[128], title[256];
    read_x11_window_info(dpy, (Window)val, res_name, sizeof(res_name),
                         res_class, sizeof(res_class), title, sizeof(title));

    static const char *const TERM_CLASSES[] = {
        "alacritty", "kitty", "st", "st-256color", "ghostty", "com.mitchellh.ghostty",
        "wezterm", "org.wezfurlong.wezterm", "urxvt", "rxvt", "xterm", "foot",
        "floaterm", "konsole", "gnome-terminal"
    };
    return str_eq_any_ci(res_name, TERM_CLASSES, G_N_ELEMENTS(TERM_CLASSES)) ||
           str_eq_any_ci(res_class, TERM_CLASSES, G_N_ELEMENTS(TERM_CLASSES));
}

static int is_game_window(Display *dpy, const char *wid_str) {
    if (!dpy || !wid_str || !*wid_str) return 0;
    unsigned long val = strtoul(wid_str, NULL, 16);
    if (val == 0) return 0;

    char res_name[128], res_class[128], title[256];
    read_x11_window_info(dpy, (Window)val, res_name, sizeof(res_name),
                         res_class, sizeof(res_class), title, sizeof(title));

    char hay[512];
    snprintf(hay, sizeof(hay), "%s %s %s", res_name, res_class, title);

    static const char *const GAME_IDENTIFIERS[] = {
        "wine", ".exe", "minecraft", "terraria", "mindustry",
        "retroarch", "steam_app_", "mgba", "gba-crossplay",
        "pegasus-frontend", "lutris", "gamescope", "dolphin-emu",
        "ppsspp", "pcsx2"
    };
    for (size_t i = 0; i < G_N_ELEMENTS(GAME_IDENTIFIERS); i++) {
        if (strcasestr(hay, GAME_IDENTIFIERS[i]) != NULL) return 1;
    }
    return 0;
}

static void launch_study_terminal(void) {
    const char *home = getenv("HOME");
    if (!home || !*home) home = "/home/vibecoder";

    char cfg_path[512];
    snprintf(cfg_path, sizeof(cfg_path), "%s/.config/bspwm/config/.term", home);
    char term[64] = "alacritty";
    FILE *tf = fopen(cfg_path, "r");
    if (tf) {
        if (fgets(term, sizeof(term), tf)) {
            g_strstrip(term);
            for (int i = 0; term[i]; i++) term[i] = g_ascii_tolower(term[i]);
        }
        fclose(tf);
    }

    char projects_dir[512];
    snprintf(projects_dir, sizeof(projects_dir), "%s/Projects", home);

    const char *rule_class = "Alacritty";
    if (strcmp(term, "kitty") == 0) rule_class = "kitty";
    else if (strcmp(term, "st") == 0) rule_class = "St";
    else if (strcmp(term, "ghostty") == 0) rule_class = "Ghostty";

    const char *rule_argv[] = { "bspc", "rule", "-a", rule_class, "desktop=^5", "follow=on", "--one-shot", NULL };
    run_argv_sync(rule_argv);

    if (strcmp(term, "kitty") == 0) {
        const char *argv[] = { "kitty", "--directory", projects_dir, "zsh", "-ic", "studyguide; exec zsh", NULL };
        spawn_argv_detached(argv, projects_dir);
    } else if (strcmp(term, "st") == 0) {
        const char *argv[] = { "st", "-e", "zsh", "-ic", "studyguide; exec zsh", NULL };
        spawn_argv_detached(argv, projects_dir);
    } else if (strcmp(term, "ghostty") == 0) {
        char wd_arg[600];
        snprintf(wd_arg, sizeof(wd_arg), "--working-directory=%s", projects_dir);
        const char *argv[] = { "ghostty", wd_arg, "-e", "zsh", "-ic", "studyguide; exec zsh", NULL };
        spawn_argv_detached(argv, projects_dir);
    } else {
        const char *argv[] = { "alacritty", "--working-directory", projects_dir, "-e", "zsh", "-ic", "studyguide; exec zsh", NULL };
        spawn_argv_detached(argv, projects_dir);
    }
}

static void ctl_study_panic(void) {
    Display *dpy = XOpenDisplay(NULL);
    if (dpy) {
        XSetErrorHandler(x11_nonfatal_err);
    }

    char focused_wid[32] = {0};
    exec_cmd_output("bspc query -N -n focused 2>/dev/null", focused_wid, sizeof(focused_wid));

    char desk5_wins[128][32];
    int desk5_count = query_bspc_lines("bspc query -N -d '^5' -n .window.!hidden 2>/dev/null", desk5_wins, 128);

    char desk6_wins[128][32];
    int desk6_count = query_bspc_lines("bspc query -N -d '^6' -n .window.!hidden 2>/dev/null", desk6_wins, 128);

    char all_wins[256][32];
    int all_count = query_bspc_lines("bspc query -N -n .window.!hidden 2>/dev/null", all_wins, 256);

    char desk5_term_wid[32] = {0};
    for (int i = 0; i < desk5_count; i++) {
        if (is_terminal_window(dpy, desk5_wins[i])) {
            g_strlcpy(desk5_term_wid, desk5_wins[i], sizeof(desk5_term_wid));
            break;
        }
    }

    /* Instantly hide all games (desktop 6 + known game classes) + active focused window if not on desktop 5 */
    for (int i = 0; i < all_count; i++) {
        const char *w = all_wins[i];
        if (list_contains(w, desk5_wins, desk5_count)) {
            continue;
        }
        int in_6 = list_contains(w, desk6_wins, desk6_count);
        int is_focused = (focused_wid[0] != '\0' && strcmp(w, focused_wid) == 0);
        if (in_6 || is_focused || is_game_window(dpy, w)) {
            save_node_meta_and_hide(w, in_6 ? "6" : NULL, 0);
        }
    }

    if (desk5_term_wid[0] != '\0') {
        const char *desk_argv[] = { "bspc", "desktop", "-f", "^5", NULL };
        run_argv_sync(desk_argv);
        const char *focus_argv[] = { "bspc", "node", desk5_term_wid, "-f", NULL };
        run_argv_sync(focus_argv);
    } else {
        /* Clear desktop 5 by hiding existing non-terminal windows, then open terminal with studyguide */
        for (int i = 0; i < desk5_count; i++) {
            save_node_meta_and_hide(desk5_wins[i], "5", 0);
        }
        const char *desk_argv[] = { "bspc", "desktop", "-f", "^5", NULL };
        run_argv_sync(desk_argv);
        launch_study_terminal();
    }

    if (dpy) {
        XCloseDisplay(dpy);
    }
}

/* -------------------------------------------------------------
 * 4. Scratchpad Runner
 * ------------------------------------------------------------- */
static void ctl_scratchpad(int argc, char **argv) {
    char cmd[1024] = "/home/vibecoder/.config/bspwm/bin/Scratchpad";
    for (int i = 2; i < argc; i++) {
        strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, argv[i], sizeof(cmd) - strlen(cmd) - 1);
    }
    spawn_async(cmd);
}

/* -------------------------------------------------------------
 * 5. Touchpad Toggle (Pure C status parser)
 * ------------------------------------------------------------- */
static void ctl_touchpad(void) {
    int is_off = 0;
    FILE *f = popen("synclient -l 2>/dev/null", "r");
    if (f) {
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            char *p = strcasestr(line, "TouchpadOff");
            if (p) {
                p += strlen("TouchpadOff");
                while (*p == ' ' || *p == '\t') p++;
                if (*p == '=') p++;
                while (*p == ' ' || *p == '\t') p++;
                if (*p == '1' || *p == '2') {
                    is_off = 1;
                }
                break;
            }
        }
        pclose(f);
    }

    if (is_off) {
        system("synclient TouchpadOff=0 2>/dev/null");
        spawn_async("sys-notif --osd touchpad 100");
    } else {
        system("synclient TouchpadOff=1 2>/dev/null");
        spawn_async("sys-notif --osd touchpad 0");
    }
}

/* -------------------------------------------------------------
 * 6. Screenshot Utility (Guarded against cancellation)
 * ------------------------------------------------------------- */
static void ctl_screenshot(int full) {
    char home_dir[512];
    const char *h = getenv("HOME");
    snprintf(home_dir, sizeof(home_dir), "%s/Pictures/Screenshots", h ? h : "/tmp");
    g_mkdir_with_parents(home_dir, 0755);

    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    char file[600];
    strftime(file, sizeof(file), "%H-%M-%S_%d-%m-%Y.png", tm);

    char fullpath[2048];
    snprintf(fullpath, sizeof(fullpath), "%s/%s", home_dir, file);

    char *cmd = NULL;
    if (full) {
        cmd = g_strdup_printf("maim -u '%s' && notify-send -a 'Screenshot' -i '%s' 'Full Screenshot Saved' '%s'",
                              fullpath, fullpath, fullpath);
    } else {
        cmd = g_strdup_printf("if maim -s -u '%s'; then xclip -selection clipboard -t image/png -i '%s' && notify-send -a 'Screenshot' -i '%s' 'Screenshot Captured' '%s'; else rm -f '%s'; fi",
                              fullpath, fullpath, fullpath, fullpath, fullpath);
    }
    if (cmd) {
        spawn_async(cmd);
        g_free(cmd);
    }
}

/* -------------------------------------------------------------
 * 7. Window Search & Activation (Native Xlib EWMH traversal)
 * ------------------------------------------------------------- */
static int focus_window_by_pattern(const char *pattern) {
    Display *dpy = XOpenDisplay(NULL);
    if (!dpy) return 0;
    Window root = DefaultRootWindow(dpy);

    Atom net_client_list = XInternAtom(dpy, "_NET_CLIENT_LIST", False);
    Atom actual_type;
    int actual_format;
    unsigned long nitems = 0, bytes_after = 0;
    unsigned char *prop = NULL;

    int found = 0;
    if (XGetWindowProperty(dpy, root, net_client_list, 0, 1024, False, XA_WINDOW,
                           &actual_type, &actual_format, &nitems, &bytes_after, &prop) == Success && prop) {
        Window *wins = (Window *)prop;
        for (unsigned long i = 0; i < nitems; i++) {
            Window w = wins[i];

            /* Read WM_CLASS */
            XClassHint ch;
            char title[512] = "";
            char class_str[512] = "";
            if (XGetClassHint(dpy, w, &ch)) {
                snprintf(class_str, sizeof(class_str), "%s %s", ch.res_name ? ch.res_name : "", ch.res_class ? ch.res_class : "");
                if (ch.res_name) XFree(ch.res_name);
                if (ch.res_class) XFree(ch.res_class);
            }

            /* Read _NET_WM_NAME */
            Atom net_wm_name = XInternAtom(dpy, "_NET_WM_NAME", False);
            Atom utf8 = XInternAtom(dpy, "UTF8_STRING", False);
            unsigned char *name_prop = NULL;
            unsigned long name_nitems = 0, name_bytes = 0;
            Atom name_type;
            int name_format;
            if (XGetWindowProperty(dpy, w, net_wm_name, 0, 512, False, utf8,
                                   &name_type, &name_format, &name_nitems, &name_bytes, &name_prop) == Success && name_prop) {
                snprintf(title, sizeof(title), "%s", (char *)name_prop);
                XFree(name_prop);
            } else {
                char *wm_name = NULL;
                if (XFetchName(dpy, w, &wm_name) && wm_name) {
                    snprintf(title, sizeof(title), "%s", wm_name);
                    XFree(wm_name);
                }
            }

            char haystack[1200];
            snprintf(haystack, sizeof(haystack), "%s %s", class_str, title);

            if (strcasestr(haystack, pattern) != NULL) {
                /* Window found! Unhide and focus via bspc */
                char cmd[128];
                snprintf(cmd, sizeof(cmd), "bspc node 0x%lx -g hidden=off 2>/dev/null; bspc node 0x%lx -f 2>/dev/null", (unsigned long)w, (unsigned long)w);
                system(cmd);
                found = 1;
                break;
            }
        }
        XFree(prop);
    }
    XCloseDisplay(dpy);
    return found;
}

static void ctl_activate(const char *target_app, const char *target_sum) {
    (void)target_sum;
    if (!target_app || strlen(target_app) == 0) return;

    char lower[128];
    g_strlcpy(lower, target_app, sizeof(lower));
    for (int i = 0; lower[i]; i++) {
        lower[i] = g_ascii_tolower(lower[i]);
    }

    if (strstr(lower, "instagram")) {
        if (!focus_window_by_pattern("Instagram") && !focus_window_by_pattern("firefox")) {
            spawn_async("firefox 'https://www.instagram.com/direct/inbox/'");
        }
    } else if (strstr(lower, "whatsapp")) {
        if (!focus_window_by_pattern("WhatsApp") && !focus_window_by_pattern("firefox")) {
            spawn_async("firefox 'https://web.whatsapp.com/'");
        }
    } else if (strstr(lower, "discord") || strstr(lower, "vesktop")) {
        if (!focus_window_by_pattern("discord") && !focus_window_by_pattern("vesktop")) {
            spawn_async("discord");
        }
    } else if (strstr(lower, "telegram")) {
        if (!focus_window_by_pattern("telegram")) {
            spawn_async("telegram-desktop");
        }
    } else if (strstr(lower, "spotify")) {
        if (!focus_window_by_pattern("spotify")) {
            spawn_async("spotify");
        }
    } else if (strstr(lower, "youtube")) {
        if (!focus_window_by_pattern("youtube") && !focus_window_by_pattern("firefox")) {
            spawn_async("firefox 'https://www.youtube.com/'");
        }
    } else if (strstr(lower, "terminal") || strstr(lower, "alacritty") || strstr(lower, "kitty")) {
        if (!focus_window_by_pattern("Alacritty") && !focus_window_by_pattern("kitty")) {
            spawn_async("/home/vibecoder/.config/bspwm/bin/Term --terminal");
        }
    } else {
        if (!focus_window_by_pattern(target_app)) {
            focus_window_by_pattern("firefox");
        }
    }
}

/* -------------------------------------------------------------
 * Main Entry Point
 * ------------------------------------------------------------- */
int main(int argc, char **argv) {
    if (argc < 2) {
        printf("sys-control: Native High-Performance System Controller for BSPWM\n");
        printf("Usage: sys-control [--vol-inc|--vol-dec|--vol-toggle|--bri-up|--bri-down|--scratchpad|--bar|--node|--activate|...]\n");
        return 0;
    }

    const char *arg = argv[1];

    /* Volume */
    if (strcmp(arg, "--vol-inc") == 0 || strcmp(arg, "vol-inc") == 0 || strcmp(arg, "volume-up") == 0) {
        ctl_volume("inc", argc >= 3 ? argv[2] : NULL);
    } else if (strcmp(arg, "--vol-dec") == 0 || strcmp(arg, "vol-dec") == 0 || strcmp(arg, "volume-down") == 0) {
        ctl_volume("dec", argc >= 3 ? argv[2] : NULL);
    } else if (strcmp(arg, "--vol-toggle") == 0 || strcmp(arg, "vol-toggle") == 0 || strcmp(arg, "volume-mute") == 0 || strcmp(arg, "volume-mute-toggle") == 0) {
        ctl_volume("toggle", NULL);
    } else if (strcmp(arg, "--get-vol") == 0 || strcmp(arg, "get-vol") == 0 || strcmp(arg, "--vol-get") == 0) {
        ctl_volume("get", NULL);
    } else if (strcmp(arg, "--vol-status") == 0) {
        ctl_volume("status", NULL);
    } else if (strcmp(arg, "volume") == 0 || strcmp(arg, "--volume") == 0) {
        const char *subaction = argc >= 3 ? argv[2] : "status";
        const char *step_val = argc >= 4 ? argv[3] : NULL;
        if (strcmp(subaction, "up") == 0) ctl_volume("inc", step_val);
        else if (strcmp(subaction, "down") == 0) ctl_volume("dec", step_val);
        else if (strcmp(subaction, "mute-toggle") == 0 || strcmp(subaction, "mute") == 0 || strcmp(subaction, "toggle") == 0) ctl_volume("toggle", NULL);
        else if (strcmp(subaction, "get") == 0) ctl_volume("get", NULL);
        else ctl_volume("status", NULL);
    }
    /* Media */
    else if (strcmp(arg, "--toggle") == 0 || strcmp(arg, "toggle") == 0) {
        ctl_media("toggle");
    } else if (strcmp(arg, "--next") == 0 || strcmp(arg, "next") == 0) {
        ctl_media("next");
    } else if (strcmp(arg, "--previous") == 0 || strcmp(arg, "previous") == 0 || strcmp(arg, "prev") == 0) {
        ctl_media("previous");
    } else if (strcmp(arg, "--play") == 0 || strcmp(arg, "play") == 0) {
        ctl_media("play");
    } else if (strcmp(arg, "--pause") == 0 || strcmp(arg, "pause") == 0) {
        ctl_media("pause");
    } else if (strcmp(arg, "--stop") == 0 || strcmp(arg, "stop") == 0) {
        ctl_media("stop");
    } else if (strcmp(arg, "--status") == 0) {
        ctl_media("status");
    } else if (strcmp(arg, "--title") == 0) {
        ctl_media("title");
    } else if (strcmp(arg, "--artist") == 0) {
        ctl_media("artist");
    } else if (strcmp(arg, "media") == 0 || strcmp(arg, "--media") == 0) {
        const char *subaction = argc >= 3 ? argv[2] : "toggle";
        ctl_media(subaction);
    }
    /* Brightness */
    else if (strcmp(arg, "--bri-up") == 0 || strcmp(arg, "bri-up") == 0 || strcmp(arg, "brightness-up") == 0 || strcmp(arg, "--bri-inc") == 0) {
        ctl_brightness("up", argc >= 3 ? argv[2] : NULL);
    } else if (strcmp(arg, "--bri-down") == 0 || strcmp(arg, "bri-down") == 0 || strcmp(arg, "brightness-down") == 0 || strcmp(arg, "--bri-dec") == 0) {
        ctl_brightness("down", argc >= 3 ? argv[2] : NULL);
    } else if (strcmp(arg, "--get-bri") == 0 || strcmp(arg, "get-bri") == 0 || strcmp(arg, "--bri-get") == 0) {
        ctl_brightness("get", NULL);
    } else if (strcmp(arg, "brightness") == 0 || strcmp(arg, "--brightness") == 0) {
        const char *subaction = argc >= 3 ? argv[2] : "get";
        const char *step_val = argc >= 4 ? argv[3] : NULL;
        ctl_brightness(subaction, step_val);
    }
    /* Hider */
    else if (strcmp(arg, "--hider-bar") == 0 || strcmp(arg, "bar") == 0 || strcmp(arg, "--bar") == 0 || strcmp(arg, "--bar-toggle") == 0) {
        ctl_hider("--bar");
    } else if (strcmp(arg, "--bar-hide") == 0) {
        ctl_hider("--bar-hide");
    } else if (strcmp(arg, "--bar-show") == 0) {
        ctl_hider("--bar-show");
    } else if (strcmp(arg, "--hider-node") == 0 || strcmp(arg, "node") == 0 || strcmp(arg, "--node") == 0 || strcmp(arg, "--hide-node") == 0 || strcmp(arg, "--window") == 0) {
        ctl_hider_node(argc >= 3 ? argv[2] : NULL);
    } else if (strcmp(arg, "--study-panic") == 0) {
        ctl_study_panic();
    } else if (strcmp(arg, "--restore") == 0 || strcmp(arg, "--restore-node") == 0) {
        ctl_hider("--restore");
    } else if (strcmp(arg, "--hider-menu") == 0 || strcmp(arg, "--windows-menu") == 0 || strcmp(arg, "--hidden-menu") == 0 || strcmp(arg, "--menu-hider") == 0) {
        ctl_hider("--menu");
    }
    /* Scratchpad */
    else if (strcmp(arg, "--scratchpad") == 0 || strcmp(arg, "scratchpad") == 0) {
        ctl_scratchpad(argc, argv);
    } else if (strcmp(arg, "--scratch") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Bspwm-ScratchPad");
    } else if (strcmp(arg, "--bluetooth") == 0) {
        if (argc >= 3 && strcmp(argv[2], "toggle") == 0) {
            spawn_async("sys-bt toggle");
        } else if (argc >= 3 && (strcmp(argv[2], "gui") == 0 || strcmp(argv[2], "blueman") == 0)) {
            spawn_async("/home/vibecoder/.config/bspwm/bin/Scratchpad center blueman-manager");
        } else {
            spawn_async("sys-bt menu");
        }
    } else if (strcmp(arg, "--blueman") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Scratchpad center blueman-manager");
    }
    /* Touchpad & Screenshots */
    else if (strcmp(arg, "--touchpad") == 0 || strcmp(arg, "touchpad") == 0) {
        ctl_touchpad();
    } else if (strcmp(arg, "--screenshot") == 0 || strcmp(arg, "screenshot") == 0) {
        if (argc >= 3 && (strcmp(argv[2], "full") == 0 || strcmp(argv[2], "--full") == 0)) {
            ctl_screenshot(1);
        } else {
            ctl_screenshot(0);
        }
    } else if (strcmp(arg, "--screenshots") == 0 || strcmp(arg, "screenshots") == 0) {
        ctl_screenshot(1);
    }
    /* Clipboard */
    else if (strcmp(arg, "--clipboard") == 0) {
        spawn_async("CM_LAUNCHER=rofi clipmenu -theme ~/.config/rofi/launchers/type-1/style-7.rasi &");
    }
    /* Window Activation */
    else if (strcmp(arg, "--activate") == 0) {
        ctl_activate(argc >= 3 ? argv[2] : "", argc >= 4 ? argv[3] : "");
    }
    /* Notification DND */
    else if (strcmp(arg, "--dnd") == 0 || strcmp(arg, "--dnd-toggle") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-notif --dnd-toggle");
    }
    /* Terminal Apps */
    else if (strcmp(arg, "--terminal") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Term --terminal");
    } else if (strcmp(arg, "--floating") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Term --floating");
    } else if (strcmp(arg, "--nvim") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Term --nvim");
    } else if (strcmp(arg, "--yazi") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/Term --yazi");
    }
    /* Standard Apps */
    else if (strcmp(arg, "--browser") == 0) {
        spawn_async("${BROWSER:-firefox} &");
    } else if (strcmp(arg, "--editor") == 0) {
        spawn_async("${EDITOR:-geany} &");
    } else if (strcmp(arg, "--filemanager") == 0) {
        spawn_async("${FILEMANAGER:-pcmanfm} &");
    } else if (strcmp(arg, "--soundcontrol") == 0) {
        spawn_async("pavucontrol");
    } else if (strcmp(arg, "--riceeditor") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/RiceEditor");
    } else if (strcmp(arg, "--whats") == 0) {
        spawn_async("firefox -new-tab 'https://web.whatsapp.com/'");
    } else if (strcmp(arg, "--pass") == 0) {
        spawn_async("RofiPass");
    } else if (strcmp(arg, "--netmanager") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/NetManagerDM");
    }
    /* Rofi Menus & OpenApps */
    else if (strcmp(arg, "--menu") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-launcher");
    } else if (strcmp(arg, "--RofiLauncher") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --RofiLauncher");
    } else if (strcmp(arg, "--powermenu") == 0 || strcmp(arg, "powermenu") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --powermenu");
    } else if (strcmp(arg, "--riceselector") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --riceselector");
    } else if (strcmp(arg, "--keybinds") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --keybinds");
    } else if (strcmp(arg, "--apptoggle") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-launcher --toggle");
    } else if (strcmp(arg, "--screenlocker") == 0 || strcmp(arg, "--lock") == 0 || strcmp(arg, "lock") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-lock --blur");
    } else if (strcmp(arg, "--lock-rice") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-lock --rice");
    } else if (strcmp(arg, "--lock-dark") == 0) {
        spawn_async("/home/vibecoder/.local/bin/sys-lock --dark");
    } else {
        /* General fallback to OpenApps for any unknown custom flags */
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "/home/vibecoder/.config/bspwm/bin/OpenApps %s", arg);
        spawn_async(cmd);
    }

    return 0;
}
