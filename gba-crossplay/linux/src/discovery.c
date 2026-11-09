#include "discovery.h"
#include "../../core/link_protocol.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/time.h>

static pthread_t g_beacon_thread;
static volatile bool g_beacon_running = false;
static char g_beacon_title[32];
static uint16_t g_beacon_port = GBA_LINK_DEFAULT_PORT;

static uint64_t current_time_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)(tv.tv_sec * 1000 + tv.tv_usec / 1000);
}

static void* beacon_worker(void* arg) {
    (void)arg;
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return NULL;

    int broadcast_enable = 1;
    setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &broadcast_enable, sizeof(broadcast_enable));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(GBA_DISCOVERY_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);

    char hostname[64] = "ArchLinux";
    gethostname(hostname, sizeof(hostname) - 1);

    char msg[128];
    snprintf(msg, sizeof(msg), "GBALINK:HOST:%s:%s:%u", hostname, g_beacon_title, g_beacon_port);

    while (g_beacon_running) {
        sendto(fd, msg, strlen(msg), 0, (struct sockaddr*)&addr, sizeof(addr));
        usleep(1000000); /* 1 second */
    }

    close(fd);
    return NULL;
}

int gba_discovery_start_beacon(const char* game_title, uint16_t tcp_port) {
    if (g_beacon_running) return 0;

    strncpy(g_beacon_title, game_title ? game_title : "GBA", sizeof(g_beacon_title) - 1);
    g_beacon_port = tcp_port ? tcp_port : GBA_LINK_DEFAULT_PORT;
    g_beacon_running = true;

    if (pthread_create(&g_beacon_thread, NULL, beacon_worker, NULL) != 0) {
        g_beacon_running = false;
        return -1;
    }
    return 0;
}

void gba_discovery_stop_beacon(void) {
    if (!g_beacon_running) return;
    g_beacon_running = false;
    pthread_join(g_beacon_thread, NULL);
}

int gba_discovery_scan(GBADiscoveredHost* out_hosts, int max_hosts, int timeout_ms) {
    if (!out_hosts || max_hosts <= 0) return 0;

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return 0;

    int reuse = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
#ifdef SO_REUSEPORT
    setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &reuse, sizeof(reuse));
#endif

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(GBA_DISCOVERY_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(fd);
        return 0;
    }

    struct timeval tv;
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    int count = 0;
    uint64_t start_ms = current_time_ms();

    while (current_time_ms() - start_ms < (uint64_t)timeout_ms && count < max_hosts) {
        char buf[256];
        struct sockaddr_in sender;
        socklen_t sender_len = sizeof(sender);

        ssize_t n = recvfrom(fd, buf, sizeof(buf) - 1, 0, (struct sockaddr*)&sender, &sender_len);
        if (n <= 0) break;
        buf[n] = '\0';

        /* Parse "GBALINK:HOST:<hostname>:<game_title>:<tcp_port>" */
        if (strncmp(buf, "GBALINK:HOST:", 13) == 0) {
            char* token = strtok(buf + 13, ":");
            if (!token) continue;
            char host[64];
            strncpy(host, token, sizeof(host) - 1);

            token = strtok(NULL, ":");
            if (!token) continue;
            char title[32];
            strncpy(title, token, sizeof(title) - 1);

            token = strtok(NULL, ":");
            if (!token) continue;
            uint16_t port = (uint16_t)atoi(token);

            char sender_ip[64];
            inet_ntop(AF_INET, &sender.sin_addr, sender_ip, sizeof(sender_ip));

            /* Check duplicate */
            bool exists = false;
            for (int i = 0; i < count; i++) {
                if (strcmp(out_hosts[i].ip, sender_ip) == 0 && out_hosts[i].port == port) {
                    exists = true;
                    out_hosts[i].last_seen_ms = current_time_ms();
                    break;
                }
            }

            if (!exists && count < max_hosts) {
                snprintf(out_hosts[count].ip, sizeof(out_hosts[count].ip), "%s", sender_ip);
                out_hosts[count].port = port;
                snprintf(out_hosts[count].hostname, sizeof(out_hosts[count].hostname), "%s", host);
                snprintf(out_hosts[count].game_title, sizeof(out_hosts[count].game_title), "%s", title);
                out_hosts[count].last_seen_ms = current_time_ms();
                count++;
            }
        }
    }

    close(fd);
    return count;
}
