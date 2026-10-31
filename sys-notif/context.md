# Context: sys-notif (Lightweight Desktop Notification & OSD Daemon)

## Overview
**sys-notif** is a modern, ultra-lightweight desktop notification daemon and on-screen display (OSD) server built specifically for Arch Linux and BSPWM. It completely replaces standard notification daemons (like Dunst or Mako) with a sleek Catppuccin Mocha aesthetic, smooth animations, and audio-safe feedback.

## Architecture & Technology
- **Language**: Native C with Cairo 2D vector drawing, Pango typography, GDK-Pixbuf, and GLib GIO D-Bus.
- **Specification Compliance**: Full Freedesktop `org.freedesktop.Notifications` D-Bus standard compliance.
- **Memory Footprint**: Extremely low (~6–10 MB RSS), making it ideal for 4 GB RAM systems.
- **Visual Features**:
  - Catppuccin Mocha color scheme with 32-bit TrueColor alpha blending and rounded corners.
  - Backward-shrinking countdown progress bar on notification cards.
  - OSD progress bars for volume (including >100% boost) and screen backlight.
  - Web service auto-detection (Instagram, WhatsApp, YouTube, Telegram) with icon mapping.
  - Low-latency notification chime audio playback.

## Modes of Operation
1. **D-Bus Daemon (Background)**:
   Listens on the session bus for standard notifications sent via `notify-send` or applications:
   ```bash
   sys-notif
   ```
2. **CLI OSD Client Mode (<2ms non-blocking)**:
   Instantly pops up an OSD bar without creating an extra daemon process:
   ```bash
   sys-notif --osd volume 75
   sys-notif --osd volume 0 muted
   sys-notif --osd brightness 50
   ```

## History & Storage
- Notification history is logged to `~/.cache/sys-notif/history.txt` for retrieval by `sys-notif-center`.
- Downloaded web avatars and icons are stored in `~/.cache/sys-notif/avatars/`.

## Compilation
```bash
cd /home/vibecoder/Projects/sys-notif
make
```
