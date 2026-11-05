# Context: sys-polkit (Ultra-lightweight native Polkit authentication agent (<2MB RSS) with Catppuccin dialog)

## Overview
**sys-polkit** is an ultra-lightweight, high-performance native PolicyKit authentication agent engineered in C for Arch Linux and BSPWM. It completely replaces the heavy `polkit-gnome` (~23 MB RSS) and the shell-spawning `cmd-polkit-agent` + `jq` + `rofi` script with an event-driven native C agent consuming **< 2 MB RAM** idle and 0% CPU.

## Architecture & Technology
- **Stack**: C11, `polkit-agent-1` / `polkit-gobject-1`, `gtk+-3.0`, `gio-2.0`, `glib-2.0`, Cairo.
- **Design Pattern**:
  - `SysPolkitListener`: GObject subclass implementing `PolkitAgentListener` interface.
  - Registers session agent with Polkit Authority on the system D-Bus bus via `polkit_agent_listener_register()`.
  - Lazy GTK initialization: Sits idle in GLib's `g_main_loop_run()` waiting for Polkit Authority events with minimal anonymous memory (~1.7 MB).
  - On `initiate_authentication`: Dynamically spawns a centered, floating Catppuccin Mocha modal dialog.
  - Event-driven PAM exchange via `PolkitAgentSession` (`request`, `show-error`, `show-info`, `completed` signals).
  - Multi-identity support: Detects multiple administrative users and provides clean identity selection, defaulting intelligently to the active session user.
  - Automatic error retry: On invalid credentials, highlights error in Catppuccin Red (`#f38ba8`), clears entry, and re-initiates session for instant retry without dismissing dialog.
  - Immediate memory cleanup: Calls `malloc_trim(0)` upon dialog destruction and request completion to keep RSS minimal.

## Styling & Desktop Integration
- **Theme**: Catppuccin Mocha (Base `#1e1e2e`, Mantle `#181825`, Mauve `#cba6f7`, Blue `#89b4fa`, Red `#f38ba8`).
- **BSPWM Rules**: `bspc rule -a sys-polkit state=floating center=true layer=above`.
- **Systemd Service**: `~/.config/systemd/user/sys-polkit.service` enabled under `graphical-session.target`.

## Commands & Build
```bash
# Build binary
make

# Run headless unit tests with xvfb-run
make test

# Install binary to ~/.local/bin/sys-polkit
make install

# Clean build artifacts
make clean

# Test dialog UI directly
sys-polkit --test-dialog

# Service status
systemctl --user status sys-polkit.service
```
