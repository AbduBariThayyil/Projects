# GBA Crossplay Context

## Overview
GBA Crossplay is a cross-platform Game Boy Advance multiplayer emulation solution bridging Arch Linux and iOS with cycle-accurate serial link cable (SIO) communication and synchronized multiplayer fast-forward over local Wi-Fi.

## Architecture
- **Core Engine:** Standalone `libmgba` (C) shared library.
- **Protocol:** `core/link_protocol.c` manages SIO packet synchronization and bidirectional turbo state broadcast.
- **Fast-Forward:** Symmetrical lockstep turbo (`core/turbo_sync.c`) ensuring both clients accelerate synchronously without SIO clock desync.
- **Arch Linux:** Snappy SDL2 + Dear ImGui style minimalist HUD client (`linux/src/main.c`).
- **iOS:** SwiftUI + Metal 60/120Hz canvas with virtual on-screen gamepad, haptic turbo trigger, and GameController framework (`ios/GBACrossplay/`).
- **CI/CD:** GitHub Actions macOS runner compiling the iOS `.ipa` for AltStore / SideStore sideloading (`.github/workflows/build-ios.yml`).

## Verification
- Unit test suite: `tests/test_protocol.c` and `tests/test_turbo.c` (`make -C tests`).
- Headless live verification: `./linux/gba-crossplay <rom.gba> --headless`.
