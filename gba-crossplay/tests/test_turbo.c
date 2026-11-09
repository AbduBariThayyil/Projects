#include "../core/turbo_sync.h"
#include <stdio.h>
#include <assert.h>

static int callback_count = 0;
static bool last_active_cb = false;

static void on_turbo_changed(bool active, uint8_t multiplier, void* userdata) {
    callback_count++;
    last_active_cb = active;
    (void)multiplier;
    (void)userdata;
}

int main(void) {
    printf("Running turbo sync tests...\n");

    GBATurboCoordinator tc;
    gba_turbo_init(&tc, 0, 2); /* Host = 0, 2x multiplier */
    gba_turbo_set_callback(&tc, on_turbo_changed, NULL);

    assert(gba_turbo_is_active(&tc) == false);
    assert(gba_turbo_get_frame_us(&tc) == GBA_BASE_FRAME_US);

    /* Local player activates turbo */
    bool changed = gba_turbo_set_local(&tc, true);
    assert(changed == true);
    assert(gba_turbo_is_active(&tc) == true);
    assert(gba_turbo_get_frame_us(&tc) == GBA_BASE_FRAME_US / 2);
    assert(callback_count == 1);
    assert(last_active_cb == true);

    /* Setting local active again shouldn't trigger duplicate change */
    changed = gba_turbo_set_local(&tc, true);
    assert(changed == false);
    assert(callback_count == 1);

    /* Remote player (e.g. iOS client id=1) also activates turbo */
    changed = gba_turbo_set_remote(&tc, 1, true);
    assert(changed == true);
    assert(gba_turbo_is_active(&tc) == true);
    assert(callback_count == 1); /* Still true, so callback didn't fire again */

    /* Local player releases turbo - effective turbo should STAY TRUE because remote still has it */
    changed = gba_turbo_set_local(&tc, false);
    assert(changed == true);
    assert(gba_turbo_is_active(&tc) == true);
    assert(callback_count == 1);

    /* Remote player releases turbo - NOW it should drop to false */
    changed = gba_turbo_set_remote(&tc, 1, false);
    assert(changed == true);
    assert(gba_turbo_is_active(&tc) == false);
    assert(gba_turbo_get_frame_us(&tc) == GBA_BASE_FRAME_US);
    assert(callback_count == 2);
    assert(last_active_cb == false);

    printf("All turbo sync tests passed successfully!\n");
    return 0;
}
