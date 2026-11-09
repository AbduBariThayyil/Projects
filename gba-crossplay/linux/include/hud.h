#ifndef GBA_CROSSPLAY_HUD_H
#define GBA_CROSSPLAY_HUD_H

#include <SDL2/SDL.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    GBA_NET_SINGLE_PLAYER,
    GBA_NET_HOSTING,
    GBA_NET_CONNECTED
} GBANetMode;

typedef enum {
    MENU_RESUME = 0,
    MENU_SAVE_STATE,
    MENU_LOAD_STATE,
    MENU_MULTIPLAYER,
    MENU_TURBO_SPEED,
    MENU_TOGGLE_HUD,
    MENU_QUIT,
    MENU_COUNT
} GBAMenuItem;

typedef struct {
    GBANetMode net_mode;
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

    /* Toast Notification */
    char toast_msg[64];
    SDL_Color toast_color;
    uint32_t toast_until_ms;

    /* In-Game Menu Overlay */
    bool menu_open;
    int menu_selected;
    int selected_slot; /* 1 - 9 */
    int mp_action_mode; /* 0: Host, 1: Join */
} GBAHUDState;

void gba_hud_init(GBAHUDState* state);
void gba_hud_show_toast(GBAHUDState* state, const char* msg, SDL_Color color, uint32_t duration_ms);
void gba_hud_draw(SDL_Renderer* renderer, int window_w, int window_h, const GBAHUDState* state);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_HUD_H */
