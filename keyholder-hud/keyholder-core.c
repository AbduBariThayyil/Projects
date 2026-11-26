#define _GNU_SOURCE
#include "keyholder.h"

#include <linux/input-event-codes.h>
#include <stdio.h>
#include <string.h>

#define MOD_META_L (1u << 0)
#define MOD_META_R (1u << 1)
#define MOD_ALT_L  (1u << 2)
#define MOD_ALT_R  (1u << 3)
#define MOD_CTRL_L (1u << 4)
#define MOD_CTRL_R (1u << 5)

static int clamp_int(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

bool kh_is_mouse_button(uint16_t code) {
    return code >= BTN_MOUSE && code <= BTN_TASK;
}

bool kh_is_ignored_code(uint16_t code) {
    switch (code) {
        case KEY_LEFTMETA:
        case KEY_RIGHTMETA:
        case KEY_LEFTALT:
        case KEY_RIGHTALT:
        case KEY_LEFTCTRL:
        case KEY_RIGHTCTRL:
        case KEY_LEFTSHIFT:
        case KEY_RIGHTSHIFT:
        case KEY_CAPSLOCK:
        case KEY_SCROLLLOCK:
        case KEY_NUMLOCK:
        case KEY_COMPOSE:
        case KEY_CALC:
        case KEY_HOMEPAGE:
        case KEY_MAIL:
        case KEY_POWER:
        case KEY_SLEEP:
        case KEY_WAKEUP:
        case KEY_MUTE:
        case KEY_VOLUMEDOWN:
        case KEY_VOLUMEUP:
        case KEY_PLAYPAUSE:
        case KEY_PAUSE:
        case KEY_PLAY:
        case KEY_PREVIOUSSONG:
        case KEY_NEXTSONG:
        case KEY_STOPCD:
        case KEY_BRIGHTNESSDOWN:
        case KEY_BRIGHTNESSUP:
        case KEY_SYSRQ:
        case KEY_FN:
            return true;
        default:
            break;
    }
    if (code >= KEY_F13 && code <= KEY_F24) {
        return true;
    }
    /* Ignore touchpad/stylus pseudo-buttons 0x140..0x14f */
    if (code >= 0x140 && code <= 0x14f) {
        return true;
    }
    return false;
}

typedef struct {
    uint16_t code;
    const char *label;
} KeyLabel;

static const KeyLabel KEY_LABELS[] = {
    { BTN_LEFT,       "LMB" },
    { BTN_RIGHT,      "RMB" },
    { BTN_MIDDLE,     "MMB" },
    { BTN_SIDE,       "M4" },
    { BTN_EXTRA,      "M5" },
    { KEY_LEFT,       "←" },
    { KEY_RIGHT,      "→" },
    { KEY_UP,         "↑" },
    { KEY_DOWN,       "↓" },
    { KEY_SPACE,      "Space" },
    { KEY_ENTER,      "Enter" },
    { KEY_KPENTER,    "KP↵" },
    { KEY_TAB,        "Tab" },
    { KEY_BACKSPACE,  "Bksp" },
    { KEY_ESC,        "Esc" },
    { KEY_DELETE,     "Del" },
    { KEY_INSERT,     "Ins" },
    { KEY_HOME,       "Home" },
    { KEY_END,        "End" },
    { KEY_PAGEUP,     "PgUp" },
    { KEY_PAGEDOWN,   "PgDn" },
    { KEY_MINUS,      "-" },
    { KEY_EQUAL,      "=" },
    { KEY_LEFTBRACE,  "[" },
    { KEY_RIGHTBRACE, "]" },
    { KEY_SEMICOLON,  ";" },
    { KEY_APOSTROPHE, "'" },
    { KEY_GRAVE,      "`" },
    { KEY_BACKSLASH,  "\\" },
    { KEY_COMMA,      "," },
    { KEY_DOT,        "." },
    { KEY_SLASH,      "/" },
};

void kh_key_label(uint16_t code, char *out, size_t out_sz) {
    if (!out || out_sz == 0) return;

    for (size_t i = 0; i < sizeof(KEY_LABELS) / sizeof(KEY_LABELS[0]); i++) {
        if (KEY_LABELS[i].code == code) {
            snprintf(out, out_sz, "%s", KEY_LABELS[i].label);
            return;
        }
    }

    static const char *ALPHA_NUM = NULL;
    (void)ALPHA_NUM;
    if (code >= KEY_1 && code <= KEY_9) {
        snprintf(out, out_sz, "%u", (unsigned)(code - KEY_1 + 1));
        return;
    }
    if (code == KEY_0) {
        snprintf(out, out_sz, "0");
        return;
    }
    if (code >= KEY_F1 && code <= KEY_F10) {
        snprintf(out, out_sz, "F%u", (unsigned)(code - KEY_F1 + 1));
        return;
    }
    if (code == KEY_F11 || code == KEY_F12) {
        snprintf(out, out_sz, "F%u", (unsigned)(code == KEY_F11 ? 11 : 12));
        return;
    }

    static const struct { uint16_t code; char ch; } QWERTY[] = {
        { KEY_Q, 'Q' }, { KEY_W, 'W' }, { KEY_E, 'E' }, { KEY_R, 'R' }, { KEY_T, 'T' },
        { KEY_Y, 'Y' }, { KEY_U, 'U' }, { KEY_I, 'I' }, { KEY_O, 'O' }, { KEY_P, 'P' },
        { KEY_A, 'A' }, { KEY_S, 'S' }, { KEY_D, 'D' }, { KEY_F, 'F' }, { KEY_G, 'G' },
        { KEY_H, 'H' }, { KEY_J, 'J' }, { KEY_K, 'K' }, { KEY_L, 'L' },
        { KEY_Z, 'Z' }, { KEY_X, 'X' }, { KEY_C, 'C' }, { KEY_V, 'V' }, { KEY_B, 'B' },
        { KEY_N, 'N' }, { KEY_M, 'M' },
    };
    for (size_t i = 0; i < sizeof(QWERTY) / sizeof(QWERTY[0]); i++) {
        if (QWERTY[i].code == code) {
            snprintf(out, out_sz, "%c", QWERTY[i].ch);
            return;
        }
    }

    snprintf(out, out_sz, "#%u", (unsigned)code);
}

static bool is_initially_down(const KhState *st, uint16_t code) {
    if (code >= 512) return false;
    return (st->initially_down[code / 8] & (uint8_t)(1u << (code % 8))) != 0;
}

void kh_set_initially_down(KhState *st, uint16_t code, bool down) {
    if (code >= 512) return;
    if (down) {
        st->initially_down[code / 8] |= (uint8_t)(1u << (code % 8));
    } else {
        st->initially_down[code / 8] &= (uint8_t)~(1u << (code % 8));
    }
}

void kh_clear_initially_down(KhState *st) {
    memset(st->initially_down, 0, sizeof(st->initially_down));
}

static void emit_ev(KhState *st, uint16_t code, bool is_mouse, int32_t value) {
    if (st->ops.emit_key) {
        st->ops.emit_key(st->ctx, code, is_mouse, value);
    }
}

static void notify_hud(KhState *st) {
    if (st->ops.hud_update) {
        st->ops.hud_update(st->ctx);
    }
}

static int compute_press_ms(int delay_ms, int hold_ms) {
    int max_press = delay_ms - 2;
    if (max_press < 1) max_press = 1;
    return clamp_int(hold_ms, 1, max_press);
}

static bool should_pause_spam_for_mods(uint32_t mod_mask, uint16_t spam_code) {
    if (mod_mask & (MOD_META_L | MOD_META_R | MOD_ALT_L | MOD_ALT_R)) {
        return true;
    }
    if ((spam_code == KEY_TAB || spam_code == KEY_BACKSPACE) && (mod_mask & (MOD_CTRL_L | MOD_CTRL_R))) {
        return true;
    }
    return false;
}

static bool is_hold_paused_any(const KhState *st) {
    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        if (st->holds[i].active && st->holds[i].paused_by_mod) return true;
    }
    return false;
}

