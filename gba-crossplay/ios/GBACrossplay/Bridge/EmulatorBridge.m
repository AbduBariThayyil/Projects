#import "EmulatorBridge.h"
#include "link_protocol.h"
#include "turbo_sync.h"

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>

@interface EmulatorBridge () {
    int _socketFd;
    GBATurboCoordinator _turbo;
    uint32_t _videoBuffer[240 * 160];
    uint32_t _currentKeys;
    uint16_t _localSendData;
    dispatch_queue_t _emuQueue;
    dispatch_source_t _timerSource;
}
@end

@implementation EmulatorBridge

+ (instancetype)shared {
    static EmulatorBridge* s_instance = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        s_instance = [[EmulatorBridge alloc] init];
    });
    return s_instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _socketFd = -1;
        _isRunning = NO;
        _isConnected = NO;
        _gameTitle = @"GBA";
        _emuQueue = dispatch_queue_create("cc.daudau.gba.crossplay.emu", DISPATCH_QUEUE_SERIAL);

        gba_turbo_init(&_turbo, 1, 2); /* Player 1 = Slave/Client */
        __weak typeof(self) weakSelf = self;
        gba_turbo_set_callback(&_turbo, [](bool is_active, uint8_t multiplier, void* userdata) {
            EmulatorBridge* strongSelf = (__bridge EmulatorBridge*)userdata;
            dispatch_async(dispatch_get_main_queue(), ^{
                [strongSelf.delegate emulatorDidUpdateTurboState:is_active multiplier:multiplier];
            });
        }, (__bridge void*)self);
    }
    return self;
}

- (BOOL)loadROMAtPath:(NSString*)romPath {
    if (![[NSFileManager defaultManager] fileExistsAtPath:romPath]) {
        return NO;
    }
    _gameTitle = [[romPath lastPathComponent] stringByDeletingPathExtension];
    return YES;
}

- (BOOL)connectToHost:(NSString*)hostAddress port:(uint16_t)port {
    [self disconnect];

    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return NO;

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, [hostAddress UTF8String], &addr.sin_addr);

    if (connect(fd, (struct sockaddr*)&addr, sizeof(addr)) != 0) {
        close(fd);
        return NO;
    }

    _socketFd = fd;
    _isConnected = YES;

    /* Send Handshake */
    GBAPacketHandshake hs;
    memset(&hs, 0, sizeof(hs));
    strncpy(hs.game_title, [_gameTitle UTF8String], sizeof(hs.game_title) - 1);
    hs.requested_slot = 1;
    hs.protocol_version = 1;

    gba_link_send_packet(_socketFd, PKT_HANDSHAKE, 1, &hs, sizeof(hs));

    [self.delegate emulatorDidConnectPeer:hostAddress];
    return YES;
}

- (void)disconnect {
    if (_socketFd >= 0) {
        gba_link_send_packet(_socketFd, PKT_DISCONNECT, 1, NULL, 0);
        close(_socketFd);
        _socketFd = -1;
    }
    _isConnected = NO;
    [self.delegate emulatorDidDisconnect];
}

- (void)setKeys:(uint32_t)keysBitmask {
    _currentKeys = keysBitmask;
}

- (void)setTurboActive:(BOOL)active {
    if (gba_turbo_set_local(&_turbo, active)) {
        if (_socketFd >= 0) {
            GBAPacketTurbo pkt;
            pkt.is_turbo = active ? 1 : 0;
            pkt.multiplier = _turbo.multiplier;
            pkt.sender_id = 1;
            gba_link_send_packet(_socketFd, PKT_TURBO_STATE, 1, &pkt, sizeof(pkt));
        }
    }
}

- (BOOL)isTurboActive {
    return gba_turbo_is_active(&_turbo);
}

- (uint8_t)turboMultiplier {
    return _turbo.multiplier;
}

- (const uint32_t*)getVideoBuffer {
    return _videoBuffer;
}

- (void)startEmulation {
    if (_isRunning) return;
    _isRunning = YES;

    _timerSource = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, _emuQueue);
    dispatch_source_set_timer(_timerSource, DISPATCH_TIME_NOW, GBA_BASE_FRAME_US * NSEC_PER_USEC, 1000 * NSEC_PER_USEC);

    __weak typeof(self) weakSelf = self;
    dispatch_source_set_event_handler(_timerSource, ^{
        [weakSelf stepFrame];
    });

    dispatch_resume(_timerSource);
}

- (void)stopEmulation {
    if (!_isRunning) return;
    _isRunning = NO;

    if (_timerSource) {
        dispatch_source_cancel(_timerSource);
        _timerSource = nil;
    }
    [self disconnect];
}

- (void)stepFrame {
    if (!_isRunning) return;

    /* Process network packets */
    if (_socketFd >= 0) {
        int flags = fcntl(_socketFd, F_GETFL, 0);
        fcntl(_socketFd, F_SETFL, flags | O_NONBLOCK);

        GBALinkHeader hdr;
        while (gba_link_recv_header(_socketFd, &hdr) > 0) {
            if (hdr.type == PKT_TURBO_STATE) {
                GBAPacketTurbo pkt;
                if (gba_link_recv_payload(_socketFd, &hdr, &pkt, sizeof(pkt)) > 0) {
                    gba_turbo_set_remote(&_turbo, hdr.player_id, pkt.is_turbo == 1);
                }
            } else if (hdr.type == PKT_SIO_MULTI) {
                GBAPacketSIOMulti pkt;
                if (gba_link_recv_payload(_socketFd, &hdr, &pkt, sizeof(pkt)) > 0) {
                    /* Reply with client's data */
                    GBAPacketSIOMulti reply;
                    memset(&reply, 0, sizeof(reply));
                    reply.transfer_id = pkt.transfer_id;
                    reply.data[1] = _localSendData;
                    gba_link_send_packet(_socketFd, PKT_SIO_MULTI, 1, &reply, sizeof(reply));
                }
            } else {
                char sink[256];
                gba_link_recv_payload(_socketFd, &hdr, sink, sizeof(sink));
            }
        }
        fcntl(_socketFd, F_SETFL, flags);
    }

    /* Dynamically adjust timer period for active turbo */
    uint32_t frameDelayUs = gba_turbo_get_frame_us(&_turbo);
    if (_timerSource) {
        dispatch_source_set_timer(_timerSource,
                                  dispatch_time(DISPATCH_TIME_NOW, frameDelayUs * NSEC_PER_USEC),
                                  frameDelayUs * NSEC_PER_USEC,
                                  500 * NSEC_PER_USEC);
    }
}

@end
