#include "keyholder.h"

#include <assert.h>
#include <linux/input-event-codes.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    uint16_t code;
    bool is_mouse;
    int32_t value;
} Emitted;

typedef struct {
    Emitted evs[256];
    size_t ev_len;
    int hud_updates;
    int saved_delay;
    int saved_hold;
    int save_calls;
} KHTest;

static void on_emit(void *ctx, uint16_t code, bool is_mouse, int32_t value) {
    KHTest *t = ctx;
    assert(t->ev_len < 256);
    t->evs[t->ev_len++] = (Emitted){ code, is_mouse, value };
}

static void on_hud(void *ctx) {
    KHTest *t = ctx;
    t->hud_updates++;
}

static void on_save(void *ctx, int delay_ms, int hold_ms) {
    KHTest *t = ctx;
    t->saved_delay = delay_ms;
    t->saved_hold = hold_ms;
    t->save_calls++;
}

static KhOps ops(void) {
    return (KhOps){ .emit_key = on_emit, .hud_update = on_hud, .save_config = on_save };
}

static void test_hold_interrupt_restart_and_mod_pause(void) {
    KHTest t = {0};
    KhState st;
    kh_init(&st, ops(), &t, 40, 15);

    int64_t now = 1000000000LL;
    kh_cmd_hold(&st, false, now);
    assert(st.listen_mode == KH_LISTEN_HOLD);

    /* Ignored modifiers cannot be latched */
    kh_on_key_event(&st, KEY_LEFTMETA, 1, now);
    kh_on_key_event(&st, KEY_LEFTMETA, 0, now + 10000000LL);
    assert(st.listen_mode == KH_LISTEN_HOLD);

    /* Latch KEY_LEFT */
    kh_on_key_event(&st, KEY_LEFT, 1, now + 20000000LL);
    assert(st.waiting_release == true);
    assert(t.ev_len == 0);
    kh_on_key_event(&st, KEY_LEFT, 0, now + 40000000LL);
    assert(st.waiting_release == false);
    assert(kh_active_hold_count(&st) == 1);
    assert(t.ev_len == 1 && t.evs[0].code == KEY_LEFT && t.evs[0].value == 1);

    /* Pressing Super pauses Hold safely (emits 0) and restarts 5ms after release (emits 1) */
    kh_on_key_event(&st, KEY_LEFTMETA, 1, now + 100000000LL);
    assert(st.holds[0].paused_by_mod == true);
    assert(t.ev_len == 2 && t.evs[1].code == KEY_LEFT && t.evs[1].value == 0);
    kh_on_key_event(&st, KEY_LEFTMETA, 0, now + 160000000LL);
    assert(st.holds[0].paused_by_mod == false && st.holds[0].phase_released == true);
    kh_tick(&st, now + 170000000LL);
    assert(st.holds[0].phase_released == false);
    assert(t.ev_len == 3 && t.evs[2].code == KEY_LEFT && t.evs[2].value == 1);

    /* Unrelated key interrupt past grace schedules clean 12ms release -> repress */
    kh_on_key_event(&st, KEY_A, 1, now + 400000000LL);
    assert(st.holds[0].phase_released == true);
    assert(t.ev_len == 4 && t.evs[3].code == KEY_LEFT && t.evs[3].value == 0);
    kh_tick(&st, now + 415000000LL);
    assert(st.holds[0].phase_released == false);
    assert(t.ev_len == 5 && t.evs[4].code == KEY_LEFT && t.evs[4].value == 1);

    /* Re-pressing KEY_LEFT after grace stops it cleanly */
    kh_on_key_event(&st, KEY_LEFT, 1, now + 600000000LL);
    assert(kh_active_hold_count(&st) == 0);
    assert(t.ev_len == 6 && t.evs[5].code == KEY_LEFT && t.evs[5].value == 0);
}

