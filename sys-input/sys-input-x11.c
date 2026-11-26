#define _GNU_SOURCE
#include "sys-input-x11.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

#define F13_KEYCODE 191
#define F22_KEYCODE 200
#define F23_KEYCODE 201
#define F24_KEYCODE 202
#define GAMING_DESKTOP_IDX 5 /* Workspace 6 (^6) zero-indexed */

struct SysInputX11 {
    Display *dpy;
    Window root;
    Atom atom_active_win;
    Atom atom_cur_desk;
    Atom atom_net_wm_name;
    Atom atom_utf8;
    int xkb_opcode;
    int xkb_event;
    bool has_xkb;
    bool last_in_game;
    bool last_in_nfs;
    bool has_game_state;
    double last_sync_sec;
    SysInputGameCtxCb game_cb;
    void *game_ctx;
};

static double mono_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static int x11_io_err(Display *dpy) {
    (void)dpy;
    return 0;
}

static int x11_nonfatal_err(Display *dpy, XErrorEvent *ev) {
    (void)dpy;
    (void)ev;
    return 0;
}

static void ensure_x11_env(void) {
    const char *disp = getenv("DISPLAY");
    if (!disp || !*disp) {
        setenv("DISPLAY", ":0", 1);
    }
    const char *auth = getenv("XAUTHORITY");
    if (!auth || !*auth || access(auth, R_OK) != 0) {
        const char *home = getenv("HOME");
        if (home && *home) {
            char buf[512];
            snprintf(buf, sizeof(buf), "%s/.Xauthority", home);
            if (access(buf, R_OK) == 0) {
                setenv("XAUTHORITY", buf, 1);
            }
        }
    }
}

static bool contains_any_ci(const char *haystack, const char *const *needles, size_t n) {
    if (!haystack || !*haystack) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        if (strcasestr(haystack, needles[i]) != NULL) {
            return true;
        }
    }
    return false;
}

static void query_game_context(SysInputX11 *x11, bool *out_in_game, bool *out_in_nfs) {
    *out_in_game = false;
    *out_in_nfs = false;
    if (!x11 || !x11->dpy) {
        return;
    }

    Atom actual_type = None;
    int actual_fmt = 0;
    unsigned long nitems = 0, bytes_after = 0;
    unsigned char *prop = NULL;

    Window active_win = None;
    if (XGetWindowProperty(x11->dpy, x11->root, x11->atom_active_win, 0, 1, False, XA_WINDOW,
                           &actual_type, &actual_fmt, &nitems, &bytes_after, &prop) == Success && prop) {
        if (nitems >= 1 && actual_fmt == 32) {
            active_win = *(Window *)prop;
        }
        XFree(prop);
        prop = NULL;
    }

    if (active_win == None) {
        return;
    }

    unsigned long desk_idx = 0;
    if (XGetWindowProperty(x11->dpy, x11->root, x11->atom_cur_desk, 0, 1, False, XA_CARDINAL,
                           &actual_type, &actual_fmt, &nitems, &bytes_after, &prop) == Success && prop) {
        if (nitems >= 1 && actual_fmt == 32) {
            desk_idx = *(unsigned long *)prop;
        }
        XFree(prop);
        prop = NULL;
    }

    char hay[512] = {0};
    XClassHint ch = {0};
    if (XGetClassHint(x11->dpy, active_win, &ch)) {
        snprintf(hay, sizeof(hay), "%s %s",
                 ch.res_name ? ch.res_name : "",
                 ch.res_class ? ch.res_class : "");
        if (ch.res_name) XFree(ch.res_name);
        if (ch.res_class) XFree(ch.res_class);
    }

    if (XGetWindowProperty(x11->dpy, active_win, x11->atom_net_wm_name, 0, 128, False, x11->atom_utf8,
                           &actual_type, &actual_fmt, &nitems, &bytes_after, &prop) == Success && prop) {
        size_t len = strlen(hay);
        if (len + 2 < sizeof(hay)) {
            snprintf(hay + len, sizeof(hay) - len, " %s", (const char *)prop);
        }
        XFree(prop);
    }

    static const char *const NON_GAME_OVERLAYS[] = {
        "sys-lock", "sys-launcher", "sys-notif-center", "sys-alarm", "sys-polkit", "rofi"
    };
    if (contains_any_ci(hay, NON_GAME_OVERLAYS, sizeof(NON_GAME_OVERLAYS) / sizeof(NON_GAME_OVERLAYS[0]))) {
        return;
    }

    static const char *const NFS_IDENTIFIERS[] = {
        "speed.exe", "need for speed"
    };
    if (contains_any_ci(hay, NFS_IDENTIFIERS, sizeof(NFS_IDENTIFIERS) / sizeof(NFS_IDENTIFIERS[0]))) {
        *out_in_game = true;
        *out_in_nfs = true;
        return;
    }

    if (desk_idx == GAMING_DESKTOP_IDX) {
        *out_in_game = true;
        return;
    }

    static const char *const GAME_IDENTIFIERS[] = {
        "wine", ".exe", "minecraft", "terraria", "mindustry",
        "retroarch", "steam_app_", "mgba", "gba-crossplay",
        "pegasus-frontend", "lutris", "gamescope", "dolphin-emu",
        "ppsspp", "pcsx2"
    };
    *out_in_game = contains_any_ci(hay, GAME_IDENTIFIERS, sizeof(GAME_IDENTIFIERS) / sizeof(GAME_IDENTIFIERS[0]));
}

