#ifndef KEYHOLDER_H
#define KEYHOLDER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KH_MAX_HOLDS      4
#define KH_DEFAULT_DELAY  40
#define KH_MIN_DELAY      4
#define KH_MAX_DELAY      2000
#define KH_DEFAULT_HOLD   15
#define KH_GRACE_NS       250000000LL /* 250ms grace before re-press stops latch */

typedef enum {
    KH_LISTEN_NONE = 0,
    KH_LISTEN_HOLD,
    KH_LISTEN_SPAM
} KhListenMode;

typedef struct {
    bool active;
    bool paused_by_mod;
    bool phase_released;
    uint16_t code;
    bool is_mouse;
    int64_t grace_until_ns;
    int64_t started_ns;
    int64_t next_reassert_ns;
    int64_t last_reassert_ns;
} KhHoldSlot;

typedef struct {
    bool active;
    bool paused_by_mod;
    bool phase_down;
    uint16_t code;
    bool is_mouse;
    int delay_ms;
    int hold_ms;
    int64_t grace_until_ns;
    int64_t started_ns;
    int64_t next_tick_ns;
} KhSpamSlot;

typedef struct {
    void (*emit_key)(void *ctx, uint16_t code, bool is_mouse, int32_t value);
    void (*hud_update)(void *ctx);
    void (*save_config)(void *ctx, int delay_ms, int hold_ms);
} KhOps;

typedef struct {
    KhListenMode listen_mode;
    bool listen_multi_hold;
    bool waiting_release;
    uint16_t pending_code;
    bool pending_is_mouse;
    KhListenMode pending_mode;
    int64_t wait_deadline_ns;

    uint8_t initially_down[64]; /* 512-bit key bitmap */
    uint32_t mod_mask;

    KhHoldSlot holds[KH_MAX_HOLDS];
    KhSpamSlot spam;

    int saved_delay_ms;
    int saved_hold_ms;

    char last_stop_msg[96];
    int64_t stop_flash_until_ns;

    KhOps ops;
    void *ctx;
} KhState;

void kh_init(KhState *st, KhOps ops, void *ctx, int init_delay_ms, int init_hold_ms);
bool kh_is_ignored_code(uint16_t code);
bool kh_is_mouse_button(uint16_t code);
void kh_key_label(uint16_t code, char *out, size_t out_sz);

void kh_set_initially_down(KhState *st, uint16_t code, bool down);
void kh_clear_initially_down(KhState *st);

void kh_cmd_hold(KhState *st, bool multi, int64_t now_ns);
void kh_cmd_spam(KhState *st, int delay_override_ms, int hold_override_ms, int64_t now_ns);
void kh_cmd_terminate(KhState *st, int64_t now_ns);
void kh_cmd_adjust_delay(KhState *st, double factor, int delta_ms, int explicit_ms);
void kh_cmd_set_hold_ms(KhState *st, int hold_ms);

void kh_on_key_event(KhState *st, uint16_t code, int32_t value, int64_t now_ns);
void kh_on_wheel_event(KhState *st, int32_t value, int64_t now_ns);
void kh_tick(KhState *st, int64_t now_ns);

int64_t kh_next_timeout_ns(const KhState *st, int64_t now_ns);
bool kh_has_activity(const KhState *st);
int kh_active_hold_count(const KhState *st);
void kh_format_hud_message(const KhState *st, int64_t now_ns, char *buf, size_t sz);

#endif
