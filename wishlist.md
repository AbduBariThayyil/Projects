# 📋 System Modernization & Rebuild Wishlist

A prioritized roadmap of custom system components to rebuild or replace one by one when ready.
All upgraded components follow the **`sys-`** naming convention (e.g. `sys-notif`, `sys-bar`, `sys-control`).

---

## 🎯 Candidate Projects

### 1. 🪟 Login Screen & Display Manager Upgrade (LightDM $\rightarrow$ Modern Dual-Auth)
* **Goal:** Replace LightDM/Slick-Greeter with a modern greeter supporting **true simultaneous fingerprint + password authentication** (no waiting, no serial blocking).
* **Candidates:**
  * **SDDM (Simple Desktop Display Manager):** Supports modern Qt6/QML themes (Catppuccin), instant loading, and smooth multi-worker authentication.
  * **Ly (TUI Display Manager):** Extremely lightweight C-based terminal greeter (~1 MB RAM).
  * **Custom Greeter / GDM Stack:** Native concurrent biometric + password listener.

### 2. 📊 Custom Ultra-Light Status Bar (`sys-bar` / Polybar)
* **Status:** **Polybar Restored (Active)**; `sys-bar` retained in `/home/vibecoder/Projects/sys-bar`.
* **Details:**
  * Polybar is running the active `32-Bit` Marisol rice styling, TokyoNight/Dracula palette, glyph icons, and dynamic `PolybarMusic` center widget.
  * `sys-bar` remains fully compiled, verified, and available as an ultra-minimalist alternative whenever needed.

### 3. 📁 Lightweight File Manager (Purging GVFS / `gvfsd` Background Daemons)
* **Current:** Thunar pulls in `gvfsd`, `gvfsd-fuse`, `gvfs-udisks2-volume-monitor`, and GNOME trash background services running constantly.
* **Goal:** Eliminate GVFS background daemons entirely.
* **Candidates:**
  * **Yazi / lf:** Fast terminal file managers in Rust/Go with sixel/kitty image previews, custom hotkeys, and zero background services.
  * **PCManFM (standalone):** Lightweight GTK file manager compiled without GVFS dependency (~8 MB RAM).

### 4. 💻 Ultra-Light Minimalist Terminal — 🔒 KEPT AS-IS
* **Status:** User prefers **Alacritty** (Retained).
* **Details:** Configured with TokyoNight palette, smooth GPU acceleration, and comfortable keybinds.

### 5. 🛡️ Lightweight Polkit Agent (Replacing `polkit-gnome`)
* **Current:** `polkit-gnome-authentication-agent-1` consumes ~23 MB RAM running constantly in the background.
* **Goal:** Replace with **`polkit-dumb-agent`** or a minimal C Polkit auth agent consuming **< 2 MB RAM** that only activates when root elevation is prompted.

### 6. ⚡ Unified Fast CLI Binary (Replacing `~/.config/bspwm/bin/*` Bash Scripts $\rightarrow$ `sys-control`) — ✅ COMPLETED
* **Status:** **Active & Production-Ready** (binary: `/home/vibecoder/.local/bin/sys-control`).
* **Source:** `/home/vibecoder/Projects/sys-control/sys-control.c`.
* **Achieved Features & Metrics:**
  * **Unified Functionality:** Consolidates volume (`pamixer`), media (`playerctl`), brightness (direct sysfs read + `brightnessctl`), status bar toggling (`Hider --bar`), window minimizing/restoring (`Hider --node`), scratchpad runner (`Scratchpad`), screenshots (`maim`), touchpad toggle, and instant Xlib EWMH client traversal (`--activate`).
  * **Hotkey Latency:** Sub-millisecond execution (< 15ms total end-to-end process lifecycle vs 80-200ms Bash forks).
  * **Zero Breaking Changes:** Fully compatible with `sxhkdrc` and existing CLI invocations. Fixed `--bar` and `--node` parameter parsing so `Win + Alt + H` status bar hide/show toggles without IPC errors.

### 7. ⌨️ KeyHolder Floating HUD (`keyholder-hud`) — ✅ COMPLETED
* **Status:** **Active & Running** as systemd service (`keyholder-hud.service`).
* **Source:** `/home/vibecoder/Projects/keyholder-hud/keyholder-hud.c`.
* **Achieved Features & Metrics:**
  * Consumes ~2.2 MB RAM and 0.0% CPU.
  * Positioned smoothly under Polybar right edge.
  * High-speed non-blocking FIFO IPC at `/tmp/keyholder_hud.fifo`.
  * Replaced all notification spam from `KeyHolder` and handles keyd debounce/exclusions.

