# Context: sys-launcher (High-Performance Native C/GTK3 Application Launcher & Toggler)

## Overview
**sys-launcher** is an ultra-fast, native C99/GTK3 application launcher and desktop visibility manager engineered to replace slow shell/Python script launchers (e.g., `OpenApps --menu` and `OpenApps --apptoggle`). It unifies the primary application launcher (`<super> + <space>`) and desktop visibility toggler (`<shift> + <super> + <space>`) into a single, cohesive, sub-millisecond binary.

## Architecture & Technology
- **Language & Libraries**: C99 with `gtk+-3.0`, `glib-2.0`, `gio-2.0`, and `gio-unix-2.0`.
- **Instant Application Indexing**: Directly leverages `g_app_info_get_all()` from GIO (zero Python startup latency, cached lowercase lookup for instantaneous multi-token fuzzy and substring filtering).
- **Window Geometry & Behavior**:
  - Frameless (`gtk_window_set_decorated(..., FALSE)`).
  - Centered on active monitor under pointer (`gdk_seat_get_pointer` + `gdk_display_get_monitor_at_point`).
  - Dimensions: 480px width × 420px height.
  - Skips taskbars and pagers (`gtk_window_set_skip_taskbar_hint(..., TRUE)`, `gtk_window_set_skip_pager_hint(..., TRUE)`).
  - RGBA visual support for rounded corners with compositor transparency (`picom`).
- **Frecency / Launch Count Ranking**:
  - Usage tracked in `~/.cache/sys-launcher/frecency.txt` (`<desktop_id> <count>\n`).
  - Empty queries rank by most frequently used applications first, with alphabetical tie-breaking.
  - Active search queries add a frecency bonus (`+ count * 150`, capped at 6000) into relevance scoring.
- **Dedicated Shell Command Execution (`!` or `>` prefix)**:
  - Entering `!<cmd>` or `><cmd>` displays a custom execution row ("Execute: <command>", "Run in system shell").
  - Activating launches asynchronously via `/bin/sh -c '<command>'` and terminates launcher cleanly.
- **Styling**:
  - Embedded CSS provider adhering to Catppuccin Mocha & Dracula palette.
  - JetBrainsMono Nerd Font typography.
  - Native 32×32 application icons rendered via `GtkImage` (`g_app_info_get_icon` with fallback to `application-x-executable`).

## Dual Modes

### Mode 1: App Launcher (Default: `sys-launcher`)
- Bound to: `<super> + <space>` (via `sys-control --menu`).
- Displays visible applications (`g_app_info_should_show() == TRUE`).
- Real-time search query filtering and weighted relevance ranking.
- **Controls**:
  - `<Up>` / `<Down>` or `<Ctrl+P>` / `<Ctrl+N>`: Navigate results list.
  - `<Enter>`: Launches selected application via `g_app_info_launch()` with proper `GdkAppLaunchContext` and immediately terminates.
  - `<Tab>`: Hides selected application from the launcher (`NoDisplay=true` in `~/.local/share/applications/<id>.desktop`), fires visual notification via `sys-notif`, updates desktop database, and dynamically filters out the row.
  - `<Escape>`: Closes launcher immediately.

### Mode 2: App Toggle Manager (`sys-launcher --toggle`)
- Bound to: `<shift> + <super> + <space>` (via `sys-control --apptoggle`).
- Lists **all** desktop applications installed on the system (both visible and hidden).
- Displays color-coded Nerd Font visibility badges (`󰈈 Visible` in `#50fa7b` green, `󰈉 Hidden` in `#ff5555` red).
- **Controls**:
  - `<Enter>` or `<Space>`: Toggles `NoDisplay` in `~/.local/share/applications/<id>.desktop`, updates `update-desktop-database` in background, and updates row badge state instantly in the UI.
  - `<Escape>`: Closes window.

## Desktop Entry Shadowing Logic
When toggling application visibility:
1. **Hiding an app**:
   - If user copy exists in `~/.local/share/applications/`, sets `NoDisplay=true`.
   - If only system copy exists in `/usr/share/applications/`, shadows it by copying to `~/.local/share/applications/` and setting `NoDisplay=true`.
2. **Unhiding an app**:
   - If user copy was purely created to shadow a system application (identical lines except `NoDisplay`), cleanly unlinks the user copy.
   - If user copy has custom modifications or system file is hidden by default, sets `NoDisplay=false`.
3. Triggers background asynchronous `update-desktop-database ~/.local/share/applications`.

## CLI Usage
```bash
# Launch application menu
sys-launcher

# Launch application visibility toggler
sys-launcher --toggle

# Display help and version
sys-launcher --help
sys-launcher --version
```

## Compilation & Installation
```bash
cd /home/vibecoder/Projects/sys-launcher
make
make install
```
Installed to: `~/.local/bin/sys-launcher`
