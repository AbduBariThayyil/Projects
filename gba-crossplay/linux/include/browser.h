#ifndef GBA_CROSSPLAY_BROWSER_H
#define GBA_CROSSPLAY_BROWSER_H

#include <SDL2/SDL.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_GBA_GAMES 32

typedef struct {
    char title[128];
    char filename[128];
    char full_path[512];
    char cover_path[512];
    bool has_cover;
    SDL_Texture* cover_texture;
    int cover_w;
    int cover_h;
    int state_count;
    int file_size_mb;
} GBAGameEntry;

typedef struct {
    GBAGameEntry games[MAX_GBA_GAMES];
    int count;
    int selected_idx;
} GBABrowser;

/* Scans directory for .gba ROMs and matching boxFront covers */
bool gba_browser_scan(GBABrowser* browser, const char* dir_path, SDL_Renderer* renderer);

/* Runs the interactive graphical browser loop.
   Returns newly allocated string with chosen ROM path, or NULL if cancelled. */
char* gba_browser_run(GBABrowser* browser, SDL_Window* window, SDL_Renderer* renderer);

/* Cleanup loaded textures */
void gba_browser_free(GBABrowser* browser);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_BROWSER_H */
