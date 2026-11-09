#include "config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static char g_config_path[512] = {0};

const char* gba_config_get_default_path(void) {
    if (g_config_path[0] == '\0') {
        const char* home = getenv("HOME");
        if (!home) home = "/tmp";
        snprintf(g_config_path, sizeof(g_config_path), "%s/.config/gba-crossplay/config.ini", home);
    }
    return g_config_path;
}

void gba_config_load_defaults(GBAConfig* cfg) {
    if (!cfg) return;
    memset(cfg, 0, sizeof(*cfg));

    /* Keyboard Defaults */
    cfg->key_a = SDLK_x;
    cfg->key_b = SDLK_z;
    cfg->key_l = SDLK_a;
    cfg->key_r = SDLK_s;
    cfg->key_start = SDLK_RETURN;
    cfg->key_select = SDLK_BACKSPACE;
    cfg->key_up = SDLK_UP;
    cfg->key_down = SDLK_DOWN;
    cfg->key_left = SDLK_LEFT;
    cfg->key_right = SDLK_RIGHT;
    cfg->key_turbo_hold = SDLK_TAB;
    cfg->key_turbo_toggle = SDLK_t;
    cfg->key_spam_a = SDLK_c;
    cfg->key_spam_b = SDLK_v;
    cfg->key_hud = SDLK_F12;

    /* Gamepad Defaults */
    cfg->pad_a = SDL_CONTROLLER_BUTTON_A;
    cfg->pad_b = SDL_CONTROLLER_BUTTON_B;
    cfg->pad_l = SDL_CONTROLLER_BUTTON_LEFTSHOULDER;
    cfg->pad_r = SDL_CONTROLLER_BUTTON_RIGHTSHOULDER;
    cfg->pad_start = SDL_CONTROLLER_BUTTON_START;
    cfg->pad_select = SDL_CONTROLLER_BUTTON_BACK;
    cfg->pad_turbo_hold = SDL_CONTROLLER_BUTTON_MISC1; // Or trigger
    cfg->pad_turbo_toggle = SDL_CONTROLLER_BUTTON_RIGHTSTICK;
    cfg->pad_spam_a = SDL_CONTROLLER_BUTTON_X;
    cfg->pad_spam_b = SDL_CONTROLLER_BUTTON_Y;

    cfg->turbo_multiplier = 2;
    cfg->dark_mode = true;
}

bool gba_config_save_file(const GBAConfig* cfg, const char* path) {
    if (!cfg || !path) return false;

    // Ensure directory exists
    char dir[512];
    snprintf(dir, sizeof(dir), "%s", path);
    char* last_slash = strrchr(dir, '/');
    if (last_slash) {
        *last_slash = '\0';
        char cmd[600];
        snprintf(cmd, sizeof(cmd), "mkdir -p '%s'", dir);
        system(cmd);
    }

    FILE* fp = fopen(path, "w");
    if (!fp) return false;

    fprintf(fp, "# GBA Crossplay Configuration\n");
    fprintf(fp, "# Modify key bindings using SDL Key names (e.g. x, z, a, s, return, backspace, tab, t, c, v, f1, space)\n\n");
    fprintf(fp, "[Keyboard]\n");
    fprintf(fp, "key_a=%s\n", SDL_GetKeyName(cfg->key_a));
    fprintf(fp, "key_b=%s\n", SDL_GetKeyName(cfg->key_b));
    fprintf(fp, "key_l=%s\n", SDL_GetKeyName(cfg->key_l));
    fprintf(fp, "key_r=%s\n", SDL_GetKeyName(cfg->key_r));
    fprintf(fp, "key_start=%s\n", SDL_GetKeyName(cfg->key_start));
    fprintf(fp, "key_select=%s\n", SDL_GetKeyName(cfg->key_select));
    fprintf(fp, "key_up=%s\n", SDL_GetKeyName(cfg->key_up));
    fprintf(fp, "key_down=%s\n", SDL_GetKeyName(cfg->key_down));
    fprintf(fp, "key_left=%s\n", SDL_GetKeyName(cfg->key_left));
    fprintf(fp, "key_right=%s\n", SDL_GetKeyName(cfg->key_right));
    fprintf(fp, "key_turbo_hold=%s\n", SDL_GetKeyName(cfg->key_turbo_hold));
    fprintf(fp, "key_turbo_toggle=%s\n", SDL_GetKeyName(cfg->key_turbo_toggle));
    fprintf(fp, "key_spam_a=%s\n", SDL_GetKeyName(cfg->key_spam_a));
    fprintf(fp, "key_spam_b=%s\n", SDL_GetKeyName(cfg->key_spam_b));
    fprintf(fp, "key_hud=%s\n\n", SDL_GetKeyName(cfg->key_hud));

    fprintf(fp, "[Settings]\n");
    fprintf(fp, "turbo_multiplier=%u\n", cfg->turbo_multiplier);
    fprintf(fp, "dark_mode=%s\n", cfg->dark_mode ? "true" : "false");

    fclose(fp);
    return true;
}

bool gba_config_load_file(GBAConfig* cfg, const char* path) {
    if (!cfg || !path) return false;

    gba_config_load_defaults(cfg);

    FILE* fp = fopen(path, "r");
    if (!fp) {
        /* File doesn't exist yet, save defaults */
        gba_config_save_file(cfg, path);
        return true;
    }

    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        char* eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char* key = line;
        char* val = eq + 1;

        // Trim leading/trailing whitespace
        while (*key == ' ' || *key == '\t') key++;
        char* end = key + strlen(key) - 1;
        while (end > key && (*end == ' ' || *end == '\t')) *end-- = '\0';

        while (*val == ' ' || *val == '\t') val++;
        end = val + strlen(val) - 1;
        while (end >= val && (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n')) *end-- = '\0';

        if (strcmp(key, "key_a") == 0) cfg->key_a = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_b") == 0) cfg->key_b = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_l") == 0) cfg->key_l = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_r") == 0) cfg->key_r = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_start") == 0) cfg->key_start = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_select") == 0) cfg->key_select = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_up") == 0) cfg->key_up = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_down") == 0) cfg->key_down = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_left") == 0) cfg->key_left = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_right") == 0) cfg->key_right = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_turbo_hold") == 0) cfg->key_turbo_hold = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_turbo_toggle") == 0) cfg->key_turbo_toggle = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_spam_a") == 0) cfg->key_spam_a = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_spam_b") == 0) cfg->key_spam_b = SDL_GetKeyFromName(val);
        else if (strcmp(key, "key_hud") == 0) cfg->key_hud = SDL_GetKeyFromName(val);
        else if (strcmp(key, "turbo_multiplier") == 0) cfg->turbo_multiplier = (uint8_t)atoi(val);
        else if (strcmp(key, "dark_mode") == 0) cfg->dark_mode = (strcmp(val, "true") == 0 || strcmp(val, "1") == 0);
    }

    fclose(fp);
    return true;
}
