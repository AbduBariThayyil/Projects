# Architecture & System Suggestions for `lyricview` & Arch Xiao

## 1. Hardware & Performance Optimization (Toshiba Portégé R700 / 4GB RAM)
- **Qt Quick Scene Graph**:
  - We defaulted `QSG_RENDER_LOOP=basic` in `lyricview`. This avoids threaded OpenGL render crashes during VT/TTY console switches on the Intel HD Graphics controller.
  - On 4GB RAM systems, running with `--lite` reduces VRAM texture footprint by disabling the dynamic multi-pass blur and card shadow shaders.
- **Thumbnail Cache Housekeeping**:
  - `~/.cache/lyricview/thumbs` creates 300x300 JPEG thumbnails. Add an automatic LRU prune (similar to `prune_art()`) when the cache exceeds 500 MB to keep disk space lean on the SSD.
- **Process Memory Leaks**:
  - By removing the external player follower mode (`playerctl --follow`), background process spawns are eliminated, saving CPU cycles and preventing zombie processes.

---

## 2. Polybar & BSPWM Integration
- **`PolybarMusic` Permanent Regex Match**:
  - The script in `~/.config/bspwm/bin/PolybarMusic` currently checks:
    ```bash
    [[ ${name,,} =~ lollypop|spotify|mpd ]] || continue
    ```
  - While `lyricview` now defaults to publishing as `lollypop` for instant zero-config compatibility, you can edit line 29 of `PolybarMusic` to natively include `lyricview`:
    ```bash
    [[ ${name,,} =~ lollypop|spotify|mpd|lyricview ]] || continue
    ```
- **BSPWM Scratchpad Hotkey**:
  - To launch `lyricview` as a floating scratchpad in `~/.config/sxhkd/sxhkdrc`:
    ```sxhkd
    super + m
        bspc rule -a lyricview state=floating sticky=on && lyricview --windowed
    ```

---

## 3. Wireless Streaming & Android Tablet Hosting (Tailscale)
- **Headless Server Mode**:
  - Use `lyricview-web` with `--no-browser --port 8765` running inside the persistent tmux session `gemini`:
    ```bash
    tmux send-keys -t gemini "python3 /home/vibecoder/Projects/lyricview-web --no-browser --port 8765" C-m
    ```
- **Tailscale Mesh Access**:
  - Once Tailscale is active on both the Arch laptop and Android tablet, open `http://arch-xiao:8765` in Chrome/Firefox on the Android tablet.
  - The tablet gets a full-screen, responsive, word-by-word synced karaoke player over encrypted peer-to-peer Wi-Fi without needing port forwarding.

---

## 4. Word-by-Word Lyrics (`e lrc`) Pipeline
- **Enhanced LRC Priority**:
  - `lyricview` searches:
    1. Sidecar `.lrc` containing real `<mm:ss.xx>` timestamps.
    2. Embedded tags via mutagen (USLT/SYLT).
    3. NetEase YRC and BetterLyrics TTML word-level APIs via `wl_fetch`.
    4. LRCLIB API fallback.
- **musicD Integration**:
  - When downloading with `musicD`, ensure word-level lyric fetching is enabled so sidecar `.lrc` files are pre-cached and ready for `lyricview`'s Edit and Rain kinetic typography modes.
