#define _POSIX_C_SOURCE 200809L
#include "sys-input-x11.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

#define F13_KEYCODE 191
#define F22_KEYCODE 200
#define F23_KEYCODE 201
#define F24_KEYCODE 202

struct SysInputX11 {
    Display *dpy;
    int xkb_opcode;
    int xkb_event;
    bool has_xkb;
    double last_sync_sec;
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

static bool ensure_x11_env(void) {
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
    return true;
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

SysInputX11 *sys_input_x11_create(void) {
    SysInputX11 *x11 = calloc(1, sizeof(*x11));
    if (!x11) {
        return NULL;
    }
    XSetIOErrorHandler(x11_io_err);
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

    int err = 0;
    int maj = XkbMajorVersion;
    int min = XkbMinorVersion;
    x11->has_xkb = XkbQueryExtension(x11->dpy, &x11->xkb_opcode, &x11->xkb_event, &err, &maj, &min) != 0;
    if (x11->has_xkb) {
        XkbSelectEvents(x11->dpy, XkbUseCoreKbd, XkbNewKeyboardNotifyMask | XkbMapNotifyMask, XkbNewKeyboardNotifyMask | XkbMapNotifyMask);
    }

    apply_keymap(x11->dpy);
    x11->last_sync_sec = mono_sec();
    return true;
}

void sys_input_x11_process(SysInputX11 *x11) {
    if (!x11 || !x11->dpy) {
        return;
    }

    bool trigger = false;
    while (XPending(x11->dpy)) {
        XEvent ev;
        XNextEvent(x11->dpy, &ev);
        if (ev.type == MappingNotify) {
            XRefreshKeyboardMapping(&ev.xmapping);
            trigger = true;
        } else if (x11->has_xkb && ev.type == x11->xkb_event) {
            XkbEvent *kev = (XkbEvent *)&ev;
            if (kev->any.xkb_type == XkbNewKeyboardNotify || kev->any.xkb_type == XkbMapNotify) {
                if (kev->any.xkb_type == XkbMapNotify) {
                    XkbRefreshKeyboardMapping(&kev->map);
                }
                trigger = true;
            }
        }
    }

    if (trigger) {
        double now = mono_sec();
        if (now - x11->last_sync_sec > 0.2) {
            x11->last_sync_sec = now;
            apply_keymap(x11->dpy);
        }
    }
}
