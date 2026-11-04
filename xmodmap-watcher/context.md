# Context: xmodmap-watcher (X11 Modifier Mapping Auto-Reloader)

## Overview
**xmodmap-watcher** is a tiny, zero-overhead native C daemon designed for X11 / BSPWM environments. It monitors X11 `MappingNotify` events (triggered by USB keyboard hotplugging, layout toggles, or suspend/wake cycles) and automatically re-applies `~/.Xmodmap` without desktop stutter or freeze.

## Architecture & Technology
- **Language**: C99 with `libX11`.
- **Detection Logic**: Inspects `XGetModifierMapping` to check if `XK_Hyper_L` is mapped to `Mod3MapIndex`. If absent, triggers remap.
- **Debounce**: 200ms rate-limiting debounce using `clock_gettime(CLOCK_MONOTONIC)` to prevent multiple rapid executions during device enumeration.
- **Process Management**: Single-instance enforcement via `/tmp/.xmodmap_watcher.pid` with `SIGINT` / `SIGTERM` cleanup.
- **Subprocess Isolation**: Forks a non-blocking detached process (`xmodmap ~/.Xmodmap`) with `SIGCHLD` ignored to avoid zombies.

## Build & Execution
```bash
# Build
cd /home/vibecoder/Projects/xmodmap-watcher
make

# Run in background (usually launched from ~/.config/bspwm/bspwmrc)
./xmodmap-watcher &
```
