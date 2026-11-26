# Context: sys-input (Unified Input Remapper & X11 Sync Daemon)

## Overview
**sys-input** is a zero-polling, sub-2 MB RSS native C daemon built on Linux `evdev`, `uinput`, `epoll`, `inotify`, `timerfd`, and `libX11` (`XKB`). It replaces `keyd`, `xmodmap-watcher`, and `~/.Xmodmap` in a single event-driven binary while keeping `sxhkd` for desktop/WM hotkeys.

## Architecture & Key Features
- **Zero-Polling Event Loop**: Uses `epoll` on physical `/dev/input/event*` devices, `inotify` for USB hotplug detection, `timerfd` for non-blocking tap releases, and the X11 connection socket for keymap sync.
- **Desktop ↔ Gaming Mode (`F13` / Mouse Button 5 `KEY_CALC`)**:
  - **Desktop Mode**:
    - Mouse Backward (`BTN_SIDE`) acts as `mod3` (`KEY_F23` / `Hyper_L`) and executes media/volume chords (`+ Left/Middle/Right/Wheel/Space`) directly in `evdev`, bypassing Wine/fullscreen grabs.
    - Mouse Forward (`BTN_EXTRA`) acts as a brightness modifier (`+ Wheel Up/Down` → `sys-control --bri-up/down`) with non-blocking tap passthrough (`BTN_EXTRA`).
    - Mouse Corner Button (`KEY_MAIL`) maps cleanly to `KEY_F15`; DPI Button (`KEY_HOMEPAGE`) maps cleanly to `KEY_F14`.
  - **Gaming Mode**:
    - Mouse Backward/Forward/Corner emit pure `BTN_SIDE`, `BTN_EXTRA`, `KEY_F15` with zero tap delay and no held `mod3`.
- **External `CASUE USB KB` Fn-Lock (`KEY_SCROLLLOCK`)**:
  - Toggles `F1`–`F10` / `F12` between standard function keys and music/media/utility actions (`qt-music`, `vol-dec`, `vol-inc`, `vol-toggle`, `stop`, `previous`, `toggle`, `next`, `KeyHolder --hold`, `KeyHolder --spam`, `calc`; `F11` unchanged), synchronized with the keyboard's Scroll Lock LED and sleek `sys-notif --osd` highlight pills.
- **Global Hardware Keys**:
  - `Shift + F1` triggers `BacklightToggle` across all keyboards (including lockscreens and fullscreen games).
  - Hardware `XF86Audio*`, `XF86MonBrightness*`, and Toshiba `KEY_TOUCHPAD_TOGGLE` / `KEY_UNKNOWN` execute directly from `evdev`.
- **Built-in X11 Keymap & `mod3` Sync**:
  - Replaces `xmodmap` and `xmodmap-watcher` via direct `XChangeKeyboardMapping` / `XSetModifierMapping` on `MappingNotify` and XKB map changes.

## Build & Test
```bash
cd /home/vibecoder/Projects/sys-input
make clean && make && make test
```
