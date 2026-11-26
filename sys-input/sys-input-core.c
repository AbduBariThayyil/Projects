#define _GNU_SOURCE
#include "sys-input.h"

#include <stddef.h>
#include <linux/input-event-codes.h>

#define SWALLOW_BTN_LEFT   (1u << 0)
#define SWALLOW_BTN_RIGHT  (1u << 1)
#define SWALLOW_BTN_MIDDLE (1u << 2)

#define CMD_SYS_CTL          "/home/vibecoder/.local/bin/sys-control"
#define CMD_BACKLIGHT_TOGGLE "/home/vibecoder/.config/bspwm/bin/BacklightToggle"
#define CMD_TOUCHPAD_TOGGLE  "/home/vibecoder/.config/bspwm/bin/ToggleTouchpad"
#define CMD_MUSIC_APP        "/home/vibecoder/.config/bspwm/bin/LyricViewLauncher"

typedef struct {
    uint16_t code;
    const char *cmd;
    bool allow_repeat;
} KeyCmdRule;

static const KeyCmdRule GLOBAL_MEDIA_RULES[] = {
    { KEY_VOLUMEUP,       CMD_SYS_CTL " --vol-inc",    true  },
    { KEY_VOLUMEDOWN,     CMD_SYS_CTL " --vol-dec",    true  },
    { KEY_MUTE,           CMD_SYS_CTL " --vol-toggle", false },
    { KEY_PLAYPAUSE,      CMD_SYS_CTL " --toggle",     false },
    { KEY_PAUSE,          CMD_SYS_CTL " --toggle",     false },
    { KEY_PLAY,           CMD_SYS_CTL " --toggle",     false },
    { KEY_PREVIOUSSONG,   CMD_SYS_CTL " --previous",   false },
    { KEY_NEXTSONG,       CMD_SYS_CTL " --next",       false },
    { KEY_STOPCD,         CMD_SYS_CTL " --stop",       false },
    { KEY_STOP,           CMD_SYS_CTL " --stop",       false },
    { KEY_BRIGHTNESSUP,   CMD_SYS_CTL " --bri-up",     true  },
    { KEY_BRIGHTNESSDOWN, CMD_SYS_CTL " --bri-down",   true  },
};

static const KeyCmdRule CASUE_FN_LOCK_RULES[] = {
    { KEY_F1, CMD_MUSIC_APP,               false },
    { KEY_F2, CMD_SYS_CTL " --vol-dec",    true  },
    { KEY_F3, CMD_SYS_CTL " --vol-inc",    true  },
    { KEY_F4, CMD_SYS_CTL " --vol-toggle", false },
    { KEY_F5, CMD_SYS_CTL " --stop",       false },
    { KEY_F6, CMD_SYS_CTL " --previous",   false },
    { KEY_F7, CMD_SYS_CTL " --toggle",     false },
    { KEY_F8, CMD_SYS_CTL " --next",       false },
};

static void emit_kbd_ev(SysInputState *st, uint16_t type, uint16_t code, int32_t value) {
    if (st->ops.emit_kbd) {
        st->ops.emit_kbd(st->ctx, type, code, value);
        st->kbd_dirty = true;
    }
}

static void emit_ptr_ev(SysInputState *st, uint16_t type, uint16_t code, int32_t value) {
    if (st->ops.emit_ptr) {
        st->ops.emit_ptr(st->ctx, type, code, value);
        st->ptr_dirty = true;
    }
}

static void flush_syn(SysInputState *st) {
    if (st->kbd_dirty && st->ops.emit_kbd_syn) {
        st->ops.emit_kbd_syn(st->ctx);
        st->kbd_dirty = false;
    }
    if (st->ptr_dirty && st->ops.emit_ptr_syn) {
        st->ops.emit_ptr_syn(st->ctx);
        st->ptr_dirty = false;
    }
}

static void trigger_cmd(SysInputState *st, const char *cmd) {
    if (st->ops.run_cmd && cmd) {
        st->ops.run_cmd(st->ctx, cmd);
    }
}