static void update_mod_pause(KhState *st, int64_t now_ns) {
    bool hud_dirty = false;

    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        KhHoldSlot *h = &st->holds[i];
        if (!h->active) continue;
        bool should_pause = should_pause_spam_for_mods(st->mod_mask, h->code);
        if (should_pause && !h->paused_by_mod) {
            if (!h->phase_released) {
                emit_ev(st, h->code, h->is_mouse, 0);
            }
            h->paused_by_mod = true;
            h->phase_released = false;
            hud_dirty = true;
        } else if (!should_pause && h->paused_by_mod) {
            h->paused_by_mod = false;
            h->phase_released = true;
            h->next_reassert_ns = now_ns + 5000000LL; /* 5ms settle after releasing Super/Alt */
            hud_dirty = true;
        }
    }

    if (st->spam.active) {
        bool should_pause = should_pause_spam_for_mods(st->mod_mask, st->spam.code);
        if (should_pause && !st->spam.paused_by_mod) {
            if (st->spam.phase_down) {
                emit_ev(st, st->spam.code, st->spam.is_mouse, 0);
                st->spam.phase_down = false;
            }
            st->spam.paused_by_mod = true;
            hud_dirty = true;
        } else if (!should_pause && st->spam.paused_by_mod) {
            st->spam.paused_by_mod = false;
            st->spam.next_tick_ns = now_ns + 5000000LL; /* 5ms settle after releasing Super/Alt */
            hud_dirty = true;
        }
    }

    if (hud_dirty) {
        notify_hud(st);
    }
}

