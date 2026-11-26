#include "sys-input.h"

#include <assert.h>
#include <linux/input-event-codes.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    uint16_t type;
    uint16_t code;
    int32_t value;
} EmittedEv;

typedef struct {
    EmittedEv kbd[128];
    size_t kbd_len;
    EmittedEv ptr[128];
    size_t ptr_len;
    uint16_t tap_release_code;
    int tap_release_delay;
    bool scroll_led;
    int scroll_led_calls;
    char cmds[32][128];
    size_t cmd_len;
    char last_notify_title[64];
    size_t notify_len;
} TestHarness;

static void reset_harness(TestHarness *h) {
    memset(h, 0, sizeof(*h));
}

static void on_emit_kbd(void *ctx, uint16_t type, uint16_t code, int32_t value) {
    TestHarness *h = ctx;
    assert(h->kbd_len < 128);
    h->kbd[h->kbd_len++] = (EmittedEv){ type, code, value };
}

static void on_emit_kbd_syn(void *ctx) {
    TestHarness *h = ctx;
    assert(h->kbd_len < 128);
    h->kbd[h->kbd_len++] = (EmittedEv){ EV_SYN, SYN_REPORT, 0 };
}

static void on_emit_ptr(void *ctx, uint16_t type, uint16_t code, int32_t value) {
    TestHarness *h = ctx;
    assert(h->ptr_len < 128);
    h->ptr[h->ptr_len++] = (EmittedEv){ type, code, value };
}

static void on_emit_ptr_syn(void *ctx) {
    TestHarness *h = ctx;
    assert(h->ptr_len < 128);
    h->ptr[h->ptr_len++] = (EmittedEv){ EV_SYN, SYN_REPORT, 0 };
}

static void on_schedule_tap_release(void *ctx, uint16_t code, int delay_ms) {
    TestHarness *h = ctx;
    h->tap_release_code = code;
    h->tap_release_delay = delay_ms;
}

static void on_set_scroll_led(void *ctx, bool on) {
    TestHarness *h = ctx;
    h->scroll_led = on;
    h->scroll_led_calls++;
}

static void on_run_cmd(void *ctx, const char *cmd) {
    TestHarness *h = ctx;
    assert(h->cmd_len < 32);
    snprintf(h->cmds[h->cmd_len++], 128, "%s", cmd);
}

static void on_notify(void *ctx, const char *title, const char *body, const char *icon) {
    (void)body;
    (void)icon;
    TestHarness *h = ctx;
    snprintf(h->last_notify_title, 64, "%s", title);
    h->notify_len++;
}

static SysInputOps test_ops(void) {
    return (SysInputOps){
        .emit_kbd = on_emit_kbd,
        .emit_kbd_syn = on_emit_kbd_syn,
        .emit_ptr = on_emit_ptr,
        .emit_ptr_syn = on_emit_ptr_syn,
        .schedule_ptr_tap_release = on_schedule_tap_release,
        .set_casue_scroll_led = on_set_scroll_led,
        .run_cmd = on_run_cmd,
        .notify = on_notify,
    };
}

static void send_ev(SysInputState *st, DeviceKind kind, uint16_t type, uint16_t code, int32_t value) {
    sys_input_handle_event(st, kind, type, code, value);
    sys_input_handle_event(st, kind, EV_SYN, SYN_REPORT, 0);
}

static void test_gm320_desktop_and_gaming_mode(void) {
    TestHarness h;
    SysInputState st;
    reset_harness(&h);
    sys_input_init(&st, test_ops(), &h);

    /* Corner button (KEY_MAIL) -> KEY_F15, DPI button (KEY_HOMEPAGE) -> KEY_F14 */
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_MAIL, 1);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_MAIL, 0);
    assert(h.kbd_len == 4);
    assert(h.kbd[0].code == KEY_F15 && h.kbd[0].value == 1);
    assert(h.kbd[2].code == KEY_F15 && h.kbd[2].value == 0);

    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_HOMEPAGE, 1);
    assert(h.kbd[0].code == KEY_F14 && h.kbd[0].value == 1);

    /* Backward + Scroll & Left/Middle/Right & Space in Desktop Mode */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 1);
    assert(h.kbd[0].code == KEY_F23 && h.kbd[0].value == 1);
    assert(h.ptr_len == 0);

    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_REL, REL_WHEEL, 1);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_REL, REL_WHEEL_HI_RES, 120);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_SYN, SYN_REPORT, 0);
    assert(h.cmd_len == 1 && strstr(h.cmds[0], "sys-control --vol-inc") != NULL);
    assert(h.ptr_len == 0);

    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_LEFT, 1);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_SPACE, 1);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_LEFT, 0);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_SPACE, 0);
    assert(h.cmd_len == 3);
    assert(strstr(h.cmds[1], "sys-control --previous") != NULL);
    assert(strstr(h.cmds[2], "sys-control --toggle") != NULL);
    assert(h.ptr_len == 0); /* Swallowed button/space releases never leaked */

    /* Backward + Tab passes Tab through while F23 (mod3) is held for sxhkd */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 1);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_TAB, 1);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_TAB, 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 0);
    assert(h.kbd_len == 8);
    assert(h.kbd[0].code == KEY_F23 && h.kbd[0].value == 1);
    assert(h.kbd[2].code == KEY_TAB && h.kbd[2].value == 1);
    assert(h.kbd[6].code == KEY_F23 && h.kbd[6].value == 0);

    /* Forward tap vs Forward + Scroll brightness */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 1);
    assert(h.ptr_len == 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 0);
    assert(h.ptr_len == 2 && h.ptr[0].code == BTN_EXTRA && h.ptr[0].value == 1);
    assert(h.tap_release_code == BTN_EXTRA && h.tap_release_delay == 15);

    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 1);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_REL, REL_WHEEL, -1);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_REL, REL_WHEEL_HI_RES, -120);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_SYN, SYN_REPORT, 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 0);
    assert(h.cmd_len == 1 && strstr(h.cmds[0], "sys-control --bri-down") != NULL);
    assert(h.ptr_len == 0);

    /* F13 (KEY_CALC on GM320) switches to Gaming Mode */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_CALC, 1);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_CALC, 0);
    assert(st.gaming_mode == true);
    assert(h.notify_len == 1 && strcmp(h.last_notify_title, "Gaming Mode") == 0);

    /* In Gaming Mode, Backward & Forward pass straight through as BTN_SIDE / BTN_EXTRA */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 1);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 1);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_REL, REL_WHEEL, 1);
    sys_input_handle_event(&st, DEV_MOUSE_GM320, EV_SYN, SYN_REPORT, 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 0);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_EXTRA, 0);
    assert(h.cmd_len == 0);
    assert(h.kbd_len == 0);
    assert(h.ptr[0].code == BTN_SIDE && h.ptr[0].value == 1);
    assert(h.ptr[2].code == BTN_EXTRA && h.ptr[2].value == 1);
    assert(h.ptr[4].type == EV_REL && h.ptr[4].code == REL_WHEEL);

    /* Mode toggle while BTN_SIDE is held in Gaming Mode still releases BTN_SIDE cleanly */
    reset_harness(&h);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 1);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, KEY_CALC, 1);
    assert(st.gaming_mode == false);
    send_ev(&st, DEV_MOUSE_GM320, EV_KEY, BTN_SIDE, 0);
    assert(h.ptr[0].code == BTN_SIDE && h.ptr[0].value == 1);
    assert(h.ptr[2].code == BTN_SIDE && h.ptr[2].value == 0);
}