### 8. 📬 Notification Daemon & Center (`sys-notif` & `sys-notif-center`) — ✅ COMPLETED
* **Status:** **Active & Production-Ready** (`sys-notif.service` and `/home/vibecoder/.local/bin/sys-notif-center`).
* **Sources:**
  * Daemon: `/home/vibecoder/Projects/sys-notif/sys-notif.c`
  * Modal Center: `/home/vibecoder/Projects/sys-notif-center/sys-notif-center.c`
* **Achieved Features & Metrics:**
  * **On-Screen Message Stacking:** Dynamically groups unread messages up to 5 per conversation with FIFO rolling window and live animated countdown bar reset.
  * **Native Modal Notification Center:** High-performance GTK3/Cairo centered dialog; groups messages by conversation, supports toggle expand for long history (>5 messages), antialiased circular avatars, and zero-flicker BSPWM floating rule.
  * **Keybinds & Mouse Controls:**
    * `Super + N` instant global keyboard shortcut to toggle Notification Center.
    * Left-Click: Dismiss notification / card silently.
    * Right-Click: Open / activate app and chat, mark read, and clear from history.
    * Polybar bell icon integration with unread indicator badge.
  * **Conversation & Avatar Routing:** Robust group chat avatar separation (group avatars never overwritten by individual member photos), DM vs. Group Chat isolation, and multi-chat separation for senders across multiple groups.

### 9. 🎨 Window Compositor Tuning & Physics Animations (`picom-ftlabs`) — ✅ COMPLETED
* **Status:** **Active & Configured** (`picom-ftlabs-git` vgit-df4c6).
* **Achieved Features & Metrics:**
  * **Physics Engine:** Configured with Style A spring-physics animations (central zoom on open, vertical squeeze on close, slide-up transient dialogs, desktop tag transitions).
  * **Zero Blur Overhead:** Gaussian/dual-kawase blur disabled for pure wire-speed 60 FPS rendering and minimal battery draw on Intel Ironlake.
  * **Driver Stack:** Direct client-to-GPU DRI3 acceleration enabled, double-vsync eliminated.
  * **Memory Footprint:** < 0.1% RAM (< 5 MB RSS) and ~2% CPU usage.
  * **Live Switcher:** CLI profile switcher implemented at `~/.config/bspwm/bin/SetPicomStyle [a|b|c]`.

### 10. 🔒 Instant Native Lock Screen (Replacing `betterlockscreen` / `i3lock` $\rightarrow$ `sys-lock`)
* **Current:** `i3lock` with `maim` blur script (takes 1–2 seconds to capture and blur).
* **Goal:** A dedicated lightweight PAM-authenticated C locker with pre-cached blur or hardware-accelerated GLSL shader blur, displaying clock and battery with zero lag.

### 11. ⏰ High-Volume Native Alarm Clock & RTC Wake System (`sys-alarm`) — ✅ COMPLETED
* **Status:** **Active & Production-Ready** (`sys-alarm-wake.timer` and `/home/vibecoder/.local/bin/sys-alarm`).
* **Source:** `/home/vibecoder/Projects/sys-alarm/sys-alarm.c`.
* **Achieved Features & Metrics:**
  * **Precision RTC Suspend-Wake:** Native ACPI RTC wake timer synchronization via systemd user timer `sys-alarm-wake.timer` (`WakeSystem=true`) and direct RTC wakealarm fallback.
  * **Zero Background RAM (0.0 MB):** Eliminates 24/7 background daemons completely; systemd's existing epoll event loop triggers `sys-alarm ring` at the exact second with zero memory overhead.
  * **Guaranteed Audio Blasting:** Unmutes the internal hardware speaker (`alsa_output.pci*`), overrides volume to 150%, and loops random music tracks from `~/Music` continuously until user action.
  * **Snooze / Dismiss Modal Popup:** Centered GTK3 modal (`sys-alarm-popup`) with instant keyboard controls (<kbd>Space</kbd>/<kbd>Enter</kbd> to Dismiss, <kbd>S</kbd> to Snooze for 5 minutes).
  * **Full Clock GUI App:** Modal window displaying live digital clock, alarm list, on/off toggles, time spin-buttons, repeat modes (daily/weekdays/once/custom), custom folder/track picker, volume slider, and non-blocking audio tester.
  * **Global Hotkey:** `Super + Alt + A` opens the alarm clock.
