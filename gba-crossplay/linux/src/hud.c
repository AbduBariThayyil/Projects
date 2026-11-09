#include "hud.h"
#include <stdio.h>
#include <string.h>

/* Minimalist 8x8 ASCII Font Bitmap (characters 32 to 126) */
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

void gba_hud_init(GBAHUDState* state) {
    if (!state) return;
    memset(state, 0, sizeof(*state));
    state->net_mode = GBA_NET_SINGLE_PLAYER;
    state->show_hud = true;
    state->selected_slot = 1;
    state->turbo_multiplier = 2;
}

void gba_hud_show_toast(GBAHUDState* state, const char* msg, SDL_Color color, uint32_t duration_ms) {
    if (!state || !msg) return;
    strncpy(state->toast_msg, msg, sizeof(state->toast_msg) - 1);
    state->toast_msg[sizeof(state->toast_msg) - 1] = '\0';
    state->toast_color = color;
    state->toast_until_ms = SDL_GetTicks() + duration_ms;
}

void gba_hud_draw(SDL_Renderer* renderer, int window_w, int window_h, const GBAHUDState* state) {
    if (!state) return;

    SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);

    /* 1. Top Status Bar */
    if (state->show_hud) {
        SDL_SetRenderDrawColor(renderer, 24, 24, 37, 220); /* Catppuccin Mantle */
        SDL_Rect bar = { 10, 10, window_w - 20, 28 };
        SDL_RenderFillRect(renderer, &bar);

        /* Border */
        SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255); /* Catppuccin Surface0 */
        SDL_RenderDrawRect(renderer, &bar);

        /* Mode Dot */
        SDL_Rect dot = { 20, 18, 12, 12 };
        char buf[128] = {0};

        if (state->net_mode == GBA_NET_SINGLE_PLAYER) {
            SDL_SetRenderDrawColor(renderer, 137, 180, 250, 255); /* Sapphire Blue */
            SDL_RenderFillRect(renderer, &dot);
            snprintf(buf, sizeof(buf), "SINGLE PLAYER  [ESC: MENU]");
        } else if (state->net_mode == GBA_NET_HOSTING) {
            SDL_SetRenderDrawColor(renderer, 249, 226, 175, 255); /* Amber Yellow */
            SDL_RenderFillRect(renderer, &dot);
            snprintf(buf, sizeof(buf), "HOSTING (PORT 8765) - WAITING FOR PEER");
        } else if (state->net_mode == GBA_NET_CONNECTED) {
            SDL_SetRenderDrawColor(renderer, 166, 227, 161, 255); /* Bright Green */
            SDL_RenderFillRect(renderer, &dot);
            snprintf(buf, sizeof(buf), "ONLINE P%d/%d (%s)", state->player_id + 1, state->total_players, state->remote_ip);
        }

        SDL_Color text_col = { 205, 214, 244, 255 }; /* Catppuccin Text */
        draw_string(renderer, buf, 38, 17, 2, text_col);

        /* FPS on Top-Right */
        if (state->net_mode == GBA_NET_CONNECTED) {
            snprintf(buf, sizeof(buf), "%u ms | %.0f FPS", state->ping_ms, state->current_fps);
        } else {
            snprintf(buf, sizeof(buf), "%.0f FPS", state->current_fps);
        }
        int info_w = (int)strlen(buf) * 16;
        draw_string(renderer, buf, window_w - 25 - info_w, 17, 2, (SDL_Color){ 166, 173, 200, 255 });

        /* Turbo Badge (Bottom-Right) */
        if (state->is_turbo) {
            int box_w = state->turbo_is_toggle ? 240 : 180;
            SDL_Rect turbo_box = { window_w - box_w - 12, window_h - 44, box_w, 32 };
            SDL_SetRenderDrawColor(renderer, 250, 179, 135, 230); /* Catppuccin Peach */
            SDL_RenderFillRect(renderer, &turbo_box);

            SDL_SetRenderDrawColor(renderer, 249, 226, 175, 255); /* Catppuccin Yellow */
            SDL_RenderDrawRect(renderer, &turbo_box);

            if (state->turbo_is_toggle) {
                snprintf(buf, sizeof(buf), "TURBO %dx [TOGGLE]", state->turbo_multiplier);
            } else {
                snprintf(buf, sizeof(buf), "TURBO %dx [HOLD]", state->turbo_multiplier);
            }
            draw_string(renderer, buf, window_w - box_w + 4, window_h - 36, 2, (SDL_Color){ 17, 17, 27, 255 });
        }

        /* Bottom Hints (Left) */
        draw_string(renderer, "[1-9] Save  [F1-F9] Load  [T] Turbo Toggle  [Tab] Hold  [C/V] Spam  [ESC] Menu",
                    14, window_h - 22, 1, (SDL_Color){ 166, 173, 200, 220 });
    }

    /* 2. Floating Toast Notification (Centered) */
    uint32_t now = SDL_GetTicks();
    if (now < state->toast_until_ms && state->toast_msg[0] != '\0') {
        int toast_len = (int)strlen(state->toast_msg);
        int toast_w = toast_len * 16 + 32;
        int toast_h = 36;
        int toast_x = (window_w - toast_w) / 2;
        int toast_y = 48;

        SDL_Rect toast_bg = { toast_x, toast_y, toast_w, toast_h };
        SDL_SetRenderDrawColor(renderer, 17, 17, 27, 240); /* Catppuccin Crust */
        SDL_RenderFillRect(renderer, &toast_bg);

        SDL_SetRenderDrawColor(renderer, state->toast_color.r, state->toast_color.g, state->toast_color.b, 255);
        SDL_RenderDrawRect(renderer, &toast_bg);

        draw_string(renderer, state->toast_msg, toast_x + 16, toast_y + 10, 2, state->toast_color);
    }

    /* 3. In-Game Pause Menu Overlay */
    if (state->menu_open) {
        /* Fullscreen dim */
        SDL_SetRenderDrawColor(renderer, 17, 17, 27, 195);
        SDL_Rect dim = { 0, 0, window_w, window_h };
        SDL_RenderFillRect(renderer, &dim);

        /* Centered Menu Card */
        int menu_w = 560;
        int menu_h = 320;
        int menu_x = (window_w - menu_w) / 2;
        int menu_y = (window_h - menu_h) / 2;

        SDL_Rect card = { menu_x, menu_y, menu_w, menu_h };
        SDL_SetRenderDrawColor(renderer, 30, 30, 46, 250); /* Catppuccin Base */
        SDL_RenderFillRect(renderer, &card);

        SDL_SetRenderDrawColor(renderer, 148, 226, 213, 255); /* Catppuccin Teal border */
        SDL_RenderDrawRect(renderer, &card);

        /* Title */
        const char* title = "=== GBA CROSSPLAY MENU ===";
        int title_w = (int)strlen(title) * 16;
        draw_string(renderer, title, menu_x + (menu_w - title_w) / 2, menu_y + 16, 2, (SDL_Color){ 203, 166, 247, 255 }); /* Mauve */

        /* Divider */
        SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255);
        SDL_RenderDrawLine(renderer, menu_x + 20, menu_y + 44, menu_x + menu_w - 20, menu_y + 44);

        /* Menu Items */
        const char* labels[MENU_COUNT];
        char slot_save_buf[64];
        char slot_load_buf[64];
        char mp_buf[64];
        char turbo_buf[64];
        char hud_buf[64];

        snprintf(slot_save_buf, sizeof(slot_save_buf), "Save State:   < Slot %d >  (Enter: Save)", state->selected_slot);
        snprintf(slot_load_buf, sizeof(slot_load_buf), "Load State:   < Slot %d >  (Enter: Load)", state->selected_slot);

        if (state->net_mode == GBA_NET_SINGLE_PLAYER) {
            if (state->mp_action_mode == 0) {
                snprintf(mp_buf, sizeof(mp_buf), "Multiplayer:  < Host Server (Port 8765) >");
            } else {
                snprintf(mp_buf, sizeof(mp_buf), "Multiplayer:  < Connect to Remote IP >");
            }
        } else if (state->net_mode == GBA_NET_HOSTING) {
            snprintf(mp_buf, sizeof(mp_buf), "Multiplayer:  < Disconnect (Stop Hosting) >");
        } else {
            snprintf(mp_buf, sizeof(mp_buf), "Multiplayer:  < Disconnect (Leave Session) >");
        }

        snprintf(turbo_buf, sizeof(turbo_buf), "Turbo Speed:  < %dx >", state->turbo_multiplier);
        snprintf(hud_buf, sizeof(hud_buf), "HUD Overlay:  < %s >", state->show_hud ? "ON" : "OFF");

        labels[MENU_RESUME] = "Resume Game";
        labels[MENU_SAVE_STATE] = slot_save_buf;
        labels[MENU_LOAD_STATE] = slot_load_buf;
        labels[MENU_MULTIPLAYER] = mp_buf;
        labels[MENU_TURBO_SPEED] = turbo_buf;
        labels[MENU_TOGGLE_HUD] = hud_buf;
        labels[MENU_QUIT] = "Quit Emulator";

        int start_y = menu_y + 60;
        int line_h = 32;

        for (int i = 0; i < MENU_COUNT; i++) {
            bool is_sel = (i == state->menu_selected);
            int item_y = start_y + i * line_h;

            if (is_sel) {
                SDL_Rect sel_bg = { menu_x + 16, item_y - 4, menu_w - 32, 26 };
                SDL_SetRenderDrawColor(renderer, 49, 50, 68, 255); /* Surface0 */
                SDL_RenderFillRect(renderer, &sel_bg);

                SDL_SetRenderDrawColor(renderer, 148, 226, 213, 255); /* Teal indicator */
                SDL_Rect ind = { menu_x + 18, item_y - 2, 4, 22 };
                SDL_RenderFillRect(renderer, &ind);

                char row[128];
                snprintf(row, sizeof(row), "> %s", labels[i]);
                draw_string(renderer, row, menu_x + 30, item_y, 2, (SDL_Color){ 148, 226, 213, 255 });
            } else {
                char row[128];
                snprintf(row, sizeof(row), "  %s", labels[i]);
                draw_string(renderer, row, menu_x + 30, item_y, 2, (SDL_Color){ 205, 214, 244, 200 });
            }
        }

        /* Bottom Controls help */
        SDL_RenderDrawLine(renderer, menu_x + 20, menu_y + menu_h - 36, menu_x + menu_w - 20, menu_y + menu_h - 36);
        const char* hint = "[UP/DOWN] Select  [LEFT/RIGHT] Adjust  [ENTER] Apply  [ESC] Close";
        int hint_w = (int)strlen(hint) * 8;
        draw_string(renderer, hint, menu_x + (menu_w - hint_w) / 2, menu_y + menu_h - 24, 1, (SDL_Color){ 166, 173, 200, 255 });
    }
}
