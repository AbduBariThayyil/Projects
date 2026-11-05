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
- `Makefile`: Compilation with `gcc -O2`, linking `x11`, `cairo`, `pango`, `pangocairo`, `glib-2.0`.
- `keyholder-hud`: Compiled native binary.

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
