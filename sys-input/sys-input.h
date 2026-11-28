#ifndef SYS_INPUT_H
#define SYS_INPUT_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    DEV_KBD_LAPTOP = 0,
    DEV_KBD_CASUE,
    DEV_KBD_ACPI,
    DEV_MOUSE_GM320,
    DEV_GENERIC_KBD,
    DEV_GENERIC_MOUSE
} DeviceKind;

typedef struct {
    void (*emit_kbd)(void *ctx, uint16_t type, uint16_t code, int32_t value);
    void (*emit_kbd_syn)(void *ctx);
    void (*emit_ptr)(void *ctx, uint16_t type, uint16_t code, int32_t value);
    void (*emit_ptr_syn)(void *ctx);
    void (*schedule_ptr_tap_release)(void *ctx, uint16_t code, int delay_ms);
    void (*set_casue_scroll_led)(void *ctx, bool on);
    void (*run_cmd)(void *ctx, const char *cmd);
    void (*notify_toggle)(void *ctx, const char *kind, bool active);
} SysInputOps;

typedef struct {
    bool gaming_mode;
    bool nfs_mode;
    bool auto_in_game;
    bool fn_lock;
    bool shift_l;
    bool shift_r;
    bool ctrl_held;
    bool alt_held;
    bool meta_held;
    bool backward_held;
    bool forward_held;
    bool forward_used_chord;
    uint16_t side_active_code;
    bool side_active_is_kbd;
    uint16_t extra_active_code;
    bool extra_active_is_kbd;
    uint32_t swallowed_mouse_btns;
    bool swallowed_space;
    bool swallowed_f1;
    bool swallowed_end;
    uint16_t swallowed_fn_mask;
    bool kbd_dirty;
    bool ptr_dirty;
    SysInputOps ops;
    void *ctx;
} SysInputState;

void sys_input_init(SysInputState *st, SysInputOps ops, void *ctx);
void sys_input_handle_event(SysInputState *st, DeviceKind kind, uint16_t type, uint16_t code, int32_t value);
void sys_input_set_game_context(SysInputState *st, bool in_game, bool in_nfs);
void sys_input_on_device_removed(SysInputState *st, DeviceKind kind);

#endif