static void check_game_context(SysInputX11 *x11) {
    if (!x11 || !x11->dpy || !x11->game_cb) {
        return;
    }
    bool in_game = false;
    bool in_nfs = false;
    query_game_context(x11, &in_game, &in_nfs);
    if (!x11->has_game_state || in_game != x11->last_in_game || in_nfs != x11->last_in_nfs) {
        x11->has_game_state = true;
        x11->last_in_game = in_game;
        x11->last_in_nfs = in_nfs;
        x11->game_cb(x11->game_ctx, in_game, in_nfs);
    }
}

static bool keymap_needs_sync(Display *dpy) {
    for (int i = 0; i <= (F22_KEYCODE - F13_KEYCODE); i++) {
        KeySym ks = XkbKeycodeToKeysym(dpy, (KeyCode)(F13_KEYCODE + i), 0, 0);
        if (ks != (KeySym)(XK_F13 + i)) {
            return true;
        }
    }

    if (XkbKeycodeToKeysym(dpy, (KeyCode)F23_KEYCODE, 0, 0) != XK_Hyper_L) {
        return true;
    }

    XModifierKeymap *map = XGetModifierMapping(dpy);
    if (!map) {
        return true;
    }

    bool has_hyper_mod3 = false;
    bool has_stale_f24_mod5 = false;

    for (int i = 0; i < map->max_keypermod; i++) {
        KeyCode kc3 = map->modifiermap[Mod3MapIndex * map->max_keypermod + i];
        if (kc3 == (KeyCode)F23_KEYCODE) {
            has_hyper_mod3 = true;
        }
        KeyCode kc5 = map->modifiermap[Mod5MapIndex * map->max_keypermod + i];
        if (kc5 == (KeyCode)F24_KEYCODE) {
            has_stale_f24_mod5 = true;
        }
    }

    XFreeModifiermap(map);
    return !has_hyper_mod3 || has_stale_f24_mod5;
}

static void apply_keymap(Display *dpy) {
    if (!keymap_needs_sync(dpy)) {
        return;
    }

    KeySym f_syms[10 * 4];
    for (int i = 0; i < 10; i++) {
        KeySym ks = (KeySym)(XK_F13 + i);
        f_syms[i * 4 + 0] = ks;
        f_syms[i * 4 + 1] = ks;
        f_syms[i * 4 + 2] = ks;
        f_syms[i * 4 + 3] = ks;
    }
    XChangeKeyboardMapping(dpy, F13_KEYCODE, 4, f_syms, 10);

    KeySym hyper_syms[4] = { XK_Hyper_L, NoSymbol, XK_Hyper_L, NoSymbol };
    XChangeKeyboardMapping(dpy, F23_KEYCODE, 4, hyper_syms, 1);

    KeySym f24_syms[4] = { XK_F24, XK_F24, XK_F24, XK_F24 };
    XChangeKeyboardMapping(dpy, F24_KEYCODE, 4, f24_syms, 1);

    XModifierKeymap *map = XGetModifierMapping(dpy);
    if (map) {
        for (int i = map->max_keypermod - 1; i >= 0; i--) {
            KeyCode kc3 = map->modifiermap[Mod3MapIndex * map->max_keypermod + i];
            if (kc3 != 0 && kc3 != (KeyCode)F23_KEYCODE) {
                map = XDeleteModifiermapEntry(map, kc3, Mod3MapIndex);
            }
            KeyCode kc5 = map->modifiermap[Mod5MapIndex * map->max_keypermod + i];
            if (kc5 == (KeyCode)F24_KEYCODE) {
                map = XDeleteModifiermapEntry(map, kc5, Mod5MapIndex);
            }
        }
        map = XInsertModifiermapEntry(map, (KeyCode)F23_KEYCODE, Mod3MapIndex);
        XSetModifierMapping(dpy, map);
        XFreeModifiermap(map);
    }

    XSync(dpy, False);
}