static const KeyCmdRule *find_rule(const KeyCmdRule *rules, size_t count, uint16_t code) {
    for (size_t i = 0; i < count; i++) {
        if (rules[i].code == code) {
            return &rules[i];
        }
    }
    return NULL;
}

static uint32_t mouse_swallow_bit(uint16_t code) {
    switch (code) {
        case BTN_LEFT:   return SWALLOW_BTN_LEFT;
        case BTN_RIGHT:  return SWALLOW_BTN_RIGHT;
        case BTN_MIDDLE: return SWALLOW_BTN_MIDDLE;
        default:         return 0;
    }
}

static const char *backward_btn_cmd(uint16_t code) {
    switch (code) {
        case BTN_LEFT:   return CMD_SYS_CTL " --previous";
        case BTN_MIDDLE: return CMD_SYS_CTL " --vol-toggle";
        case BTN_RIGHT:  return CMD_SYS_CTL " --next";
        default:         return NULL;
    }
}

static void release_desktop_modifiers(SysInputState *st) {
    if (st->backward_held) {
        st->backward_held = false;
        emit_kbd_ev(st, EV_KEY, KEY_F23, 0);
        flush_syn(st);
    }
    st->forward_held = false;
    st->forward_used_chord = false;
}

static bool handle_gm320_special_key(SysInputState *st, uint16_t code, int32_t value) {
    if (code == KEY_CALC) {
        if (value == 1) {
            st->gaming_mode = !st->gaming_mode;
            release_desktop_modifiers(st);
            if (st->ops.notify) {
                if (st->gaming_mode) {
                    st->ops.notify(st->ctx, "Gaming Mode", "Mouse buttons: Mouse4 / Mouse5 / F15", "input-gaming");
                } else {
                    st->ops.notify(st->ctx, "Desktop Mode", "Mouse modifiers & chords active", "input-mouse");
                }
            }
        }
        return true;
    }
    if (code == KEY_MAIL) {
        emit_kbd_ev(st, EV_KEY, KEY_F15, value);
        return true;
    }
    if (code == KEY_HOMEPAGE) {
        emit_kbd_ev(st, EV_KEY, KEY_F14, value);
        return true;
    }
    return false;
}

static bool handle_mouse_rel(SysInputState *st, uint16_t code, int32_t value) {
    if (code != REL_WHEEL && code != REL_WHEEL_HI_RES) {
        emit_ptr_ev(st, EV_REL, code, value);
        return true;
    }

    if (st->backward_held) {
        if (code == REL_WHEEL) {
            trigger_cmd(st, value > 0 ? CMD_SYS_CTL " --vol-inc" : CMD_SYS_CTL " --vol-dec");
        }
        return true;
    }

    if (st->forward_held) {
        st->forward_used_chord = true;
        if (code == REL_WHEEL) {
            trigger_cmd(st, value > 0 ? CMD_SYS_CTL " --bri-up" : CMD_SYS_CTL " --bri-down");
        }
        return true;
    }

    emit_ptr_ev(st, EV_REL, code, value);
    return true;
}

