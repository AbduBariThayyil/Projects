#include "../core/link_protocol.h"
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

void test_header_validation(void) {
    GBALinkHeader hdr;
    gba_link_header_init(&hdr, PKT_HANDSHAKE, 0, sizeof(GBAPacketHandshake));

    assert(hdr.magic == GBA_LINK_MAGIC);
    assert(hdr.type == PKT_HANDSHAKE);
    assert(hdr.player_id == 0);
    assert(hdr.length == sizeof(GBAPacketHandshake));
    assert(gba_link_header_validate(&hdr) == true);

    hdr.magic = 0x12345678;
    assert(gba_link_header_validate(&hdr) == false);
    printf("PASS: test_header_validation\n");
}

void test_socket_roundtrip(void) {
    int sv[2];
    assert(socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == 0);

    GBAPacketTurbo turbo_send = { .is_turbo = 1, .multiplier = 3, .sender_id = 1 };
    int ret = gba_link_send_packet(sv[0], PKT_TURBO_STATE, 1, &turbo_send, sizeof(turbo_send));
    assert(ret == 0);

    GBALinkHeader recv_hdr;
    ret = gba_link_recv_header(sv[1], &recv_hdr);
    assert(ret == sizeof(GBALinkHeader));
    assert(recv_hdr.type == PKT_TURBO_STATE);
    assert(recv_hdr.player_id == 1);
    assert(recv_hdr.length == sizeof(GBAPacketTurbo));

    GBAPacketTurbo turbo_recv;
    ret = gba_link_recv_payload(sv[1], &recv_hdr, &turbo_recv, sizeof(turbo_recv));
    assert(ret == sizeof(GBAPacketTurbo));
    assert(turbo_recv.is_turbo == 1);
    assert(turbo_recv.multiplier == 3);
    assert(turbo_recv.sender_id == 1);

    close(sv[0]);
    close(sv[1]);
    printf("PASS: test_socket_roundtrip\n");
}

int main(void) {
    printf("Running protocol tests...\n");
    test_header_validation();
    test_socket_roundtrip();
    printf("All protocol tests passed successfully!\n");
    return 0;
}
