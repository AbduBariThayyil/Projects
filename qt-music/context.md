# Context: qt-music (Native Music & Lyrics Suite)

## Overview
**qt-music** is a comprehensive, low-resource music playback, synced lyrics visualization, and music download suite tailored for low-RAM Arch Linux systems running BSPWM.

## Architecture & Sub-Tools
The project consists of 4 distinct tools:

### 1. `qt-music` (formerly `lyricview`)
- **Type**: PySide6 / Qt Quick standalone music player and synced lyrics display.
- **Key Features**:
  - Two-stage architecture: Lightweight headless background audio engine (`QMediaPlayer` / GStreamer) and on-demand GUI window.
  - Low-spec GPU optimizations: `--lite` mode for Intel HD Graphics.
  - Native MPRIS D-Bus integration for global media keys and Polybar synchronization.
  - Controls: `Space` (Play/Pause), `F` (Fullscreen toggle), `←`/`→` (Seek), `[`/`]` (Lyric offset adjustment).
- **Execution**:
  ```bash
  ./qt-music           # Launch player
  ./qt-music --lite    # Run in ultra-low RAM mode
  ./qt-music --own     # Play local library
  ```

### 2. `lyricview-web`
- **Type**: Python lightweight web server streaming synced lyrics from the active MPRIS desktop player over HTTP/WebSockets.
- **Use Case**: Display real-time synchronized lyrics on secondary screens, tablets, or phones across the local network without extra desktop load.
- **Execution**:
  ```bash
  ./lyricview-web --no-browser --port 8765
  ```

### 3. `musicD`
- **Type**: Automated music downloader and ID3 tagger.
- **Backend**: Fetches high-bitrate audio from YouTube Music, tags metadata via iTunes API, and pulls synchronized LRC lyrics.
- **Execution**:
  ```bash
  ./musicD song "Song Title - Artist"
  ./musicD album "Playlist/Album URL"
  ./musicD lyrics ~/Music
  ```

### 4. `PolybarMusic`
- **Type**: Shell script companion for Polybar status bar.
- **Features**: Displays currently playing track, playback status, and interactive controls (play, pause, next, close).

## Supporting Files
- `Instructions.md`: Detailed system requirements, keybindings, and workflow instructions.
- `Suggestions.md`: Feature roadmap and design ideas.
- `Work.txt`: Development log and task checklist.
