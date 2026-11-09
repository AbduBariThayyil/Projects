#include "browser.h"
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdint.h>

/* Minimalist 8x8 font helper (referenced from hud.c) */
static const uint8_t FONT_8X8[95][8] = {
    {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}, /* ' ' */
    {0x18,0x3C,0x3C,0x18,0x18,0x00,0x18,0x00}, /* '!' */
    {0x66,0x66,0x24,0x00,0x00,0x00,0x00,0x00}, /* '"' */
    {0x6C,0x6C,0xFE,0x6C,0xFE,0x6C,0x6C,0x00}, /* '#' */
    {0x18,0x3E,0x60,0x3C,0x06,0x7C,0x18,0x00}, /* '$' */
    {0x00,0x66,0xA6,0xD4,0x2B,0x65,0x66,0x00}, /* '%' */
    {0x1C,0x36,0x1C,0x38,0x6D,0x67,0x3B,0x00}, /* '&' */
    {0x18,0x18,0x30,0x00,0x00,0x00,0x00,0x00}, /* ''' */
    {0x0C,0x18,0x30,0x30,0x30,0x18,0x0C,0x00}, /* '(' */
    {0x30,0x18,0x0C,0x0C,0x0C,0x18,0x30,0x00}, /* ')' */
    {0x00,0x66,0x3C,0xFF,0x3C,0x66,0x00,0x00}, /* '*' */
    {0x00,0x18,0x18,0x7E,0x18,0x18,0x00,0x00}, /* '+' */
    {0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x30}, /* ',' */
    {0x00,0x00,0x00,0x7E,0x00,0x00,0x00,0x00}, /* '-' */
    {0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00}, /* '.' */
    {0x06,0x0C,0x18,0x30,0x60,0xC0,0x80,0x00}, /* '/' */
    {0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00}, /* '0' */
    {0x18,0x38,0x18,0x18,0x18,0x18,0x7E,0x00}, /* '1' */
    {0x3C,0x66,0x06,0x0C,0x18,0x30,0x7E,0x00}, /* '2' */
    {0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00}, /* '3' */
    {0x0C,0x1C,0x3C,0x6C,0xFE,0x0C,0x0C,0x00}, /* '4' */
    {0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00}, /* '5' */
    {0x1C,0x30,0x60,0x7C,0x66,0x66,0x3C,0x00}, /* '6' */
    {0x7E,0x06,0x0C,0x18,0x30,0x30,0x30,0x00}, /* '7' */
    {0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00}, /* '8' */
    {0x3C,0x66,0x66,0x3E,0x06,0x0C,0x38,0x00}, /* '9' */
    {0x00,0x18,0x18,0x00,0x18,0x18,0x00,0x00}, /* ':' */
    {0x00,0x18,0x18,0x00,0x18,0x18,0x30,0x00}, /* ';' */
    {0x0C,0x18,0x30,0x60,0x30,0x18,0x0C,0x00}, /* '<' */
    {0x00,0x00,0x7E,0x00,0x7E,0x00,0x00,0x00}, /* '=' */
    {0x30,0x18,0x0C,0x06,0x0C,0x18,0x30,0x00}, /* '>' */
    {0x3C,0x66,0x06,0x0C,0x18,0x00,0x18,0x00}, /* '?' */
    {0x3C,0x66,0x6E,0x6A,0x6E,0x60,0x3C,0x00}, /* '@' */
    {0x18,0x3C,0x66,0x66,0x7E,0x66,0x66,0x00}, /* 'A' */
    {0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00}, /* 'B' */
    {0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00}, /* 'C' */
    {0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00}, /* 'D' */
    {0x7E,0x60,0x60,0x78,0x60,0x60,0x7E,0x00}, /* 'E' */
    {0x7E,0x60,0x60,0x78,0x60,0x60,0x60,0x00}, /* 'F' */
    {0x3C,0x66,0x60,0x6E,0x66,0x66,0x3C,0x00}, /* 'G' */
    {0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00}, /* 'H' */
    {0x3C,0x18,0x18,0x18,0x18,0x18,0x3C,0x00}, /* 'I' */
    {0x0E,0x06,0x06,0x06,0x06,0x66,0x3C,0x00}, /* 'J' */
    {0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00}, /* 'K' */
    {0x60,0x60,0x60,0x60,0x60,0x60,0x7E,0x00}, /* 'L' */
    {0x63,0x77,0x7F,0x6B,0x63,0x63,0x63,0x00}, /* 'M' */
    {0x66,0x76,0x7E,0x7E,0x6E,0x66,0x66,0x00}, /* 'N' */
    {0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00}, /* 'O' */
    {0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00}, /* 'P' */
    {0x3C,0x66,0x66,0x66,0x6A,0x6C,0x36,0x00}, /* 'Q' */
    {0x7C,0x66,0x66,0x7C,0x6C,0x66,0x66,0x00}, /* 'R' */
    {0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00}, /* 'S' */
    {0x7E,0x18,0x18,0x18,0x18,0x18,0x18,0x00}, /* 'T' */
    {0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00}, /* 'U' */
    {0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00}, /* 'V' */
    {0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00}, /* 'W' */
    {0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00}, /* 'X' */
    {0x66,0x66,0x66,0x3C,0x18,0x18,0x18,0x00}, /* 'Y' */
    {0x7E,0x06,0x0C,0x18,0x30,0x60,0x7E,0x00}, /* 'Z' */
    {0x3C,0x30,0x30,0x30,0x30,0x30,0x3C,0x00}, /* '[' */
    {0xC0,0x60,0x30,0x18,0x0C,0x06,0x02,0x00}, /* '\' */
    {0x3C,0x0C,0x0C,0x0C,0x0C,0x0C,0x3C,0x00}, /* ']' */
    {0x18,0x3C,0x66,0x00,0x00,0x00,0x00,0x00}, /* '^' */
    {0x00,0x00,0x00,0x00,0x00,0x00,0xFF,0x00}, /* '_' */
    {0x30,0x18,0x0C,0x00,0x00,0x00,0x00,0x00}, /* '`' */
    {0x00,0x00,0x3C,0x06,0x3E,0x66,0x3B,0x00}, /* 'a' */
    {0x60,0x60,0x7C,0x66,0x66,0x66,0x7C,0x00}, /* 'b' */
    {0x00,0x00,0x3C,0x66,0x60,0x66,0x3C,0x00}, /* 'c' */
    {0x06,0x06,0x3E,0x66,0x66,0x66,0x3E,0x00}, /* 'd' */
    {0x00,0x00,0x3C,0x66,0x7E,0x60,0x3C,0x00}, /* 'e' */
    {0x0E,0x18,0x7E,0x18,0x18,0x18,0x18,0x00}, /* 'f' */
    {0x00,0x00,0x3B,0x66,0x66,0x3E,0x06,0x3C}, /* 'g' */
    {0x60,0x60,0x7C,0x66,0x66,0x66,0x66,0x00}, /* 'h' */
    {0x18,0x00,0x38,0x18,0x18,0x18,0x3C,0x00}, /* 'i' */
    {0x06,0x00,0x06,0x06,0x06,0x66,0x3C,0x00}, /* 'j' */
    {0x60,0x60,0x66,0x6C,0x78,0x6C,0x66,0x00}, /* 'k' */
    {0x38,0x18,0x18,0x18,0x18,0x18,0x3C,0x00}, /* 'l' */
    {0x00,0x00,0x66,0x7F,0x7F,0x6B,0x63,0x00}, /* 'm' */
    {0x00,0x00,0x7C,0x66,0x66,0x66,0x66,0x00}, /* 'n' */
    {0x00,0x00,0x3C,0x66,0x66,0x66,0x3C,0x00}, /* 'o' */
    {0x00,0x00,0x7C,0x66,0x66,0x7C,0x60,0x60}, /* 'p' */
    {0x00,0x00,0x3E,0x66,0x66,0x3E,0x06,0x07}, /* 'q' */
    {0x00,0x00,0x7C,0x66,0x60,0x60,0x60,0x00}, /* 'r' */
    {0x00,0x00,0x3E,0x60,0x3C,0x06,0x7C,0x00}, /* 's' */
    {0x18,0x18,0x7E,0x18,0x18,0x18,0x0E,0x00}, /* 't' */
    {0x00,0x00,0x66,0x66,0x66,0x66,0x3E,0x00}, /* 'u' */
    {0x00,0x00,0x66,0x66,0x66,0x3C,0x18,0x00}, /* 'v' */
    {0x00,0x00,0x63,0x6B,0x7F,0x7F,0x36,0x00}, /* 'w' */
    {0x00,0x00,0x66,0x3C,0x18,0x3C,0x66,0x00}, /* 'x' */
    {0x00,0x00,0x66,0x66,0x66,0x3E,0x06,0x3C}, /* 'y' */
    {0x00,0x00,0x7E,0x0C,0x18,0x30,0x7E,0x00}, /* 'z' */
    {0x0E,0x18,0x18,0x70,0x18,0x18,0x0E,0x00}, /* '{' */
    {0x18,0x18,0x18,0x00,0x18,0x18,0x18,0x00}, /* '|' */
    {0x70,0x18,0x18,0x0E,0x18,0x18,0x70,0x00}, /* '}' */
    {0x76,0xDC,0x00,0x00,0x00,0x00,0x00,0x00}  /* '~' */
};

