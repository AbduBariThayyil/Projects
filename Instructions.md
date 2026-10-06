# Project Instructions & Workflow Guide

## System & Environment Context
- **Host**: Toshiba Portégé R700 ("Arch Xiao") running Arch Linux.
- **Hardware Specs**: 
  - RAM: 4 GB (ZRAM + `/swapfile`).
  - Storage: 250 GB SSD (`sda`).
  - Desktop: BSPWM with custom `gh0stzk` dotfiles (`~/.config/bspwm`, `~/.local/bin`).
- **Workspace**: `/home/vibecoder/Projects` (Version controlled via Git).
- **Active Tmux Session**: `gemini` (Preserved for persistent background jobs & server processes).

---

## Workspace Tools & Scripts

### 1. [`lyricview`](file:///home/vibecoder/Projects/lyricview)
Native GPU-accelerated fullscreen synced lyrics viewer and standalone music player (PySide6 / Qt Quick).
- **Execution**:
  - Windowed mode: `./lyricview --windowed`
  - Low-spec GPU mode *(recommended for Intel HD graphics)*: `./lyricview --lite`
  - Play local library directly: `./lyricview --own`
  - Follow specific player: `./lyricview -p lollypop`
- **Key Shortcuts**:
  - `Space`: Play / Pause
  - `←` / `→`: Seek ±5s
  - `N` / `P`: Next / Previous track
  - `[` / `]`: Adjust lyric offset ±100ms
  - `,` / `.`: Adjust word timing spread
  - `F`: Toggle Fullscreen | `Q`: Quit
- **Dependencies**: `pyside6`, `playerctl`, `python-gobject`, `python-mutagen` (optional).

### 2. [`lyricview-web`](file:///home/vibecoder/Projects/lyricview-web)
Browser-based alternative serving MPRIS lyrics over HTTP.
- **Execution**:
  - Standard launcher: `./lyricview-web`
  - Headless server mode *(for remote devices)*: `./lyricview-web --no-browser --port 8765`
- **Use Case**: Wireless streaming & lyrics display on mobile/tablet (e.g., Android tablet tunneled over Tailscale).

### 3. [`musicD`](file:///home/vibecoder/Projects/musicD)
High-accuracy music downloader and metadata/lyrics tagger (YouTube Music & iTunes backend).
- **Commands**:
  - Single song: `./musicD song "<title> - <artist>"`
  - Album / Playlist: `./musicD album "<url>"`
  - Batch upgrade lyrics: `./musicD lyrics ~/Music`
- **Storage Location**: Defaults to `~/Music` (or `$MUSICD_DIR`).

---

## Development & Collaboration Rules

1. **Git Tracking**:
   - Always verify `git status` before and after modifying codebase files.
   - Commit logical milestones with clear messages.
2. **Persistent Background Tasks (tmux)**:
   - Run servers (like `lyricview-web` or test servers) inside the persistent tmux session:
     ```bash
     tmux send-keys -t gemini "<command>" C-m
     ```
   - Attach anytime: `tmux attach -t gemini`.
3. **Hardware Considerations**:
   - Keep memory usage lean (4 GB RAM available).
   - Avoid unbounded background processes and use `--lite` flags when testing graphic shaders.
4. **Task Tracking**:
   - Refer to [TODO.md](file:///home/vibecoder/Projects/TODO.md) for pending development tasks, window manager configs, and gaming fixes.
