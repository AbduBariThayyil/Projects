#include "link_protocol.h"
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <stdio.h>

void gba_link_header_init(GBALinkHeader* hdr, GBALinkPacketType type, uint8_t player_id, uint16_t payload_len) {
    if (!hdr) return;
    hdr->magic = GBA_LINK_MAGIC;
    hdr->type = (uint8_t)type;
    hdr->player_id = player_id;
    hdr->length = payload_len;
}

bool gba_link_header_validate(const GBALinkHeader* hdr) {
    if (!hdr) return false;
    if (hdr->magic != GBA_LINK_MAGIC) return false;
    return true;
}

static int send_all(int fd, const void* data, size_t total_bytes) {
    size_t sent = 0;
    const uint8_t* ptr = (const uint8_t*)data;
    while (sent < total_bytes) {
        ssize_t ret = send(fd, ptr + sent, total_bytes - sent, MSG_NOSIGNAL);
        if (ret < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (ret == 0) return -1;
        sent += (size_t)ret;
    }
    return 0;
}

static int recv_all(int fd, void* data, size_t total_bytes) {
    size_t received = 0;
    uint8_t* ptr = (uint8_t*)data;
    while (received < total_bytes) {
        ssize_t ret = recv(fd, ptr + received, total_bytes - received, 0);
        if (ret < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (ret == 0) return 0; /* EOF */
        received += (size_t)ret;
    }
    return (int)received;
}

int gba_link_send_packet(int socket_fd, GBALinkPacketType type, uint8_t player_id, const void* payload, uint16_t len) {
    if (socket_fd < 0) return -1;

    GBALinkHeader hdr;
    gba_link_header_init(&hdr, type, player_id, len);

    if (send_all(socket_fd, &hdr, sizeof(hdr)) < 0) {
        return -1;
    }

    if (len > 0 && payload) {
        if (send_all(socket_fd, payload, len) < 0) {
            return -1;
        }
    }

    return 0;
}

int gba_link_recv_header(int socket_fd, GBALinkHeader* hdr) {
    if (socket_fd < 0 || !hdr) return -1;

    int ret = recv_all(socket_fd, hdr, sizeof(GBALinkHeader));
    if (ret <= 0) return ret;

    if (!gba_link_header_validate(hdr)) {
        return -2; /* Invalid header/magic */
    }

    return (int)sizeof(GBALinkHeader);
}

int gba_link_recv_payload(int socket_fd, const GBALinkHeader* hdr, void* buffer, size_t max_buf_len) {
    if (socket_fd < 0 || !hdr || !buffer) return -1;
    if (hdr->length == 0) return 0;
    if (hdr->length > max_buf_len) return -3; /* Buffer too small */

    int ret = recv_all(socket_fd, buffer, hdr->length);
    if (ret <= 0) return ret;

    return ret;
}
