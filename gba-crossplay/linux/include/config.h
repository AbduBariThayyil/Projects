#ifndef GBA_CROSSPLAY_CONFIG_H
#define GBA_CROSSPLAY_CONFIG_H

#include <SDL2/SDL.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    /* Keyboard Mappings */
    SDL_Keycode key_a;
    SDL_Keycode key_b;
    SDL_Keycode key_l;
    SDL_Keycode key_r;
    SDL_Keycode key_start;
    SDL_Keycode key_select;
    SDL_Keycode key_up;
    SDL_Keycode key_down;
    SDL_Keycode key_left;
    SDL_Keycode key_right;
    SDL_Keycode key_turbo_hold;
    SDL_Keycode key_turbo_toggle;
    SDL_Keycode key_spam_a;
    SDL_Keycode key_spam_b;
    SDL_Keycode key_hud;

    /* Gamepad Button Mappings */
    SDL_GameControllerButton pad_a;
    SDL_GameControllerButton pad_b;
    SDL_GameControllerButton pad_l;
    SDL_GameControllerButton pad_r;
    SDL_GameControllerButton pad_start;
    SDL_GameControllerButton pad_select;
    SDL_GameControllerButton pad_turbo_hold;
    SDL_GameControllerButton pad_turbo_toggle;
    SDL_GameControllerButton pad_spam_a;
    SDL_GameControllerButton pad_spam_b;

    /* Settings */
    uint8_t turbo_multiplier;
    bool dark_mode;
} GBAConfig;

void gba_config_load_defaults(GBAConfig* cfg);
bool gba_config_load_file(GBAConfig* cfg, const char* path);
bool gba_config_save_file(const GBAConfig* cfg, const char* path);
const char* gba_config_get_default_path(void);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_CONFIG_H */
