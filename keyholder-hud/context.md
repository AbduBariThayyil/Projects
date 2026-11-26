# Context: keyholder-hud (Native C Key/Mouse Hold & Spam Suite + Micro-Pill HUD)

## Overview
**keyholder-hud** is a 100% native C automation suite replacing the legacy Python `KeyHolder` script and oversized bottom HUD. It combines a lightweight `epoll` + `uinput` daemon (`KeyHolder`) with a sleek, click-through Catppuccin Mocha micro-pill HUD (`keyholder-hud`) positioned cleanly below Polybar.

## Architecture & Key Features
- **Pure C Automation Daemon (`keyholder.c`, `keyholder-core.c`)**:
  - Single-instance Unix socket (`$XDG_RUNTIME_DIR/keyholder.sock`) + `flock` + `timerfd` + `inotify` device hotplug (zero polling, <2 MB RSS, <1ms CLI response).
  - **Simultaneous Hold + Spam**: Hold one or more keys (`--hold` / `--multi`) while spamming another (`--spam`) independently.
  - **No Hold Pulse Bug**: Holds keys continuously without release/repress glitches on unrelated keypresses.
  - **sxhkd Safe**: Uses non-floated `UInput` (`0x4b48:0x0001/0x0002`, ignored by `sys-input`) so 100% of X11 apps and Wine/evdev games receive inputs, while automatically pausing spam ticks whenever physical `Super` (`Meta`) or `Alt` is held so `sxhkd` binds never misfire.
  - **Smart Spam Timing**: Separate per-tap press duration (`--hold-ms`, default 15ms) and cycle delay (`--delay` / `--cps`, default 40ms / 25 CPS). Scroll wheel or `+`/`-` adjusts speed live during Listening; `Esc` cancels Listening.
- **Sleek Click-Through Micro-Pill HUD (`keyholder-hud.c`)**:
  - Compact 34px-tall dynamic-width Catppuccin Mocha pill centered below Polybar (`y = 52`).
  - 100% click-through via `XShapeCombineRectangles` (`ShapeInput`) so it never steals clicks in games.
  - Displays friendly keycap chips (`[←]`, `[LMB]`), pulsing status dot, live CPS, pause indicator, and elapsed timer.

## Build, Test & Install
```bash
cd /home/vibecoder/Projects/keyholder-hud
make clean && make && make test && make install
```