static void test_spam_mod_pause_and_simultaneous_hold(void) {
    KHTest t = {0};
    KhState st;
    kh_init(&st, ops(), &t, 40, 15);

    int64_t now = 2000000000LL;

    /* Hold KEY_W */
    kh_cmd_hold(&st, false, now);
    kh_on_key_event(&st, KEY_W, 1, now + 10000000LL);
    kh_on_key_event(&st, KEY_W, 0, now + 20000000LL);
    assert(kh_active_hold_count(&st) == 1);

    /* Start Spam listen, adjust speed via wheel up (faster) then latch BTN_LEFT */
    kh_cmd_spam(&st, 0, 0, now + 30000000LL);
    assert(st.listen_mode == KH_LISTEN_SPAM);
    kh_on_wheel_event(&st, 1, now + 35000000LL);
    assert(st.saved_delay_ms < 40 && t.save_calls == 1);

    kh_on_key_event(&st, BTN_LEFT, 1, now + 40000000LL);
    kh_on_key_event(&st, BTN_LEFT, 0, now + 50000000LL);
    assert(st.spam.active == true && st.spam.is_mouse == true);
    assert(kh_active_hold_count(&st) == 1);

    /* Verify HUD formats both Hold + Spam simultaneously */
    char hud_msg[512];
    kh_format_hud_message(&st, now + 2050000000LL, hud_msg, sizeof(hud_msg));
    assert(strstr(hud_msg, "holds=W") != NULL);
    assert(strstr(hud_msg, "spam=LMB") != NULL);

    /* Tick through release and next press */
    size_t before = t.ev_len;
    kh_tick(&st, now + 70000000LL); /* release after 15ms hold_ms */
    assert(t.ev_len == before + 1 && t.evs[before].value == 0);

    /* Holding Super pauses BOTH Hold (W) and Spam (LMB) immediately */
    kh_tick(&st, now + 100000000LL); /* press LMB */
    assert(st.spam.phase_down == true);
    size_t pre_super = t.ev_len;
    kh_on_key_event(&st, KEY_LEFTMETA, 1, now + 105000000LL);
    assert(st.holds[0].paused_by_mod == true);
    assert(st.spam.paused_by_mod == true);
    assert(st.spam.phase_down == false);
    assert(t.ev_len == pre_super + 2);
    assert(t.evs[pre_super].code == KEY_W && t.evs[pre_super].value == 0);
    assert(t.evs[pre_super + 1].code == BTN_LEFT && t.evs[pre_super + 1].value == 0);

    /* No spam ticks emitted while Super is held */
    kh_tick(&st, now + 200000000LL);
    assert(t.ev_len == pre_super + 2);

    /* Releasing Super resumes both Hold and Spam; holding Shift does NOT pause */
    kh_on_key_event(&st, KEY_LEFTMETA, 0, now + 220000000LL);
    assert(st.holds[0].paused_by_mod == false);
    assert(st.spam.paused_by_mod == false);
    kh_on_key_event(&st, KEY_LEFTSHIFT, 1, now + 221000000LL);
    assert(st.holds[0].paused_by_mod == false && st.spam.paused_by_mod == false);
    kh_tick(&st, now + 230000000LL);
    assert(st.holds[0].phase_released == false && st.spam.phase_down == true);

    /* Terminate releases both W and LMB */
    kh_cmd_terminate(&st, now + 300000000LL);
    assert(kh_has_activity(&st) == false);
}

static void test_esc_cancels_listen(void) {
    KHTest t = {0};
    KhState st;
    kh_init(&st, ops(), &t, 40, 15);
    kh_cmd_spam(&st, 0, 0, 1000);
    assert(st.listen_mode == KH_LISTEN_SPAM);
    kh_on_key_event(&st, KEY_ESC, 1, 2000);
    assert(st.listen_mode == KH_LISTEN_NONE && kh_has_activity(&st) == false);
}

int main(void) {
    test_hold_interrupt_restart_and_mod_pause();
    test_spam_mod_pause_and_simultaneous_hold();
    test_esc_cancels_listen();
    printf("All KeyHolder core tests passed!\n");
    return 0;
}
