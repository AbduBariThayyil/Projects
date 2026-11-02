# Context: polybar-music (Native High-Efficiency D-Bus Media Widget)

## Overview
**polybar-music** (`PolybarMusic`) is a lightweight native C streaming module for Polybar. It connects directly to the session D-Bus to monitor `lyricview` (and `qt-music`), rendering animated playback status, song titles, progress bars, and interactive click/scroll controls without polling.

## Architecture & Technology
- **Language**: Pure C (C99/GNU99) with GIO/GLib (`gio-2.0`).
- **Streaming Mode**: Polybar `type = custom/script` with `tail = true`.
- **Target Player**: Strictly locked to `org.mpris.MediaPlayer2.lyricview` / `org.mpris.MediaPlayer2.qt-music`.
- **Event-Driven**: Uses `g_bus_watch_name` and `g_dbus_connection_signal_subscribe`. When lyricview is idle or closed, it consumes **0.0% CPU** and performs zero polling.
- **Controls**:
  - Left click (Title/Face/Bar): Launch or focus LyricView (`LyricViewLauncher`).
  - Right click: Toggle LyricView (`lyricview --toggle`).
  - Scroll Up / Down: Seek ∓5 seconds (`playerctl position 5+ / 5-`).
  - Play/Pause icon: Toggle playback.
  - Previous / Next icons: Track traversal.
  - Close button: Exit player cleanly.
