#include "turbo_sync.h"
#include <string.h>

void gba_turbo_init(GBATurboCoordinator* tc, uint8_t local_id, uint8_t multiplier) {
    if (!tc) return;
    memset(tc, 0, sizeof(*tc));
    tc->local_player_id = local_id;
    tc->multiplier = (multiplier > 1) ? multiplier : 2;
    tc->effective_turbo = false;
    tc->target_frame_us = GBA_BASE_FRAME_US;
}

void gba_turbo_set_callback(GBATurboCoordinator* tc, GBATurboCallback cb, void* userdata) {
    if (!tc) return;
    tc->on_change = cb;
    tc->callback_userdata = userdata;
}

static void update_effective_state(GBATurboCoordinator* tc) {
    bool any_active = false;
    for (int i = 0; i < GBA_MAX_PLAYERS; i++) {
        if (tc->player_states[i]) {
            any_active = true;
            break;
        }
    }

    if (tc->effective_turbo != any_active) {
        tc->effective_turbo = any_active;
        if (any_active) {
            tc->target_frame_us = GBA_BASE_FRAME_US / tc->multiplier;
        } else {
            tc->target_frame_us = GBA_BASE_FRAME_US;
        }

        if (tc->on_change) {
            tc->on_change(tc->effective_turbo, tc->multiplier, tc->callback_userdata);
        }
    }
}

bool gba_turbo_set_local(GBATurboCoordinator* tc, bool active) {
    if (!tc || tc->local_player_id >= GBA_MAX_PLAYERS) return false;
    if (tc->player_states[tc->local_player_id] == active) {
        return false; /* No change */
    }

    tc->player_states[tc->local_player_id] = active;
    update_effective_state(tc);
    return true; /* State changed, need to broadcast to network */
}

bool gba_turbo_set_remote(GBATurboCoordinator* tc, uint8_t player_id, bool active) {
    if (!tc || player_id >= GBA_MAX_PLAYERS) return false;
    if (tc->player_states[player_id] == active) {
        return false;
    }

    tc->player_states[player_id] = active;
    update_effective_state(tc);
    return true;
}

bool gba_turbo_is_active(const GBATurboCoordinator* tc) {
    return tc ? tc->effective_turbo : false;
}

uint32_t gba_turbo_get_frame_us(const GBATurboCoordinator* tc) {
    return tc ? tc->target_frame_us : GBA_BASE_FRAME_US;
}