static void draw_char(SDL_Renderer* ren, char c, int x, int y, int scale, SDL_Color color) {
    if (c < 32 || c > 126) c = '?';
    int idx = c - 32;

    SDL_SetRenderDrawColor(ren, color.r, color.g, color.b, color.a);
    for (int row = 0; row < 8; row++) {
        uint8_t bits = FONT_8X8[idx][row];
        for (int col = 0; col < 8; col++) {
            if (bits & (0x80 >> col)) {
                SDL_Rect r = { x + col * scale, y + row * scale, scale, scale };
                SDL_RenderFillRect(ren, &r);
            }
        }
    }
}

static void draw_string(SDL_Renderer* ren, const char* str, int x, int y, int scale, SDL_Color color) {
    int cur_x = x;
    while (*str) {
        draw_char(ren, *str, cur_x, y, scale, color);
        cur_x += 8 * scale;
        str++;
    }
}

static uint32_t* load_png_rgba(const char* filename, int* width, int* height) {
    FILE* fp = fopen(filename, "rb");
    if (!fp) return NULL;

    png_structp png = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!png) { fclose(fp); return NULL; }

    png_infop info = png_create_info_struct(png);
    if (!info) { png_destroy_read_struct(&png, NULL, NULL); fclose(fp); return NULL; }

    if (setjmp(png_jmpbuf(png))) {
        png_destroy_read_struct(&png, &info, NULL);
        fclose(fp);
        return NULL;
    }

    png_init_io(png, fp);
    png_read_info(png, info);

    *width = png_get_image_width(png, info);
    *height = png_get_image_height(png, info);
    png_byte color_type = png_get_color_type(png, info);
    png_byte bit_depth  = png_get_bit_depth(png, info);

    if (bit_depth == 16) png_set_strip_16(png);
    if (color_type == PNG_COLOR_TYPE_PALETTE) png_set_palette_to_rgb(png);
    if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) png_set_expand_gray_1_2_4_to_8(png);
    if (png_get_valid(png, info, PNG_INFO_tRNS)) png_set_tRNS_to_alpha(png);
    if (color_type == PNG_COLOR_TYPE_RGB || color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_PALETTE)
        png_set_filler(png, 0xFF, PNG_FILLER_AFTER);
    if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA)
        png_set_gray_to_rgb(png);

    png_read_update_info(png, info);

    uint32_t* buffer = (uint32_t*)malloc(*width * *height * sizeof(uint32_t));
    if (!buffer) {
        png_destroy_read_struct(&png, &info, NULL);
        fclose(fp);
        return NULL;
    }

    png_bytep* row_pointers = (png_bytep*)malloc(sizeof(png_bytep) * *height);
    for (int y = 0; y < *height; y++) {
        row_pointers[y] = (png_byte*)(buffer + y * *width);
    }

    png_read_image(png, row_pointers);
    free(row_pointers);
    png_destroy_read_struct(&png, &info, NULL);
    fclose(fp);

    return buffer;
}

