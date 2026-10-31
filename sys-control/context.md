# Context: sys-control (High-Speed System & BSPWM Controller)

## Overview
**sys-control** is a unified, high-speed C binary engineered to replace bloated shell scripts in the BSPWM desktop environment. It delivers sub-2ms response latency for global multimedia hotkeys, screen brightness adjustments, window manipulation, and screenshot capture.

## Architecture & Technology
- **Language**: Pure C99 with Xlib, Glib, and POSIX APIs.
- **Sub-2ms Latency**: Bypasses shell startup overhead (`sh`, `bash`, `python`) by executing direct system calls or lightweight targeted subprocesses.
- **Hardware Integration**:
  - Direct sysfs backlight control (`/sys/class/backlight/`).
  - Audio control via `pamixer` and MPRIS `playerctl`.
  - Notification integration: Sends instant OSD display signals to `sys-notif`.
  - Window manager integration: Native Xlib client traversal, window kill, focus toggles, and workspace navigation.

## Commands & Usage
```bash
# Audio Volume Control
sys-control volume up [step]      # e.g., sys-control volume up 5
sys-control volume down [step]
sys-control volume mute-toggle
sys-control volume mic-mute-toggle

# Screen Brightness Control
sys-control brightness up [step]  # e.g., sys-control brightness up 10
sys-control brightness down [step]

# Media Control
sys-control media play-pause
sys-control media next
sys-control media prev

# Screenshots
sys-control screenshot full
sys-control screenshot select
sys-control screenshot window
```

## Compilation
```bash
cd /home/vibecoder/Projects/sys-control
make
```