static void stop_hold_idx(KhState *st, int idx, int64_t now_ns) {
    if (idx < 0 || idx >= KH_MAX_HOLDS || !st->holds[idx].active) return;
    uint16_t code = st->holds[idx].code;
    bool is_mouse = st->holds[idx].is_mouse;
    bool was_down = !st->holds[idx].paused_by_mod && !st->holds[idx].phase_released;
    st->holds[idx].active = false;
    st->holds[idx].paused_by_mod = false;
    st->holds[idx].phase_released = false;
    if (was_down) {
        emit_ev(st, code, is_mouse, 0);
    }

    char lbl[24];
    kh_key_label(code, lbl, sizeof(lbl));
    snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Released %s", lbl);
    st->stop_flash_until_ns = now_ns + 750000000LL;
}

static void stop_all_holds(KhState *st, int64_t now_ns) {
    int count = 0;
    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        if (st->holds[i].active) {
            stop_hold_idx(st, i, now_ns);
            count++;
        }
    }
    if (count > 1) {
        snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Released %d holds", count);
    }
}

static void stop_spam(KhState *st, int64_t now_ns) {
    if (!st->spam.active) return;
    if (st->spam.phase_down) {
        emit_ev(st, st->spam.code, st->spam.is_mouse, 0);
    }
    char lbl[24];
    kh_key_label(st->spam.code, lbl, sizeof(lbl));
    st->spam.active = false;
    st->spam.phase_down = false;
    st->spam.paused_by_mod = false;
    snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Stopped %s", lbl);
    st->stop_flash_until_ns = now_ns + 750000000LL;
}

