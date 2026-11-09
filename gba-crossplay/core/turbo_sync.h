#ifndef GBA_TURBO_SYNC_H
#define GBA_TURBO_SYNC_H

#include <stdint.h>
#include <stdbool.h>
#include "link_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

#define GBA_BASE_FRAME_US 16742 /* ~59.7275 FPS */

typedef void (*GBATurboCallback)(bool is_active, uint8_t multiplier, void* userdata);

typedef struct {
    uint8_t  local_player_id;
    uint8_t  multiplier; /* e.g. 2 or 3 */
    bool     player_states[GBA_MAX_PLAYERS];
    bool     effective_turbo;
    uint32_t target_frame_us;
    GBATurboCallback on_change;
    void*    callback_userdata;
} GBATurboCoordinator;

void gba_turbo_init(GBATurboCoordinator* tc, uint8_t local_id, uint8_t multiplier);
void gba_turbo_set_callback(GBATurboCoordinator* tc, GBATurboCallback cb, void* userdata);

/* Updates local player's intent (e.g. user pressed/released Turbo button) */
bool gba_turbo_set_local(GBATurboCoordinator* tc, bool active);

/* Updates a remote player's state based on received PKT_TURBO_STATE */
bool gba_turbo_set_remote(GBATurboCoordinator* tc, uint8_t player_id, bool active);

/* Returns whether turbo is currently active across the session */
bool gba_turbo_is_active(const GBATurboCoordinator* tc);

/* Returns current target frame delay in microseconds */
uint32_t gba_turbo_get_frame_us(const GBATurboCoordinator* tc);

#ifdef __cplusplus
}
#endif

#endif /* GBA_TURBO_SYNC_H */