static SDL_Texture* create_cover_texture(SDL_Renderer* renderer, const char* png_path, int* out_w, int* out_h) {
    int w, h;
    uint32_t* pixels = load_png_rgba(png_path, &w, &h);
    if (!pixels) return NULL;

    SDL_Texture* tex = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                          SDL_TEXTUREACCESS_STATIC, w, h);
    if (tex) {
        SDL_UpdateTexture(tex, NULL, pixels, w * sizeof(uint32_t));
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
        if (out_w) *out_w = w;
        if (out_h) *out_h = h;
    }
    free(pixels);
    return tex;
}

bool gba_browser_scan(GBABrowser* browser, const char* dir_path, SDL_Renderer* renderer) {
    if (!browser || !dir_path) return false;
    memset(browser, 0, sizeof(*browser));

    DIR* dir = opendir(dir_path);
    if (!dir) return false;

    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL && browser->count < MAX_GBA_GAMES) {
        if (entry->d_name[0] == '.') continue;

        size_t len = strlen(entry->d_name);
        if (len < 5) continue;

        const char* ext = entry->d_name + len - 4;
        if (strcasecmp(ext, ".gba") != 0 && strcasecmp(ext, ".bin") != 0) continue;

        GBAGameEntry* game = &browser->games[browser->count];
        strncpy(game->filename, entry->d_name, sizeof(game->filename) - 1);
        snprintf(game->full_path, sizeof(game->full_path), "%s/%s", dir_path, entry->d_name);

        /* Extract base name */
        char base[128];
        memset(base, 0, sizeof(base));
        if (len - 4 < sizeof(base)) {
            memcpy(base, entry->d_name, len - 4);
        }
        snprintf(game->title, sizeof(game->title), "%s", base);

        /* Check file size */
        struct stat st;
        if (stat(game->full_path, &st) == 0) {
            game->file_size_mb = (int)(st.st_size / (1024 * 1024));
        }

        /* Check Save states */
        game->state_count = 0;
        for (int s = 1; s <= 9; s++) {
            char ss_path[512];
            snprintf(ss_path, sizeof(ss_path), "%s/%s.ss%d", dir_path, base, s);
            if (access(ss_path, F_OK) == 0) {
                game->state_count++;
            }
        }

        /* Check Box Front Cover */
        snprintf(game->cover_path, sizeof(game->cover_path), "%s/media/boxFront/%s.png", dir_path, base);
        if (access(game->cover_path, F_OK) == 0) {
            game->has_cover = true;
            if (renderer) {
                game->cover_texture = create_cover_texture(renderer, game->cover_path, &game->cover_w, &game->cover_h);
            }
        } else {
            game->has_cover = false;
            game->cover_texture = NULL;
        }

        browser->count++;
    }
    closedir(dir);
    return (browser->count > 0);
}

