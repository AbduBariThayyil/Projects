# GBA Crossplay

A high-performance, cycle-accurate Game Boy Advance multiplayer emulation suite designed specifically for crossplay between **Arch Linux** and **iOS**.

Built on the native `libmgba` C engine, it delivers low-latency GBA Link Cable synchronization over Wi-Fi, bidirectional symmetrical fast-forward (turbo), zero-configuration mDNS/UDP beacon discovery, and a hybrid input system supporting both touch and Bluetooth controllers.

---

## 🎮 Compatible Games

Specifically engineered and verified for titles requiring hardware link cable emulation:
* **Pokémon Quetzal (Emerald Multiplayer ROM Hack):** Full overworld co-op, real-time following, wild doubles, trades, and battles.
* **Kirby & The Amazing Mirror:** 4-player real-time 60 FPS platforming with cell phone summoning and separate world exploration.

---

## ✨ Features

* **No RetroArch, No Web:** 100% standalone native binaries on Arch Linux and iOS.
* **Symmetrical Fast-Forward (Turbo):** Either player can hold the Fast-Forward key/button (`Tab` on Linux, dedicated glowing **Turbo** button on iOS, or Controller R2). Both devices accelerate simultaneously in lockstep (2x or 3x) without link cable timeout or buffer overflow.
* **Auto-Discovery:** Arch Linux broadcasts a local network beacon on UDP 52840. The iOS client automatically discovers the host with a 1-tap join list.
* **ProMotion & Metal Support:** 60 FPS / 120 FPS Metal rendering on iPhone/iPad.
* **Hybrid iOS Controls:** On-screen virtual D-Pad, A, B, L, R, Start, Select, and glowing Turbo button with haptic feedback, plus automatic MFi/Xbox/PlayStation controller detection.
* **BSPWM / Tiling Friendly:** Lightweight SDL2 + pixel font HUD on Arch Linux with integer aspect ratio preservation.

---

## 🚀 Arch Linux Quickstart

### 1. Build
```bash
cd gba-crossplay
make all
```

### 2. Host a Multiplayer Session
```bash
./linux/gba-crossplay /path/to/pokemon_quetzal.gba --host 52841
```
* The beacon will start broadcasting on your local Wi-Fi automatically.
* Once the iOS player joins, the session will launch into link cable mode.

### 3. Controls (Arch Linux)
| Action | Keyboard | Gamepad (Xbox/PlayStation) |
| :--- | :--- | :--- |
| **D-Pad** | Arrow Keys / WASD | D-Pad / Left Stick |
| **A Button** | `X` | `A` (Xbox) / `Cross` (PS) |
| **B Button** | `Z` | `B` (Xbox) / `Circle` (PS) |
| **L Shoulder** | `A` | `Left Bumper` (LB) |
| **R Shoulder** | `S` | `Right Bumper` (RB) |
| **Start / Select** | `Enter` / `Backspace` | `Start` / `Back` |
| **Fast-Forward (Turbo)** | `Tab` (Hold) | `Right Trigger` (RT / R2) |
| **Toggle HUD** | `F1` | - |
| **Quit** | `Esc` | - |

---

## 📱 iOS Sideloading Quickstart

### 1. Download `.ipa` from GitHub Actions
* Go to the **Actions** tab on your GitHub repository.
* Click on the latest workflow run under **Build iOS IPA**.
* Download the `GBACrossplay-iOS-IPA` artifact.

### 2. Install with AltStore / SideStore
1. Open the `.ipa` file on your iPhone.
2. Tap **Share → AltStore** (or SideStore / TrollStore).
3. The app will install with zero errors and appear on your Home Screen.

### 3. Join the Game
1. Open **GBA Crossplay** on iOS.
2. Ensure your iPhone is connected to the same Wi-Fi as your Arch Linux PC.
3. Tap **Lobby (Scan)** at the top.
4. Your Arch Linux host will appear in the list. Tap **Join** to connect!
5. Use touch controls or pair any Bluetooth Xbox/PlayStation/Backbone controller.

---

## 📁 Project Structure

```
gba-crossplay/
├── core/                       # Shared GBA network link protocol & turbo sync
│   ├── link_protocol.h         # SIO packet serialization & opcodes
│   ├── link_protocol.c         # State machine & packet transport
│   ├── turbo_sync.h            # Symmetrical turbo coordinator
│   └── turbo_sync.c            # Frame delay & lockstep pacing
├── linux/                      # Native Arch Linux SDL2 client
│   ├── include/                # Audio, discovery, emulator, HUD headers
│   ├── src/                    # Implementation files
│   └── Makefile                # Linux build definition
├── ios/                        # Native iOS SwiftUI + Metal client
│   ├── GBACrossplay/           # Swift, Metal, and GameController source
│   ├── GBACrossplay.xcodeproj  # Xcode project configuration
│   └── Info.plist              # Permissions & document associations
├── .github/workflows/          # CI/CD pipeline building iOS .ipa
└── tests/                      # Core protocol & turbo sync unit tests
```
