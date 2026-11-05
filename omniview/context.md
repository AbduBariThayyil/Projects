# Context: omniview (Universal Media Streaming & Cast Engine)

## Overview
**OmniView** is a universal Anime, Movies, and TV Shows desktop streaming, local playback, and Google Chromecast casting suite tailored for Arch Linux and BSPWM. It features a polished, symmetrical Catppuccin Mocha CLI, an interactive dmenu/rofi-style selector, a multi-tab GTK 4 / Libadwaita dark desktop GUI, a custom high-performance local HLS proxy server, and MPV resume tracking via Lua.

## Architecture & Technology
- **Languages**: Python 3 (PyGObject / GTK 4 / Libadwaita, HTTP server, HLS proxy), Bash, Lua (MPV hooks).
- **Styling**: Catppuccin Mocha dark aesthetic (`gui/style.css` & CLI box-drawing ANSI palette).
- **Dependencies**: `python-gobject`, `gtk4`, `libadwaita`, `mpv`, `ffmpeg`, `socat`, `yt-dlp` (optional).

## Core Components & Structure
- **CLI (`bin/omniview`)**:
  - Unified CLI frontend with a symmetrical Catppuccin Mocha box-drawing layout.
  - Seamlessly searches and streams Anime, Movies, and TV Shows.
  - Supports `--continue`, `--local`, `--cast`, `--movie`, `--show`, quality selection (`1080p`, `720p`), dub/sub toggles, and episode jumping.
  - Clean MPV subprocess execution with zero terminal clutter.
- **Interactive Selector (`bin/omniview-menu`)**:
  - Rofi / dmenu fuzzy search integration for episode and Chromecast device selection.
- **Chromecast Pipeline (`bin/mpv-chromecast`)**:
  - Bridges local or remote HLS video streams to network Chromecast devices.
- **GUI Application (`gui/`)**:
  - `app.py` & `window.py`: Multi-tab GTK 4 / Libadwaita GUI window with `🌸 Anime`, `🎬 Movies & Shows`, and `💾 Downloads / Library`.
  - `playback_manager.py`: Controls MPV IPC socket, play/pause, volume, Chromecast casting, and timeline scrub.
  - `download_manager.py`: Multi-threaded background downloader with progress tracking and completed-episode skipping.
  - `device_manager.py`: Discovers local Chromecast devices on LAN.
  - `image_cache.py`: Local asynchronous poster and thumbnail caching.
- **Engine & Streaming (`lib/`)**:
  - `anicast_engine.py`: Scrapes stream links, parses anime providers, and resolves CDN sources.
  - `movies_engine.py`: Scrapes and resolves stream links, seasons, and episodes for Movies and TV Shows.
  - `cli_view.py`: Symmetrical ANSI box-drawing presentation module for the OmniView CLI.
  - `hls_streamer.py`: High-performance local HTTP server handling HLS m3u8 playlist rewriting, header spoofing (Referer/User-Agent), and segment proxying.
  - `ani_cast_mpv_resume.lua`: MPV hook that records playback timestamps in `~/.local/state/omniview/` (with fallback to `ani-cast/`) and resumes automatically.

## Usage & Commands
```bash
# Launch interactive CLI
omniview "Frieren"
omniview --movie "Interstellar"
omniview --show "Breaking Bad"

# Resume last watched media
omniview --continue

# Play locally instead of casting to TV
omniview --local "Steins Gate"

# Download episode
omniview --download "Attack on Titan" -s 1 -e 1 --quality 1080p

# Launch full GTK 4 / Libadwaita GUI
omniview-gui
```
