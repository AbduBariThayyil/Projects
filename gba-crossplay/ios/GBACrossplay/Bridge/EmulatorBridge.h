#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>

NS_ASSUME_NONNULL_BEGIN

@protocol EmulatorBridgeDelegate <NSObject>
- (void)emulatorDidUpdateTurboState:(BOOL)isTurbo multiplier:(uint8_t)multiplier;
- (void)emulatorDidConnectPeer:(NSString*)peerIP;
- (void)emulatorDidDisconnect;
@end

@interface EmulatorBridge : NSObject

@property (class, readonly, strong) EmulatorBridge* shared;
@property (nonatomic, weak) id<EmulatorBridgeDelegate> delegate;
@property (nonatomic, readonly) BOOL isRunning;
@property (nonatomic, readonly) BOOL isConnected;
@property (nonatomic, readonly) BOOL isTurboActive;
@property (nonatomic, readonly) uint8_t turboMultiplier;
@property (nonatomic, readonly) NSString* gameTitle;

+ (instancetype)shared;

- (BOOL)loadROMAtPath:(NSString*)romPath;
- (void)startEmulation;
- (void)stopEmulation;

/* Connect to Arch Linux host */
- (BOOL)connectToHost:(NSString*)hostAddress port:(uint16_t)port;
- (void)disconnect;

/* Input updates */
- (void)setKeys:(uint32_t)keysBitmask;
- (void)setTurboActive:(BOOL)active;

/* Render buffer access (240x160 RGBA32) */
- (const uint32_t*)getVideoBuffer;

@end

NS_ASSUME_NONNULL_END