SysInputX11 *sys_input_x11_create(SysInputGameCtxCb cb, void *ctx) {
    SysInputX11 *x11 = calloc(1, sizeof(*x11));
    if (!x11) {
        return NULL;
    }
    x11->game_cb = cb;
    x11->game_ctx = ctx;
    XSetIOErrorHandler(x11_io_err);
    XSetErrorHandler(x11_nonfatal_err);
    return x11;
}

void sys_input_x11_destroy(SysInputX11 *x11) {
    if (!x11) {
        return;
    }
    if (x11->dpy) {
        XCloseDisplay(x11->dpy);
        x11->dpy = NULL;
    }
    free(x11);
}

int sys_input_x11_fd(const SysInputX11 *x11) {
    if (!x11 || !x11->dpy) {
        return -1;
    }
    return ConnectionNumber(x11->dpy);
}

bool sys_input_x11_connect(SysInputX11 *x11) {
    if (!x11) {
        return false;
    }
    if (x11->dpy) {
        return true;
    }

    ensure_x11_env();
    x11->dpy = XOpenDisplay(NULL);
    if (!x11->dpy) {
        return false;
    }

    x11->root = DefaultRootWindow(x11->dpy);
    x11->atom_active_win = XInternAtom(x11->dpy, "_NET_ACTIVE_WINDOW", False);
    x11->atom_cur_desk = XInternAtom(x11->dpy, "_NET_CURRENT_DESKTOP", False);
    x11->atom_net_wm_name = XInternAtom(x11->dpy, "_NET_WM_NAME", False);
    x11->atom_utf8 = XInternAtom(x11->dpy, "UTF8_STRING", False);

    XSelectInput(x11->dpy, x11->root, PropertyChangeMask);

    int err = 0;
    int maj = XkbMajorVersion;
    int min = XkbMinorVersion;
    x11->has_xkb = XkbQueryExtension(x11->dpy, &x11->xkb_opcode, &x11->xkb_event, &err, &maj, &min) != 0;
    if (x11->has_xkb) {
        XkbSelectEvents(x11->dpy, XkbUseCoreKbd, XkbNewKeyboardNotifyMask | XkbMapNotifyMask, XkbNewKeyboardNotifyMask | XkbMapNotifyMask);
    }

    apply_keymap(x11->dpy);
    x11->last_sync_sec = mono_sec();
    check_game_context(x11);
    return true;
}

void sys_input_x11_process(SysInputX11 *x11) {
    if (!x11 || !x11->dpy) {
        return;
    }

    bool map_trigger = false;
    bool ctx_trigger = false;

    while (XPending(x11->dpy)) {
        XEvent ev;
        XNextEvent(x11->dpy, &ev);
        if (ev.type == PropertyNotify && ev.xproperty.window == x11->root) {
            if (ev.xproperty.atom == x11->atom_active_win || ev.xproperty.atom == x11->atom_cur_desk) {
                ctx_trigger = true;
            }
        } else if (ev.type == MappingNotify) {
            XRefreshKeyboardMapping(&ev.xmapping);
            map_trigger = true;
        } else if (x11->has_xkb && ev.type == x11->xkb_event) {
            XkbEvent *kev = (XkbEvent *)&ev;
            if (kev->any.xkb_type == XkbNewKeyboardNotify || kev->any.xkb_type == XkbMapNotify) {
                if (kev->any.xkb_type == XkbMapNotify) {
                    XkbRefreshKeyboardMapping(&kev->map);
                }
                map_trigger = true;
            }
        }
    }

    if (ctx_trigger) {
        check_game_context(x11);
    }

    if (map_trigger) {
        double now = mono_sec();
        if (now - x11->last_sync_sec > 0.2) {
            x11->last_sync_sec = now;
            apply_keymap(x11->dpy);
        }
    }
}
