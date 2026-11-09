#ifndef GBA_CROSSPLAY_HUD_H
#define GBA_CROSSPLAY_HUD_H

#include <SDL2/SDL.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bool connected;
    uint8_t player_id;
    uint8_t total_players;
    char remote_ip[64];
    uint32_t ping_ms;
    bool is_turbo;
    bool turbo_is_toggle;
    uint8_t turbo_multiplier;
    float current_fps;
    bool show_hud;
} GBAHUDState;

void gba_hud_draw(SDL_Renderer* renderer, int window_w, int window_h, const GBAHUDState* state);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_HUD_H */