void gba_browser_free(GBABrowser* browser) {
    if (!browser) return;
    for (int i = 0; i < browser->count; i++) {
        if (browser->games[i].cover_texture) {
            SDL_DestroyTexture(browser->games[i].cover_texture);
            browser->games[i].cover_texture = NULL;
        }
    }
}

char* gba_browser_run(GBABrowser* browser, SDL_Window* window, SDL_Renderer* renderer) {
    if (!browser || browser->count == 0 || !window || !renderer) return NULL;

    bool running = true;
    char* chosen_path = NULL;

    while (running) {
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) {
                running = false;
            } else if (ev.type == SDL_KEYDOWN) {
                SDL_Keycode k = ev.key.keysym.sym;
                if (k == SDLK_ESCAPE) {
                    running = false;
                } else if (k == SDLK_UP) {
                    browser->selected_idx = (browser->selected_idx - 1 + browser->count) % browser->count;
                } else if (k == SDLK_DOWN) {
                    browser->selected_idx = (browser->selected_idx + 1) % browser->count;
                } else if (k == SDLK_RETURN || k == SDLK_SPACE) {
                    chosen_path = strdup(browser->games[browser->selected_idx].full_path);
                    running = false;
                } else if (k == SDLK_f || k == SDLK_b) {
                    /* Open external file picker starting in GBA dir */
                    char picked[1024] = {0};
                    FILE* fp = popen("GTK_THEME=catppuccin-mocha-teal-standard+default ADW_DEBUG_COLOR_SCHEME=prefer-dark zenity --file-selection --filename='/home/vibecoder/Games/Console Games/GBA/' --title='Select GBA ROM' --file-filter='GBA ROMs (*.gba *.bin)|*.gba *.bin' --file-filter='All Files|*' 2>/dev/null", "r");
                    if (fp) {
                        if (fgets(picked, sizeof(picked), fp)) {
                            size_t l = strlen(picked);
                            if (l > 0 && picked[l - 1] == '\n') picked[l - 1] = '\0';
                        }
                        pclose(fp);
                    }
                    if (picked[0] != '\0') {
                        chosen_path = strdup(picked);
                        running = false;
                    }
                }
            } else if (ev.type == SDL_CONTROLLERBUTTONDOWN) {
                SDL_GameControllerButton b = ev.cbutton.button;
                if (b == SDL_CONTROLLER_BUTTON_DPAD_UP) {
                    browser->selected_idx = (browser->selected_idx - 1 + browser->count) % browser->count;
                } else if (b == SDL_CONTROLLER_BUTTON_DPAD_DOWN) {
                    browser->selected_idx = (browser->selected_idx + 1) % browser->count;
                } else if (b == SDL_CONTROLLER_BUTTON_A) {
                    chosen_path = strdup(browser->games[browser->selected_idx].full_path);
                    running = false;
                } else if (b == SDL_CONTROLLER_BUTTON_B) {
                    running = false;
                }
            }
        }

        /* Render Game Library Browser UI */
        int win_w, win_h;
        SDL_GetWindowSize(window, &win_w, &win_h);

        /* Catppuccin Base Background */
        SDL_SetRenderDrawColor(renderer, 30, 30, 46, 255); /* #1E1E2E */
        SDL_RenderClear(renderer);

        /* Top Header Bar */
        SDL_SetRenderDrawColor(renderer, 24, 24, 37, 255); /* #181825 */
        SDL_Rect header_rect = { 0, 0, win_w, 48 };
        SDL_RenderFillRect(renderer, &header_rect);
        SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255);
        SDL_RenderDrawLine(renderer, 0, 48, win_w, 48);

        draw_string(renderer, "GBA CROSSPLAY - GAME LIBRARY", 20, 14, 2, (SDL_Color){ 203, 166, 247, 255 }); /* Mauve */
        draw_string(renderer, "Arch Linux / iOS", win_w - 180, 18, 1, (SDL_Color){ 166, 173, 200, 255 });

        /* Left Panel: Cover Art Box */
        int cover_box_x = 24;
        int cover_box_y = 68;
        int cover_box_w = 260;
        int cover_box_h = 320;

        SDL_Rect box_rect = { cover_box_x, cover_box_y, cover_box_w, cover_box_h };
        SDL_SetRenderDrawColor(renderer, 24, 24, 37, 255); /* Mantle */
        SDL_RenderFillRect(renderer, &box_rect);
        SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255);
        SDL_RenderDrawRect(renderer, &box_rect);

        GBAGameEntry* sel_game = &browser->games[browser->selected_idx];
        if (sel_game->cover_texture) {
            /* Maintain 1:1 aspect ratio inside cover box */
            int pad = 12;
            int img_avail_w = cover_box_w - pad * 2;
            int img_avail_h = cover_box_h - pad * 2;
            int img_w = img_avail_w;
            int img_h = img_avail_h;

            if (sel_game->cover_w > 0 && sel_game->cover_h > 0) {
                float aspect = (float)sel_game->cover_w / (float)sel_game->cover_h;
                if (aspect > 1.0f) {
                    img_h = (int)(img_w / aspect);
                } else {
                    img_w = (int)(img_h * aspect);
                }
            }
            SDL_Rect dst_cover = {
                cover_box_x + (cover_box_w - img_w) / 2,
                cover_box_y + (cover_box_h - img_h) / 2,
                img_w,
                img_h
            };
            SDL_RenderCopy(renderer, sel_game->cover_texture, NULL, &dst_cover);
            SDL_SetRenderDrawColor(renderer, 148, 226, 213, 200); /* Teal border */
            SDL_RenderDrawRect(renderer, &dst_cover);
        } else {
            /* Placeholder Cartridge */
            SDL_Rect cart = { cover_box_x + 30, cover_box_y + 60, cover_box_w - 60, cover_box_h - 120 };
            SDL_SetRenderDrawColor(renderer, 69, 71, 90, 255); /* Surface1 */
            SDL_RenderFillRect(renderer, &cart);
            SDL_SetRenderDrawColor(renderer, 137, 180, 250, 255);
            SDL_RenderDrawRect(renderer, &cart);
            draw_string(renderer, "NO COVER", cover_box_x + 75, cover_box_y + 140, 2, (SDL_Color){ 166, 173, 200, 255 });
        }

        /* Right Panel: Game List */
        int list_x = cover_box_x + cover_box_w + 24;
        int list_y = 68;
        int list_w = win_w - list_x - 24;

        for (int i = 0; i < browser->count; i++) {
            GBAGameEntry* g = &browser->games[i];
            bool is_sel = (i == browser->selected_idx);
            int row_y = list_y + i * 64;

            SDL_Rect row_rect = { list_x, row_y, list_w, 56 };
            if (is_sel) {
                SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255); /* Surface0 */
                SDL_RenderFillRect(renderer, &row_rect);
                SDL_SetRenderDrawColor(renderer, 148, 226, 213, 255); /* Teal accent bar */
                SDL_Rect sel_bar = { list_x, row_y, 4, 56 };
                SDL_RenderFillRect(renderer, &sel_bar);

                char row_title[128];
                snprintf(row_title, sizeof(row_title), "> %s", g->title);
                draw_string(renderer, row_title, list_x + 14, row_y + 10, 2, (SDL_Color){ 148, 226, 213, 255 });
            } else {
                SDL_SetRenderDrawColor(renderer, 24, 24, 37, 200); /* Mantle */
                SDL_RenderFillRect(renderer, &row_rect);
                SDL_SetRenderDrawColor(renderer, 49, 50, 68, 150);
                SDL_RenderDrawRect(renderer, &row_rect);

                char row_title[128];
                snprintf(row_title, sizeof(row_title), "  %s", g->title);
                draw_string(renderer, row_title, list_x + 14, row_y + 10, 2, (SDL_Color){ 205, 214, 244, 220 });
            }

            /* Subtext: File size & Save states */
            char sub[128];
            if (g->state_count > 0) {
                snprintf(sub, sizeof(sub), "    %s (%d MB) | Saves: %d slots", g->filename, g->file_size_mb, g->state_count);
            } else {
                snprintf(sub, sizeof(sub), "    %s (%d MB) | No save states", g->filename, g->file_size_mb);
            }
            draw_string(renderer, sub, list_x + 14, row_y + 34, 1, is_sel ? (SDL_Color){ 166, 227, 161, 255 } : (SDL_Color){ 166, 173, 200, 200 });
        }

        /* Bottom Controls Help Bar */
        SDL_SetRenderDrawColor(renderer, 24, 24, 37, 255);
        SDL_Rect btm_rect = { 0, win_h - 36, win_w, 36 };
        SDL_RenderFillRect(renderer, &btm_rect);
        SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255);
        SDL_RenderDrawLine(renderer, 0, win_h - 36, win_w, win_h - 36);

        const char* hint = "[UP/DOWN] Select Game   [ENTER/A] Play   [F] File Picker   [ESC] Exit";
        draw_string(renderer, hint, 20, win_h - 24, 1, (SDL_Color){ 166, 173, 200, 255 });

        SDL_RenderPresent(renderer);
        usleep(16000);
    }

    return chosen_path;
}