static void test_casue_fn_lock_and_shift_f1(void) {
    TestHarness h;
    SysInputState st;
    reset_harness(&h);
    sys_input_init(&st, test_ops(), &h);

    /* Shift + F1 runs BacklightToggle even before Fn-Lock */
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_LEFTSHIFT, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F1, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_LEFTSHIFT, 0);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F1, 0);
    assert(h.cmd_len == 1 && strstr(h.cmds[0], "BacklightToggle") != NULL);
    /* Only Shift down + Shift up emitted; F1 swallowed */
    assert(h.kbd_len == 4);
    assert(h.kbd[0].code == KEY_LEFTSHIFT && h.kbd[2].code == KEY_LEFTSHIFT);

    /* Toggle Fn-Lock via Scroll Lock on CASUE USB KB */
    reset_harness(&h);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_SCROLLLOCK, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_SCROLLLOCK, 0);
    assert(st.fn_lock == true);
    assert(h.scroll_led == true && h.scroll_led_calls == 1);
    assert(h.kbd_len == 0);

    /* F1..F8 under Fn-Lock */
    reset_harness(&h);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F1, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F1, 0);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F2, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F2, 2); /* repeat allowed for vol-dec */
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F2, 0);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F5, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F5, 2); /* repeat ignored for stop */
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F5, 0);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F9, 1); /* F9 stays normal */
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F9, 0);
    assert(h.cmd_len == 4);
    assert(strstr(h.cmds[0], "LyricViewLauncher") != NULL);
    assert(strstr(h.cmds[1], "sys-control --vol-dec") != NULL);
    assert(strstr(h.cmds[2], "sys-control --vol-dec") != NULL);
    assert(strstr(h.cmds[3], "sys-control --stop") != NULL);
    assert(h.kbd_len == 4 && h.kbd[0].code == KEY_F9);

    /* Alt + F4 still passes Alt+F4 cleanly even when Fn-Lock is ON */
    reset_harness(&h);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_LEFTALT, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F4, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_F4, 0);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_LEFTALT, 0);
    assert(h.cmd_len == 0);
    assert(h.kbd_len == 8 && h.kbd[2].code == KEY_F4);

    /* Laptop keyboard F2 stays normal even when CASUE Fn-Lock is ON */
    reset_harness(&h);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_F2, 1);
    send_ev(&st, DEV_KBD_LAPTOP, EV_KEY, KEY_F2, 0);
    assert(h.cmd_len == 0 && h.kbd_len == 4 && h.kbd[0].code == KEY_F2);

    /* Hardware media + Toshiba touchpad toggle bypass grabs */
    reset_harness(&h);
    send_ev(&st, DEV_KBD_ACPI, EV_KEY, KEY_TOUCHPAD_TOGGLE, 1);
    send_ev(&st, DEV_KBD_ACPI, EV_KEY, KEY_UNKNOWN, 1);
    send_ev(&st, DEV_KBD_CASUE, EV_KEY, KEY_VOLUMEUP, 1);
    assert(h.cmd_len == 3);
    assert(strstr(h.cmds[0], "ToggleTouchpad") != NULL);
    assert(strstr(h.cmds[1], "ToggleTouchpad") != NULL);
    assert(strstr(h.cmds[2], "sys-control --vol-inc") != NULL);
}

int main(void) {
    test_gm320_desktop_and_gaming_mode();
    test_casue_fn_lock_and_shift_f1();
    printf("All sys-input core tests passed!\n");
    return 0;
}
