# Context: xmodmap-watcher (X11 Modifier Mapping Auto-Reloader)

## Overview
**xmodmap-watcher** is a tiny, zero-overhead native C daemon designed for X11 / BSPWM environments. It monitors X11 MappingNotify and device configuration events (e.g., when plugging/unplugging external USB keyboards or waking from sleep) and automatically reloads `~/.Xmodmap` without manual intervention or desktop freezing.

## Architecture & Technology
- **Language**: C with `libX11`.
- **Event Loop**: Listens directly to X11 socket events (`XNextEvent`) for `MappingNotify` events and applies rate-limiting debounce before invoking `xmodmap ~/.Xmodmap`.
- **Process Management**: Self-daemonizes with a lock PID file in `/tmp/.xmodmap_watcher.pid`.
- **Build**: Single `Makefile` compiling `xmodmap-watcher.c` with `-O2 -Wall -Wextra -lX11`.