static bool handle_mouse_button(SysInputState *st, uint16_t code, int32_t value) {
    if (code == BTN_SIDE) {
        if (value == 1) {
            if (st->gaming_mode) {
                st->side_passed_through = true;
                emit_ptr_ev(st, EV_KEY, BTN_SIDE, 1);
            } else {
                st->backward_held = true;
                emit_kbd_ev(st, EV_KEY, KEY_F23, 1);
            }
        } else if (value == 0) {
            if (st->side_passed_through) {
                st->side_passed_through = false;
                emit_ptr_ev(st, EV_KEY, BTN_SIDE, 0);
            }
            if (st->backward_held) {
                st->backward_held = false;
                emit_kbd_ev(st, EV_KEY, KEY_F23, 0);
            }
        }
        return true;
    }

    if (code == BTN_EXTRA) {
        if (value == 1) {
            if (st->gaming_mode) {
                st->extra_passed_through = true;
                emit_ptr_ev(st, EV_KEY, BTN_EXTRA, 1);
            } else {
                st->forward_held = true;
                st->forward_used_chord = false;
            }
        } else if (value == 0) {
            if (st->extra_passed_through) {
                st->extra_passed_through = false;
                emit_ptr_ev(st, EV_KEY, BTN_EXTRA, 0);
            } else if (st->forward_held) {
                bool was_chord = st->forward_used_chord;
                st->forward_held = false;
                st->forward_used_chord = false;
                if (!was_chord) {
                    emit_ptr_ev(st, EV_KEY, BTN_EXTRA, 1);
                    flush_syn(st);
                    if (st->ops.schedule_ptr_tap_release) {
                        st->ops.schedule_ptr_tap_release(st->ctx, BTN_EXTRA, 15);
                    } else {
                        emit_ptr_ev(st, EV_KEY, BTN_EXTRA, 0);
                    }
                }
            }
        }
        return true;
    }

    uint32_t bit = mouse_swallow_bit(code);
    if (bit != 0) {
        if (value == 1 && st->backward_held) {
            st->swallowed_mouse_btns |= bit;
            trigger_cmd(st, backward_btn_cmd(code));
            return true;
        }
        if (value == 0 && (st->swallowed_mouse_btns & bit)) {
            st->swallowed_mouse_btns &= ~bit;
            return true;
        }
        if (value == 2 && (st->swallowed_mouse_btns & bit)) {
            return true;
        }
    }

    return false;
}

static bool handle_keyboard_key(SysInputState *st, DeviceKind kind, uint16_t code, int32_t value) {
    /* Track physical modifier state across keyboards */
    if (code == KEY_LEFTSHIFT) {
        st->shift_l = (value != 0);
        return false;
    }
    if (code == KEY_RIGHTSHIFT) {
        st->shift_r = (value != 0);
        return false;
    }
    if (code == KEY_LEFTCTRL || code == KEY_RIGHTCTRL) {
        st->ctrl_held = (value != 0);
        return false;
    }
    if (code == KEY_LEFTALT || code == KEY_RIGHTALT) {
        st->alt_held = (value != 0);
        return false;
    }
    if (code == KEY_LEFTMETA || code == KEY_RIGHTMETA) {
        st->meta_held = (value != 0);
        return false;
    }

    /* Shift + F1 runs BacklightToggle everywhere (including lockscreen & games) */
    if (code == KEY_F1) {
        if (value == 1 && (st->shift_l || st->shift_r)) {
            st->swallowed_f1 = true;
            trigger_cmd(st, CMD_BACKLIGHT_TOGGLE);
            return true;
        }
        if (st->swallowed_f1) {
            if (value == 0) {
                st->swallowed_f1 = false;
            }
            return true;
        }
    }

    /* Backward (mod3) + Space toggles media play/pause directly from evdev */
    if (code == KEY_SPACE) {
        if (value == 1 && st->backward_held) {
            st->swallowed_space = true;
            trigger_cmd(st, CMD_SYS_CTL " --toggle");
            return true;
        }
        if (st->swallowed_space) {
            if (value == 0) {
                st->swallowed_space = false;
            }
            return true;
        }
    }

    /* External CASUE USB KB: Scroll Lock toggles Fn-Lock */
    if (kind == DEV_KBD_CASUE && code == KEY_SCROLLLOCK) {
        if (value == 1) {
            st->fn_lock = !st->fn_lock;
            if (st->ops.set_casue_scroll_led) {
                st->ops.set_casue_scroll_led(st->ctx, st->fn_lock);
            }
            if (st->ops.notify) {
                st->ops.notify(
                    st->ctx,
                    st->fn_lock ? "Fn-Lock ON" : "Fn-Lock OFF",
                    st->fn_lock ? "CASUE F1-F8: Media & Music controls" : "CASUE F1-F8: Standard F-keys",
                    "input-keyboard"
                );
            }
        }
        return true;
    }

    /* External CASUE USB KB: F1-F8 media row when Fn-Lock is active & unmodified */
    if (kind == DEV_KBD_CASUE && code >= KEY_F1 && code <= KEY_F8) {
        uint16_t bit = (uint16_t)(1u << (code - KEY_F1));
        bool any_mod = st->shift_l || st->shift_r || st->ctrl_held || st->alt_held || st->meta_held;
        const KeyCmdRule *rule = find_rule(
            CASUE_FN_LOCK_RULES,
            sizeof(CASUE_FN_LOCK_RULES) / sizeof(CASUE_FN_LOCK_RULES[0]),
            code
        );
        if (rule) {
            if (value == 1 && st->fn_lock && !any_mod) {
                st->swallowed_fn_mask |= bit;
                trigger_cmd(st, rule->cmd);
                return true;
            }
            if (st->swallowed_fn_mask & bit) {
                if (value == 2 && rule->allow_repeat) {
                    trigger_cmd(st, rule->cmd);
                } else if (value == 0) {
                    st->swallowed_fn_mask &= (uint16_t)~bit;
                }
                return true;
            }
        }
    }

    /* Global hardware media & brightness keys (bypass Wine/X11 grabs) */
    const KeyCmdRule *media = find_rule(
        GLOBAL_MEDIA_RULES,
        sizeof(GLOBAL_MEDIA_RULES) / sizeof(GLOBAL_MEDIA_RULES[0]),
        code
    );
    if (media) {
        if (value == 1 || (value == 2 && media->allow_repeat)) {
            trigger_cmd(st, media->cmd);
        }
        return true;
    }

    /* Laptop ACPI / Quickstart touchpad toggle key */
    if (code == KEY_TOUCHPAD_TOGGLE || (kind == DEV_KBD_ACPI && code == KEY_UNKNOWN)) {
        if (value == 1) {
            trigger_cmd(st, CMD_TOUCHPAD_TOGGLE);
        }
        return true;
    }

    return false;
}

