# Context: ani-cast (Anime Desktop Streaming & Chromecast Engine)

## Overview
**ani-cast** is a desktop streaming, local playback, and Chromecast casting suite tailored for anime streaming. It combines a CLI runner (`ani-cast`), an interactive dmenu/rofi-style selector (`ani-cast-menu`), a PySide6 GUI (`ani-cast-gui`), and a local HLS streaming proxy server (`hls_streamer.py`) with MPV resume tracking via Lua.

## Architecture & Technology
- **Languages**: Python 3 (PySide6 / Qt6, HTTP server, HLS streaming), Bash, Lua (MPV scripts).
- **Core Components**:
  - `bin/ani-cast`: Command-line streamer and player orchestrator.
  - `bin/ani-cast-menu`: Rofi / dmenu interactive episode and quality selector.
  - `bin/mpv-chromecast`: Streaming pipeline to Google Chromecast devices.
  - `gui/`: Full PySide6 application with dark theme, image caching, download manager, and playback controls.
  - `lib/anicast_engine.py`: Scraper and stream resolver engine.
  - `lib/hls_streamer.py`: Custom local HTTP proxy server for segment re-streaming and header spoofing.
  - `lib/ani_cast_mpv_resume.lua`: Automatic playback timestamp caching and resumption.
- **Styling**: Catppuccin / TokyoNight dark aesthetic (`gui/style.css`).
- **Dependencies**: `python-pyside6`, `mpv`, `ffmpeg`, `yt-dlp` (optional), `socat`.
