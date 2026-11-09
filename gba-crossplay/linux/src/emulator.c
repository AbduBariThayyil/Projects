#include "audio.h"
#include "emulator.h"
#include "../../core/link_protocol.h"
#include "../../core/turbo_sync.h"

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/input.h>
#include <mgba/internal/gba/io.h>
#include <mgba/internal/gba/sio.h>
#include <mgba/internal/gba/memory.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <fcntl.h>

struct CustomSIODriver {
    struct GBASIODriver d;
    struct GBAEmulator* emu;
};

struct GBAEmulator {
    struct mCore* core;
    struct GBA* gba;
    struct CustomSIODriver sio_driver;
    struct mAVStream av_stream;

    uint32_t video_buffer[GBA_VIDEO_WIDTH * GBA_VIDEO_HEIGHT];
    uint8_t player_id;
    int socket_fd;

    uint16_t local_send_data;
    uint32_t transfer_counter;

    GBATurboCoordinator turbo;
    char title[16];
    uint32_t crc32;
};

static void av_post_audio_frame(struct mAVStream* stream, int16_t left, int16_t right) {
    (void)stream;
    int16_t samples[2] = { left, right };
    gba_audio_feed(samples, 1, false);
}

static uint16_t sio_write_register(struct GBASIODriver* driver, uint32_t address, uint16_t value) {
    struct CustomSIODriver* custom = (struct CustomSIODriver*)driver;
    if (!custom || !custom->emu) return value;
    GBAEmulator* emu = custom->emu;
    if (!emu || !emu->gba) return value;

    if (address == REG_SIOMLT_SEND) {
        emu->local_send_data = value;
        return value;
    }

    if (address == REG_SIOCNT) {
        /* Check Start bit (Bit 7 = 0x80) */
        if ((value & 0x80) && emu->socket_fd >= 0) {
            if (emu->player_id == 0) {
                /* Master: Send multi packet to Client */
                GBAPacketSIOMulti pkt;
                memset(&pkt, 0, sizeof(pkt));
                pkt.transfer_id = ++emu->transfer_counter;
                pkt.data[0] = emu->local_send_data;
                pkt.siocnt = value;

                gba_link_send_packet(emu->socket_fd, PKT_SIO_MULTI, 0, &pkt, sizeof(pkt));

                /* Receive Client's reply */
                GBALinkHeader reply_hdr;
                if (gba_link_recv_header(emu->socket_fd, &reply_hdr) > 0) {
                    if (reply_hdr.type == PKT_SIO_MULTI) {
                        GBAPacketSIOMulti client_pkt;
                        if (gba_link_recv_payload(emu->socket_fd, &reply_hdr, &client_pkt, sizeof(client_pkt)) > 0) {
                            pkt.data[1] = client_pkt.data[1];
                        }
                    }
                }

                /* Populate received data in GBA IO memory */
                emu->gba->memory.io[REG_SIOMULTI0 >> 1] = pkt.data[0];
                emu->gba->memory.io[REG_SIOMULTI1 >> 1] = pkt.data[1];
                emu->gba->memory.io[REG_SIOMULTI2 >> 1] = 0xFFFF;
                emu->gba->memory.io[REG_SIOMULTI3 >> 1] = 0xFFFF;

                /* Clear Start bit, Clear Error bit */
                value &= ~0x00C0;

                /* Raise SIO IRQ if enabled */
                if (value & 0x4000) {
                    GBARaiseIRQ(emu->gba, GBA_IRQ_SIO, 0);
                }
            }
        }
        return value;
    }

    return value;
}

static void on_turbo_changed_cb(bool active, uint8_t multiplier, void* userdata) {
    GBAEmulator* emu = (GBAEmulator*)userdata;
    if (!emu || emu->socket_fd < 0) return;

    GBAPacketTurbo pkt;
    pkt.is_turbo = active ? 1 : 0;
    pkt.multiplier = multiplier;
    pkt.sender_id = emu->player_id;

    gba_link_send_packet(emu->socket_fd, PKT_TURBO_STATE, emu->player_id, &pkt, sizeof(pkt));
}

