#ifndef GBA_CROSSPLAY_DISCOVERY_H
#define GBA_CROSSPLAY_DISCOVERY_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    char ip[64];
    uint16_t port;
    char hostname[64];
    char game_title[32];
    uint64_t last_seen_ms;
} GBADiscoveredHost;

/* Starts background UDP broadcast beacon advertising host */
int gba_discovery_start_beacon(const char* game_title, uint16_t tcp_port);
void gba_discovery_stop_beacon(void);

/* Scans for available hosts on local Wi-Fi / LAN */
int gba_discovery_scan(GBADiscoveredHost* out_hosts, int max_hosts, int timeout_ms);

#ifdef __cplusplus
}
#endif

#endif /* GBA_CROSSPLAY_DISCOVERY_H */
