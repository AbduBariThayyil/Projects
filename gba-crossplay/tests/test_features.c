#include "../linux/include/emulator.h"
#include "../linux/include/hud.h"
#include "../core/link_protocol.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>

static void create_test_rom(const char* path) {
    FILE* f = fopen(path, "wb");
    assert(f != NULL);

    uint8_t header[0x200] = {0};
    /* ARM infinite loop: b . (0xEAFFFFFE) */
    header[0] = 0xFE; header[1] = 0xFF; header[2] = 0xFF; header[3] = 0xEA;

    static const uint8_t nintendo_logo[] = {
        0x24, 0xFF, 0xAE, 0x51, 0x69, 0x9A, 0xA2, 0x21, 0x3D, 0x84, 0x82, 0x0A, 0x84, 0xE4, 0x09, 0xAD,
        0x11, 0x24, 0x8B, 0x98, 0xC0, 0x81, 0x7F, 0x21, 0xA3, 0x52, 0xBE, 0x19, 0x93, 0x09, 0xCE, 0x20,
        0x10, 0x46, 0x4A, 0x4A, 0xF8, 0x27, 0x31, 0xEC, 0x58, 0xC7, 0xE8, 0x33, 0x82, 0xE3, 0xCE, 0xBF,
        0x85, 0xF4, 0xDF, 0x94, 0xCE, 0x4B, 0x09, 0x2B, 0x94, 0x58, 0xD4, 0x8E, 0x83, 0x66, 0x4A, 0x23
    };
    for (size_t i = 0; i < sizeof(nintendo_logo); i++) {
        header[0x04 + i] = nintendo_logo[i];
    }
    snprintf((char*)&header[0xA0], 12, "FEATTEST");
    header[0xB2] = 0x96;

    uint8_t chk = 0;
    for (int i = 0xA0; i <= 0xBC; i++) {
        chk = chk - header[i];
    }
    chk -= 0x19;
    header[0xBD] = chk;

    fwrite(header, 1, sizeof(header), f);
    fclose(f);
}

int main() {
    const char* rom_path = "/tmp/test_features.gba";
    create_test_rom(rom_path);

    printf("[TEST] Creating emulator instance in Single Player...\n");
    GBAEmulator* emu = gba_emulator_create(rom_path, 0, -1);
    assert(emu != NULL);
    assert(strcmp(gba_emulator_get_title(emu), "FEATTEST") == 0);
    assert(gba_emulator_get_socket(emu) == -1);

    printf("[TEST] Stepping 10 frames of valid ARM infinite loop...\n");
    for (int i = 0; i < 10; i++) {
        gba_emulator_step_frame(emu);
    }

    printf("[TEST] Testing savestates slots 1-9...\n");
    for (int slot = 1; slot <= 9; slot++) {
        bool saved = gba_emulator_save_state(emu, slot);
        assert(saved && "Save state must succeed for all slots 1-9");
        bool has = gba_emulator_has_state(emu, slot);
        assert(has && "State existence check must return true");
    }

    printf("[TEST] Testing loadstates slots 1-9...\n");
    for (int slot = 1; slot <= 9; slot++) {
        bool loaded = gba_emulator_load_state(emu, slot);
        assert(loaded && "Load state must succeed for all slots 1-9");
    }

    printf("[TEST] Testing dynamic network mode switching...\n");
    int sv[2];
    assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0);

    gba_emulator_set_network(emu, sv[0], 1);
    assert(gba_emulator_get_socket(emu) == sv[0]);

    gba_emulator_disconnect_network(emu);
    assert(gba_emulator_get_socket(emu) == -1);
    close(sv[1]);

    printf("[TEST] Testing HUD state init & toast...\n");
    GBAHUDState hud;
    gba_hud_init(&hud);
    assert(hud.net_mode == GBA_NET_SINGLE_PLAYER);
    assert(hud.selected_slot == 1);
    assert(hud.show_hud == true);

    gba_hud_show_toast(&hud, "[SAVED STATE SLOT 1]", (SDL_Color){166, 227, 161, 255}, 2000);
    assert(strcmp(hud.toast_msg, "[SAVED STATE SLOT 1]") == 0);

    gba_emulator_destroy(emu);
    printf("[TEST] All savestate, loadstate, network, and HUD tests passed!\n");

    /* Cleanup temporary files */
    unlink(rom_path);
    for (int s = 1; s <= 9; s++) {
        char ss_file[128];
        snprintf(ss_file, sizeof(ss_file), "%s.ss%d", rom_path, s);
        unlink(ss_file);
    }

    return 0;
}