static void activate_latch(KhState *st, KhListenMode mode, uint16_t code, bool is_mouse, int64_t now_ns) {
    st->stop_flash_until_ns = 0;
    if (mode == KH_LISTEN_HOLD) {
        /* If already holding this key, refresh or keep; find free slot */
        for (int i = 0; i < KH_MAX_HOLDS; i++) {
            if (st->holds[i].active && st->holds[i].code == code) {
                st->holds[i].grace_until_ns = now_ns + KH_GRACE_NS;
                notify_hud(st);
                return;
            }
        }
        if (!st->listen_multi_hold) {
            stop_all_holds(st, now_ns);
        }
        int free_idx = -1;
        for (int i = 0; i < KH_MAX_HOLDS; i++) {
            if (!st->holds[i].active) {
                free_idx = i;
                break;
            }
        }
        if (free_idx < 0) {
            stop_hold_idx(st, 0, now_ns);
            free_idx = 0;
        }
        bool paused_now = should_pause_spam_for_mods(st->mod_mask, code);
        st->holds[free_idx] = (KhHoldSlot){
            .active = true,
            .paused_by_mod = paused_now,
            .phase_released = false,
            .code = code,
            .is_mouse = is_mouse,
            .grace_until_ns = now_ns + KH_GRACE_NS,
            .started_ns = now_ns,
            .next_reassert_ns = 0,
            .last_reassert_ns = now_ns,
        };
        if (!paused_now) {
            emit_ev(st, code, is_mouse, 1);
        }
    } else if (mode == KH_LISTEN_SPAM) {
        if (st->spam.active && st->spam.phase_down) {
            emit_ev(st, st->spam.code, st->spam.is_mouse, 0);
        }
        st->spam = (KhSpamSlot){
            .active = true,
            .paused_by_mod = should_pause_spam_for_mods(st->mod_mask, code),
            .phase_down = false,
            .code = code,
            .is_mouse = is_mouse,
            .delay_ms = st->saved_delay_ms,
            .hold_ms = st->saved_hold_ms,
            .grace_until_ns = now_ns + KH_GRACE_NS,
            .started_ns = now_ns,
            .next_tick_ns = now_ns,
        };
        if (!st->spam.paused_by_mod) {
            int press_ms = compute_press_ms(st->spam.delay_ms, st->spam.hold_ms);
            emit_ev(st, st->spam.code, st->spam.is_mouse, 1);
            st->spam.phase_down = true;
            st->spam.next_tick_ns = now_ns + (int64_t)press_ms * 1000000LL;
        }
    }
    notify_hud(st);
}

void kh_init(KhState *st, KhOps ops, void *ctx, int init_delay_ms, int init_hold_ms) {
    memset(st, 0, sizeof(*st));
    st->ops = ops;
    st->ctx = ctx;
    st->saved_delay_ms = clamp_int(init_delay_ms > 0 ? init_delay_ms : KH_DEFAULT_DELAY, KH_MIN_DELAY, KH_MAX_DELAY);
    st->saved_hold_ms = clamp_int(init_hold_ms > 0 ? init_hold_ms : KH_DEFAULT_HOLD, 1, 500);
}

void kh_cmd_hold(KhState *st, bool multi, int64_t now_ns) {
    if (st->listen_mode == KH_LISTEN_HOLD) {
        st->listen_mode = KH_LISTEN_NONE;
        st->waiting_release = false;
        snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Cancelled");
        st->stop_flash_until_ns = now_ns + 600000000LL;
        notify_hud(st);
        return;
    }
    if (!multi && kh_active_hold_count(st) > 0) {
        stop_all_holds(st, now_ns);
        notify_hud(st);
        return;
    }
    st->listen_multi_hold = multi;
    st->listen_mode = KH_LISTEN_HOLD;
    st->waiting_release = false;
    st->stop_flash_until_ns = 0;
    notify_hud(st);
}

void kh_cmd_spam(KhState *st, int delay_override_ms, int hold_override_ms, int64_t now_ns) {
    if (delay_override_ms > 0) {
        st->saved_delay_ms = clamp_int(delay_override_ms, KH_MIN_DELAY, KH_MAX_DELAY);
        if (st->ops.save_config) st->ops.save_config(st->ctx, st->saved_delay_ms, st->saved_hold_ms);
    }
    if (hold_override_ms > 0) {
        st->saved_hold_ms = clamp_int(hold_override_ms, 1, 500);
        if (st->ops.save_config) st->ops.save_config(st->ctx, st->saved_delay_ms, st->saved_hold_ms);
    }

    if (st->listen_mode == KH_LISTEN_SPAM) {
        st->listen_mode = KH_LISTEN_NONE;
        st->waiting_release = false;
        snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Cancelled");
        st->stop_flash_until_ns = now_ns + 600000000LL;
        notify_hud(st);
        return;
    }
    if (st->spam.active && delay_override_ms <= 0 && hold_override_ms <= 0) {
        stop_spam(st, now_ns);
        notify_hud(st);
        return;
    }
    st->listen_mode = KH_LISTEN_SPAM;
    st->waiting_release = false;
    st->stop_flash_until_ns = 0;
    notify_hud(st);
}

