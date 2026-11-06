# Context: keyholder-hud (Zero-Latency X11 Overlay HUD)

## Overview
**keyholder-hud** is a high-performance, lightweight native C overlay HUD built with Xlib, Cairo, and Pango. It replaces intrusive desktop notification popups with a floating, non-intrusive on-screen display (HUD) for keystroke locking, mode changes, and key status.

## Architecture & Technology
- **Language**: Pure C (C99/GNU99).
- **Graphics Pipeline**: Cairo 2D vector graphics with Pango text rendering, 32-bit ARGB TrueColor with rounded corners and Catppuccin Mocha aesthetic.
- **IPC Mechanism**: Per-user named FIFO pipe at `$XDG_RUNTIME_DIR/keyholder-hud.fifo` (with legacy fallback/symlink at `/tmp/keyholder-hud.fifo`) for sub-millisecond asynchronous message delivery with on-demand daemon autospawning.
- **Performance**: Sub-1ms render time, cached Pango font descriptions, zero CPU when idle, idle auto-exit with instant CLI wake, <5 MB RSS memory.

## Key Files
- `keyholder-hud.c`: Main event loop (Glib `GMainLoop`), X11 window initialization with `_NET_WM_WINDOW_TYPE_NOTIFICATION` / override-redirect, FIFO reader, and Cairo rendering.
- `KeyHolder`: Standalone Python evdev automation daemon managing high-frequency spamming, latching, and holding of keyboard/mouse inputs with live HUD feedback.
- `Makefile`: Compilation with `gcc -O2`, linking `x11`, `cairo`, `pango`, `pangocairo`, `glib-2.0`, and installing binaries to `$(PREFIX)/bin` and `~/.config/bspwm/bin`.
- `keyholder-hud`: Compiled native binary.

## KeyHolder Input Automation & Ignored Binds
The `KeyHolder` CLI script (`KeyHolder --spam`, `--hold`, `--terminate`, `--inc`, `--dec`) captures evdev input events to latch onto user keys.

### Ignored Key Codes (`IGNORED_CODES`)
To prevent window manager chords, sxhkd binds, and modifier triggers from being latched onto or interrupting holding sessions:
- **Modifiers**: `KEY_LEFTMETA`, `KEY_RIGHTMETA`, `KEY_LEFTALT`, `KEY_RIGHTALT`, `KEY_LEFTCTRL`, `KEY_RIGHTCTRL`, `KEY_LEFTSHIFT`, `KEY_RIGHTSHIFT`, `KEY_CAPSLOCK`, `KEY_COMPOSE`.
- **Mouse Modifiers & Extra Buttons**: `BTN_SIDE` (275 / `mod3`), `BTN_EXTRA` (276 / `mod5`), `BTN_FORWARD` (277), `BTN_BACK` (278), `BTN_TASK` (279).
- **Keyd / Function Layers**: `KEY_F13` through `KEY_F24` (inclusive).
- **Multimedia & System Hotkeys**: `KEY_CALC`, `KEY_CALCULATOR`, `KEY_HOMEPAGE`, `KEY_MAIL`, `KEY_POWER`, `KEY_SLEEP`, `KEY_WAKEUP`, `KEY_MUTE`, `KEY_VOLUMEDOWN`, `KEY_VOLUMEUP`, `KEY_PLAYPAUSE`, `KEY_PAUSE`, `KEY_PLAY`, `KEY_PREVIOUSSONG`, `KEY_NEXTSONG`, `KEY_BRIGHTNESSDOWN`, `KEY_BRIGHTNESSUP`, `KEY_SYSRQ`, `KEY_PRINT`.
- **Touchpad Pseudo-Buttons**: `0x140` through `0x14f`.

### Chord & Pre-Hold Latch Immunity
`wait_for_latch(sel, devices)` captures `initially_down = set()` across all devices before listening. Any keys already physically held during sxhkd chord invocation (e.g. `mod5 + button1`) are ignored until fully released (`event.value == 0`), preventing false latching onto trigger keys.

## IPC Protocol
Send simple newline-terminated strings to `/tmp/keyholder-hud.fifo`:
```bash
# Format: <mode>|<title>|<subtitle>
echo "locked|KeyHolder|Caps Lock ON" > /tmp/keyholder-hud.fifo
echo "gaming|Macro Mode|Profile 1 Active" > /tmp/keyholder-hud.fifo
```

## Compilation
```bash
cd /home/vibecoder/Projects/keyholder-hud
make
```
