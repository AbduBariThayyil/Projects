#ifndef GBA_CROSSPLAY_EMULATOR_H
#define GBA_CROSSPLAY_EMULATOR_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "../../core/link_protocol.h"
#include "../../core/turbo_sync.h"

#ifdef __cplusplus
extern "C" {
#endif

#define GBA_VIDEO_WIDTH  240
#define GBA_VIDEO_HEIGHT 160

typedef struct GBAEmulator GBAEmulator;

/* Creates emulator instance for given ROM */
GBAEmulator* gba_emulator_create(const char* rom_path, uint8_t player_id, int socket_fd);
void gba_emulator_destroy(GBAEmulator* emu);

/* Steps one frame */
void gba_emulator_step_frame(GBAEmulator* emu);

/* Input updates */
void gba_emulator_set_keys(GBAEmulator* emu, uint32_t keys_bitmask);

/* Video framebuffer access (240x160 RGBA32) */
const uint32_t* gba_emulator_get_pixels(const GBAEmulator* emu);

/* Network poll / processing */
void gba_emulator_process_network(GBAEmulator* emu);

/* Turbo access */
GBATurboCoordinator* gba_emulator_get_turbo(GBAEmulator* emu);

/* Returns game title */
const char* gba_emulator_get_title(const GBAEmulator* emu);

/* ROM CRC32 */
uint32_t gba_emulator_get_crc32(const GBAEmulator* emu);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_EMULATOR_H */