void kh_cmd_terminate(KhState *st, int64_t now_ns) {
    st->listen_mode = KH_LISTEN_NONE;
    st->waiting_release = false;
    stop_all_holds(st, now_ns);
    stop_spam(st, now_ns);
    snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "All released");
    st->stop_flash_until_ns = now_ns + 750000000LL;
    notify_hud(st);
}

void kh_cmd_adjust_delay(KhState *st, double factor, int delta_ms, int explicit_ms) {
    int cur = st->saved_delay_ms;
    int next = cur;
    if (explicit_ms > 0) {
        next = explicit_ms;
    } else if (delta_ms != 0) {
        next = cur + delta_ms;
    } else if (factor > 0.0) {
        next = (int)(cur * factor + 0.5);
        if (next == cur) {
            next = cur + (factor > 1.0 ? 1 : -1);
        }
    }
    st->saved_delay_ms = clamp_int(next, KH_MIN_DELAY, KH_MAX_DELAY);
    if (st->spam.active) {
        st->spam.delay_ms = st->saved_delay_ms;
    }
    if (st->ops.save_config) {
        st->ops.save_config(st->ctx, st->saved_delay_ms, st->saved_hold_ms);
    }
    notify_hud(st);
}

void kh_cmd_set_hold_ms(KhState *st, int hold_ms) {
    st->saved_hold_ms = clamp_int(hold_ms, 1, 500);
    if (st->spam.active) {
        st->spam.hold_ms = st->saved_hold_ms;
    }
    if (st->ops.save_config) {
        st->ops.save_config(st->ctx, st->saved_delay_ms, st->saved_hold_ms);
    }
    notify_hud(st);
}

static void update_mod_bit(KhState *st, uint16_t code, int32_t value, int64_t now_ns) {
    uint32_t bit = 0;
    switch (code) {
        case KEY_LEFTMETA:  bit = MOD_META_L; break;
        case KEY_RIGHTMETA: bit = MOD_META_R; break;
        case KEY_LEFTALT:   bit = MOD_ALT_L;  break;
        case KEY_RIGHTALT:  bit = MOD_ALT_R;  break;
        case KEY_LEFTCTRL:  bit = MOD_CTRL_L; break;
        case KEY_RIGHTCTRL: bit = MOD_CTRL_R; break;
        default: return;
    }
    if (value != 0) {
        st->mod_mask |= bit;
    } else {
        st->mod_mask &= ~bit;
    }
    update_mod_pause(st, now_ns);
}