void sys_input_init(SysInputState *st, SysInputOps ops, void *ctx) {
    *st = (SysInputState){0};
    st->ops = ops;
    st->ctx = ctx;
}

void sys_input_handle_event(SysInputState *st, DeviceKind kind, uint16_t type, uint16_t code, int32_t value) {
    if (type == EV_SYN && code == SYN_REPORT) {
        flush_syn(st);
        return;
    }

    if (type == EV_REL) {
        handle_mouse_rel(st, code, value);
        return;
    }

    if (type != EV_KEY) {
        return;
    }

    if (kind == DEV_MOUSE_GM320 && handle_gm320_special_key(st, code, value)) {
        return;
    }

    if (code >= BTN_MOUSE && code <= BTN_TASK) {
        if (!handle_mouse_button(st, code, value)) {
            emit_ptr_ev(st, EV_KEY, code, value);
        }
        return;
    }

    if (!handle_keyboard_key(st, kind, code, value)) {
        emit_kbd_ev(st, EV_KEY, code, value);
    }
}

void sys_input_on_device_removed(SysInputState *st, DeviceKind kind) {
    if (kind == DEV_MOUSE_GM320 || kind == DEV_GENERIC_MOUSE) {
        release_desktop_modifiers(st);
        if (st->side_passed_through) {
            st->side_passed_through = false;
            emit_ptr_ev(st, EV_KEY, BTN_SIDE, 0);
        }
        if (st->extra_passed_through) {
            st->extra_passed_through = false;
            emit_ptr_ev(st, EV_KEY, BTN_EXTRA, 0);
        }
        st->swallowed_mouse_btns = 0;
        flush_syn(st);
    }
    if (kind == DEV_KBD_CASUE) {
        st->swallowed_fn_mask = 0;
        st->shift_l = false;
        st->shift_r = false;
        st->ctrl_held = false;
        st->alt_held = false;
        st->meta_held = false;
    }
}