GBAEmulator* gba_emulator_create(const char* rom_path, uint8_t player_id, int socket_fd) {
    if (!rom_path) return NULL;

    GBAEmulator* emu = (GBAEmulator*)calloc(1, sizeof(GBAEmulator));
    if (!emu) return NULL;

    emu->player_id = player_id;
    emu->socket_fd = socket_fd;
    gba_turbo_init(&emu->turbo, player_id, 2);
    gba_turbo_set_callback(&emu->turbo, on_turbo_changed_cb, emu);

    emu->core = mCoreFind(rom_path);
    if (!emu->core) {
        fprintf(stderr, "Failed to load mGBA core for: %s\n", rom_path);
        free(emu);
        return NULL;
    }

    mCoreInitConfig(emu->core, "mgba");
    if (!emu->core->init(emu->core)) {
        fprintf(stderr, "Failed to init core\n");
        emu->core->deinit(emu->core);
        free(emu);
        return NULL;
    }

    if (!mCoreLoadFile(emu->core, rom_path)) {
        fprintf(stderr, "Failed to load ROM file: %s\n", rom_path);
        emu->core->deinit(emu->core);
        free(emu);
        return NULL;
    }

    mCoreAutoloadSave(emu->core);
    emu->core->reset(emu->core);

    emu->core->setVideoBuffer(emu->core, (color_t*)emu->video_buffer, GBA_VIDEO_WIDTH);

    /* Setup Audio */
    memset(&emu->av_stream, 0, sizeof(emu->av_stream));
    emu->av_stream.postAudioFrame = av_post_audio_frame;
    emu->core->setAVStream(emu->core, &emu->av_stream);

    /* Attach SIO Driver to GBA board */
    emu->gba = (struct GBA*)emu->core->board;
    if (emu->gba) {
        memset(&emu->sio_driver, 0, sizeof(emu->sio_driver));
        emu->sio_driver.emu = emu;
        emu->sio_driver.d.writeRegister = sio_write_register;
        GBASIOSetDriver(&emu->gba->sio, &emu->sio_driver.d, SIO_MULTI);
    }

    /* Extract Title */
    emu->core->getGameTitle(emu->core, emu->title);

    return emu;
}

void gba_emulator_destroy(GBAEmulator* emu) {
    if (!emu) return;

    if (emu->gba) {
        GBASIOSetDriver(&emu->gba->sio, NULL, SIO_MULTI);
    }

    if (emu->core) {
        mCoreSaveState(emu->core, 0, 0);
        emu->core->unloadROM(emu->core);
        emu->core->deinit(emu->core);
    }
    free(emu);
}

void gba_emulator_step_frame(GBAEmulator* emu) {
    if (!emu || !emu->core) return;

    gba_emulator_process_network(emu);
    emu->core->runFrame(emu->core);
}

void gba_emulator_set_keys(GBAEmulator* emu, uint32_t keys_bitmask) {
    if (!emu || !emu->core) return;
    emu->core->setKeys(emu->core, keys_bitmask);
}

const uint32_t* gba_emulator_get_pixels(const GBAEmulator* emu) {
    return emu ? emu->video_buffer : NULL;
}

void gba_emulator_process_network(GBAEmulator* emu) {
    if (!emu || emu->socket_fd < 0) return;

    /* Non-blocking read for incoming packets */
    int flags = fcntl(emu->socket_fd, F_GETFL, 0);
    fcntl(emu->socket_fd, F_SETFL, flags | O_NONBLOCK);

    GBALinkHeader hdr;
    while (gba_link_recv_header(emu->socket_fd, &hdr) > 0) {
        if (hdr.type == PKT_TURBO_STATE) {
            GBAPacketTurbo turbo_pkt;
            if (gba_link_recv_payload(emu->socket_fd, &hdr, &turbo_pkt, sizeof(turbo_pkt)) > 0) {
                gba_turbo_set_remote(&emu->turbo, hdr.player_id, turbo_pkt.is_turbo == 1);
            }
        } else if (hdr.type == PKT_SIO_MULTI && emu->player_id != 0) {
            /* Slave: Received multi transfer from Master */
            GBAPacketSIOMulti multi_pkt;
            if (gba_link_recv_payload(emu->socket_fd, &hdr, &multi_pkt, sizeof(multi_pkt)) > 0) {
                /* Reply with our data */
                GBAPacketSIOMulti reply;
                memset(&reply, 0, sizeof(reply));
                reply.transfer_id = multi_pkt.transfer_id;
                reply.data[emu->player_id] = emu->local_send_data;
                gba_link_send_packet(emu->socket_fd, PKT_SIO_MULTI, emu->player_id, &reply, sizeof(reply));

                /* Update our IO memory */
                if (emu->gba) {
                    emu->gba->memory.io[REG_SIOMULTI0 >> 1] = multi_pkt.data[0];
                    emu->gba->memory.io[REG_SIOMULTI1 >> 1] = emu->local_send_data;
                    emu->gba->memory.io[REG_SIOMULTI2 >> 1] = 0xFFFF;
                    emu->gba->memory.io[REG_SIOMULTI3 >> 1] = 0xFFFF;

                    /* Complete transfer */
                    emu->gba->memory.io[REG_SIOCNT >> 1] &= ~0x00C0;

                    if (emu->gba->memory.io[REG_SIOCNT >> 1] & 0x4000) {
                        GBARaiseIRQ(emu->gba, GBA_IRQ_SIO, 0);
                    }
                }
            }
        } else {
            /* Drain unhandled packet */
            char sink[256];
            gba_link_recv_payload(emu->socket_fd, &hdr, sink, sizeof(sink));
        }
    }

    fcntl(emu->socket_fd, F_SETFL, flags);
}

GBATurboCoordinator* gba_emulator_get_turbo(GBAEmulator* emu) {
    return emu ? &emu->turbo : NULL;
}

const char* gba_emulator_get_title(const GBAEmulator* emu) {
    return emu ? emu->title : "Unknown";
}

uint32_t gba_emulator_get_crc32(const GBAEmulator* emu) {
    return emu ? emu->crc32 : 0;
}