void kh_on_key_event(KhState *st, uint16_t code, int32_t value, int64_t now_ns) {
    update_mod_bit(st, code, value, now_ns);

    if (value == 0) {
        kh_set_initially_down(st, code, false);
    }

    if (st->waiting_release) {
        if (code == st->pending_code && value == 0) {
            st->waiting_release = false;
            KhListenMode m = st->pending_mode;
            st->pending_mode = KH_LISTEN_NONE;
            activate_latch(st, m, st->pending_code, st->pending_is_mouse, now_ns);
        }
        return;
    }

    if (st->listen_mode != KH_LISTEN_NONE && value == 1) {
        if (code == KEY_ESC) {
            st->listen_mode = KH_LISTEN_NONE;
            snprintf(st->last_stop_msg, sizeof(st->last_stop_msg), "Cancelled");
            st->stop_flash_until_ns = now_ns + 600000000LL;
            notify_hud(st);
            return;
        }
        if (st->listen_mode == KH_LISTEN_SPAM) {
            if (code == KEY_EQUAL || code == KEY_KPPLUS) {
                kh_cmd_adjust_delay(st, 0.8, 0, 0); /* faster */
                return;
            }
            if (code == KEY_MINUS || code == KEY_KPMINUS) {
                kh_cmd_adjust_delay(st, 1.25, 0, 0); /* slower */
                return;
            }
        }
        if (kh_is_ignored_code(code) || is_initially_down(st, code)) {
            return;
        }
        st->pending_code = code;
        st->pending_is_mouse = kh_is_mouse_button(code);
        st->pending_mode = st->listen_mode;
        st->listen_mode = KH_LISTEN_NONE;
        st->waiting_release = true;
        st->wait_deadline_ns = now_ns + 1200000000LL;
        return;
    }

    bool is_held_code = false;
    bool is_spam_code = (st->spam.active && st->spam.code == code);

    if (value == 1) {
        bool changed = false;
        for (int i = 0; i < KH_MAX_HOLDS; i++) {
            if (st->holds[i].active && st->holds[i].code == code) {
                is_held_code = true;
                if (now_ns >= st->holds[i].grace_until_ns) {
                    stop_hold_idx(st, i, now_ns);
                    changed = true;
                }
            }
        }
        if (is_spam_code && now_ns >= st->spam.grace_until_ns) {
            stop_spam(st, now_ns);
            changed = true;
        }
        if (changed) {
            notify_hud(st);
            return;
        }
    } else {
        for (int i = 0; i < KH_MAX_HOLDS; i++) {
            if (st->holds[i].active && st->holds[i].code == code) {
                is_held_code = true;
            }
        }
    }

    /* Restart active Hold(s) cleanly after unrelated in-game key/button interrupts */
    if (!is_held_code && !is_spam_code && (value == 1 || value == 0) && !kh_is_ignored_code(code)) {
        for (int i = 0; i < KH_MAX_HOLDS; i++) {
            KhHoldSlot *h = &st->holds[i];
            if (h->active && !h->paused_by_mod && !h->phase_released &&
                now_ns >= h->grace_until_ns && (now_ns - h->last_reassert_ns) >= 80000000LL) {
                emit_ev(st, h->code, h->is_mouse, 0);
                h->phase_released = true;
                h->next_reassert_ns = now_ns + 12000000LL; /* 12ms release before repress */
                h->last_reassert_ns = now_ns;
            }
        }
    }
}

void kh_on_wheel_event(KhState *st, int32_t value, int64_t now_ns) {
    (void)now_ns;
    if (st->listen_mode == KH_LISTEN_SPAM && value != 0) {
        /* Scroll up -> faster (smaller delay), Scroll down -> slower */
        kh_cmd_adjust_delay(st, value > 0 ? 0.8 : 1.25, 0, 0);
    }
}

void kh_tick(KhState *st, int64_t now_ns) {
    if (st->waiting_release && now_ns >= st->wait_deadline_ns) {
        st->waiting_release = false;
        KhListenMode m = st->pending_mode;
        st->pending_mode = KH_LISTEN_NONE;
        activate_latch(st, m, st->pending_code, st->pending_is_mouse, now_ns);
    }

    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        KhHoldSlot *h = &st->holds[i];
        if (h->active && !h->paused_by_mod && h->phase_released && now_ns >= h->next_reassert_ns) {
            emit_ev(st, h->code, h->is_mouse, 1);
            h->phase_released = false;
        }
    }

    if (st->spam.active && !st->spam.paused_by_mod && now_ns >= st->spam.next_tick_ns) {
        int press_ms = compute_press_ms(st->spam.delay_ms, st->spam.hold_ms);
        int gap_ms = st->spam.delay_ms - press_ms;
        if (gap_ms < 1) gap_ms = 1;

        if (!st->spam.phase_down) {
            emit_ev(st, st->spam.code, st->spam.is_mouse, 1);
            st->spam.phase_down = true;
            st->spam.next_tick_ns = now_ns + (int64_t)press_ms * 1000000LL;
        } else {
            emit_ev(st, st->spam.code, st->spam.is_mouse, 0);
            st->spam.phase_down = false;
            st->spam.next_tick_ns = now_ns + (int64_t)gap_ms * 1000000LL;
        }
    }
}

