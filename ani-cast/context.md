# Context: ani-cast (Anime Desktop Streaming & Chromecast Engine)

## Overview
**ani-cast** is a complete anime streaming, local desktop playback, and Google Chromecast casting suite tailored for Arch Linux and BSPWM. It features a CLI runner, an interactive dmenu/rofi-style selector, a GTK 4 / Libadwaita dark desktop GUI, a custom local HLS proxy server, and MPV resume tracking via Lua.

## Architecture & Technology
- **Languages**: Python 3 (PyGObject / GTK 4 / Libadwaita, HTTP server, HLS proxy), Bash, Lua (MPV hooks).
- **Styling**: Catppuccin Mocha / TokyoNight dark palette (`gui/style.css`).
- **Dependencies**: `python-gobject`, `gtk4`, `libadwaita`, `mpv`, `ffmpeg`, `socat`, `yt-dlp` (optional).

## Core Components & Structure
- **CLI (`bin/ani-cast`)**:
  - Full CLI frontend supporting resume, local playback, download queuing, quality selection (`720p`, `1080p`), dub/sub toggles, and episode jumping.
  - Automatically manages temporary session state files in `$XDG_RUNTIME_DIR`.
- **Interactive Selector (`bin/ani-cast-menu`)**:
  - Rofi / dmenu fuzzy search integration for episode and Chromecast device selection.
- **Chromecast Pipeline (`bin/mpv-chromecast`)**:
  - Bridges local or remote HLS video streams to network Chromecast devices.
- **GUI Application (`gui/`)**:
  - `app.py` & `window.py`: GTK 4 / Libadwaita GUI window with dark mode, search bar, and grid display.
  - `playback_manager.py`: Controls MPV IPC socket, play/pause, volume, and timeline scrub.
  - `download_manager.py`: Multi-threaded background episode downloader with progress tracking.
  - `device_manager.py`: Discovers local Chromecast devices on LAN.
  - `image_cache.py`: Local asynchronous poster and thumbnail caching.
- **Engine & Streaming (`lib/`)**:
  - `anicast_engine.py`: Scrapes stream links, parses anime providers, and resolves CDN sources.
  - `hls_streamer.py`: High-performance local HTTP server handling HLS m3u8 playlist rewriting, header spoofing (Referer/User-Agent), and segment proxying.
  - `ani_cast_mpv_resume.lua`: MPV hook that records playback timestamps in `~/.local/state/ani-cast/` and resumes automatically.

## Usage & Commands
```bash
# Launch interactive CLI
ani-cast "Frieren"

# Resume last watched anime
ani-cast --continue

# Play locally instead of casting to TV
ani-cast --local "Steins Gate"

# Download episode
ani-cast --download "Attack on Titan" -s 1 -e 1 --quality 1080p

# Launch full PySide6 GUI
ani-cast-gui
```
