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
 * 3. Hider Control (Windows & Bar)
 * ------------------------------------------------------------- */
static void ctl_hider(const char *target) {
    char cmd[256];
    snprintf(cmd, sizeof(cmd), "/home/vibecoder/.config/bspwm/bin/Hider %s", target ? target : "");
    spawn_async(cmd);
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
        ctl_hider("--node");
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
        spawn_async("${FILEMANAGER:-thunar} &");
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
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --screenlocker");
    } else if (strcmp(arg, "--lock-rice") == 0) {
        spawn_async("/home/vibecoder/.config/bspwm/bin/OpenApps --lock-rice");
    } else {
        /* General fallback to OpenApps for any unknown custom flags */
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "/home/vibecoder/.config/bspwm/bin/OpenApps %s", arg);
        spawn_async(cmd);
    }

    return 0;
}
