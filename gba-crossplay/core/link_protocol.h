#ifndef GBA_LINK_PROTOCOL_H
#define GBA_LINK_PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GBA_LINK_MAGIC          0x4C414247 /* "GBAL" in Little Endian */
#define GBA_LINK_DEFAULT_PORT   52841
#define GBA_DISCOVERY_PORT      52840
#define GBA_MAX_PLAYERS         4

/* Protocol Packet Types */
typedef enum {
    PKT_HEARTBEAT    = 0x00,
    PKT_HANDSHAKE    = 0x01,
    PKT_WELCOME      = 0x02,
    PKT_SIO_MULTI    = 0x10,
    PKT_SIO_NORMAL   = 0x11,
    PKT_TURBO_STATE  = 0x20,
    PKT_PING         = 0x30,
    PKT_PONG         = 0x31,
    PKT_DISCONNECT   = 0xFF
} GBALinkPacketType;

/* Packet Header (Fixed 8 Bytes) */
#pragma pack(push, 1)
typedef struct {
    uint32_t magic;      /* GBA_LINK_MAGIC */
    uint8_t  type;       /* GBALinkPacketType */
    uint8_t  player_id;  /* 0 = Host (Master), 1..3 = Slaves */
    uint16_t length;     /* Payload byte length */
} GBALinkHeader;

/* PKT_HANDSHAKE Payload */
typedef struct {
    uint32_t rom_crc32;
    char     game_title[16];
    uint8_t  requested_slot;
    uint8_t  protocol_version;
} GBAPacketHandshake;

/* PKT_WELCOME Payload */
typedef struct {
    uint8_t  assigned_id;
    uint8_t  total_players;
    uint8_t  turbo_multiplier; /* Default e.g. 2 or 3 */
    uint8_t  flags;
    char     host_name[32];
} GBAPacketWelcome;

/* PKT_SIO_MULTI Payload (16-bit multiplayer transfer) */
typedef struct {
    uint32_t transfer_id;
    uint16_t data[GBA_MAX_PLAYERS]; /* 16-bit word per player */
    uint16_t siocnt;
    uint8_t  ready_mask;
} GBAPacketSIOMulti;

/* PKT_SIO_NORMAL Payload (32-bit normal transfer) */
typedef struct {
    uint32_t transfer_id;
    uint32_t data;
    uint16_t siocnt;
} GBAPacketSIONormal;

/* PKT_TURBO_STATE Payload */
typedef struct {
    uint8_t is_turbo;        /* 1 = active, 0 = inactive */
    uint8_t multiplier;      /* e.g. 2 (120 FPS), 3 (180 FPS) */
    uint8_t sender_id;
} GBAPacketTurbo;

/* PKT_PING / PKT_PONG Payload */
typedef struct {
    uint64_t timestamp_us;
} GBAPacketPingPong;
#pragma pack(pop)

/* Helper Functions */
void gba_link_header_init(GBALinkHeader* hdr, GBALinkPacketType type, uint8_t player_id, uint16_t payload_len);
bool gba_link_header_validate(const GBALinkHeader* hdr);

int gba_link_send_packet(int socket_fd, GBALinkPacketType type, uint8_t player_id, const void* payload, uint16_t len);
int gba_link_recv_header(int socket_fd, GBALinkHeader* hdr);
int gba_link_recv_payload(int socket_fd, const GBALinkHeader* hdr, void* buffer, size_t max_buf_len);

#ifdef __cplusplus
}
#endif

#endif /* GBA_LINK_PROTOCOL_H */
