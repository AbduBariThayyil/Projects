# Context: xmodmap-watcher (X11 Modifier Mapping Auto-Reloader)

## Overview
**xmodmap-watcher** is a tiny, zero-overhead native C daemon designed for X11 / BSPWM environments. It monitors X11 `MappingNotify` and Xkb extension events (triggered by USB keyboard hotplugging, layout toggles, or suspend/wake cycles) and automatically re-applies `~/.Xmodmap` without desktop stutter or freeze.

## Architecture & Technology
- **Language**: C99 with `libX11` & `Xkb`.
- **Detection Logic**: Listens for core `MappingNotify` and Xkb events (`XkbNewKeyboardNotify`, `XkbMapNotify`). Inspects `XGetModifierMapping` to check if `XK_Hyper_L` is mapped to `Mod3MapIndex`. If absent, triggers remap.
- **Debounce**: 200ms rate-limiting debounce using `clock_gettime(CLOCK_MONOTONIC)` to prevent multiple rapid executions during device enumeration.
- **Process Management**: Single-instance enforcement via `flock(fd, LOCK_EX | LOCK_NB)` on `$XDG_RUNTIME_DIR/xmodmap_watcher.lock` (fallback to `/tmp/xmodmap_watcher-<uid>.lock`) with clean exit and `SIGINT` / `SIGTERM` / `XSetIOErrorHandler` cleanup.
- **Subprocess Isolation**: Forks a non-blocking detached process (`xmodmap ~/.Xmodmap`) with `SIGCHLD` ignored to avoid zombies.
- **Path Resolution**: Dynamically resolves `~/.Xmodmap` via `getenv("HOME")` or user passwd entry.

## Build & Execution
```bash
# Build
cd /home/vibecoder/Projects/xmodmap-watcher
make clean && make

# Install
make install

# Service restart
systemctl --user restart xmodmap-watcher.service
```