int64_t kh_next_timeout_ns(const KhState *st, int64_t now_ns) {
    int64_t next = -1;
    if (st->waiting_release) {
        next = st->wait_deadline_ns > now_ns ? (st->wait_deadline_ns - now_ns) : 0;
    }
    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        const KhHoldSlot *h = &st->holds[i];
        if (h->active && !h->paused_by_mod && h->phase_released) {
            int64_t dt = h->next_reassert_ns > now_ns ? (h->next_reassert_ns - now_ns) : 0;
            if (next < 0 || dt < next) next = dt;
        }
    }
    if (st->spam.active && !st->spam.paused_by_mod) {
        int64_t dt = st->spam.next_tick_ns > now_ns ? (st->spam.next_tick_ns - now_ns) : 0;
        if (next < 0 || dt < next) {
            next = dt;
        }
    }
    return next;
}

int kh_active_hold_count(const KhState *st) {
    int c = 0;
    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        if (st->holds[i].active) c++;
    }
    return c;
}

bool kh_has_activity(const KhState *st) {
    if (st->listen_mode != KH_LISTEN_NONE || st->waiting_release || st->spam.active) {
        return true;
    }
    return kh_active_hold_count(st) > 0;
}

void kh_format_hud_message(const KhState *st, int64_t now_ns, char *buf, size_t sz) {
    if (!buf || sz == 0) return;

    char holds_str[128] = "";
    int64_t min_start = 0;
    for (int i = 0; i < KH_MAX_HOLDS; i++) {
        if (!st->holds[i].active) continue;
        char lbl[24];
        kh_key_label(st->holds[i].code, lbl, sizeof(lbl));
        if (holds_str[0] != '\0') {
            strncat(holds_str, ",", sizeof(holds_str) - strlen(holds_str) - 1);
        }
        strncat(holds_str, lbl, sizeof(holds_str) - strlen(holds_str) - 1);
        if (min_start == 0 || st->holds[i].started_ns < min_start) {
            min_start = st->holds[i].started_ns;
        }
    }

    char spam_lbl[24] = "";
    if (st->spam.active) {
        kh_key_label(st->spam.code, spam_lbl, sizeof(spam_lbl));
        if (min_start == 0 || st->spam.started_ns < min_start) {
            min_start = st->spam.started_ns;
        }
    }

    long elapsed_sec = 0;
    if (min_start > 0 && now_ns >= min_start) {
        elapsed_sec = (long)((now_ns - min_start) / 1000000000LL);
    }

    const char *listen_str = "none";
    if (st->listen_mode == KH_LISTEN_HOLD) listen_str = "hold";
    else if (st->listen_mode == KH_LISTEN_SPAM) listen_str = "spam";

    double cps = 1000.0 / (double)st->saved_delay_ms;

    if (!kh_has_activity(st)) {
        const char *msg = (st->last_stop_msg[0] != '\0') ? st->last_stop_msg : "Released";
        snprintf(buf, sz, "stop|%s|cps=%.1f|ms=%d\n", msg, cps, st->saved_delay_ms);
        return;
    }

    snprintf(
        buf, sz,
        "state|listen=%s|holds=%s|spam=%s|cps=%.1f|ms=%d|paused=%d|sec=%ld\n",
        listen_str,
        holds_str,
        spam_lbl,
        cps,
        st->spam.active ? st->spam.delay_ms : st->saved_delay_ms,
        (st->spam.paused_by_mod || is_hold_paused_any(st)) ? 1 : 0,
        elapsed_sec
    );
}
