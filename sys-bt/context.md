# Context: sys-bt (Smart On-Demand Bluetooth Manager & Power Daemon)

## Overview
**sys-bt** is an event-driven, native C Bluetooth power manager and control stack engineered specifically for Arch Linux, BSPWM, and the Toshiba Portégé R700 ("Arch Xiao"). It eliminates wasteful 24/7 background Bluetooth radio polling, kernel wakeups, and battery drain by implementing on-demand radio activation and automatic inactivity powerdown after 5 minutes of disconnected idle time.

## Architecture & Technology
- **Language**: C (C11 standard, compiled with `-O2 -Wall -Wextra -Wpedantic`).
- **D-Bus Integration**: Native GLib / GIO D-Bus (`gio-2.0`, `glib-2.0`) communicating with BlueZ (`org.bluez`).
- **Zero-Polling Event Loop**: 100% `GMainLoop` epoll wait with zero CPU wakeups during idle.
- **RFKill Management**: Fine-grained hardware soft-blocking targeting HCI kernel interfaces (`hci*`) to avoid ACPI USB power rail thrashing on Toshiba laptops.
- **Desktop Notifications**: Native asynchronous desktop notifications via `sys-notif` (`notify-send`).
- **System Integration**: Systemd user daemon (`sys-bt.service`), Polybar module (`sys-bt polybar`), Rofi interactive connection menu (`sys-bt menu`), and BSPWM `sys-control --bluetooth`.

## Binary Target & Service
- Binary: `/home/vibecoder/.local/bin/sys-bt`
- Service: `~/.config/systemd/user/sys-bt.service`
- State File: `/run/user/1000/sys-bt.json`

## CLI Subcommands
```bash
# Power Controls
sys-bt on                            # Unblock rfkill, power on BlueZ adapter, emit notification
sys-bt off                           # Power off adapter, soft-block rfkill, emit notification
sys-bt toggle                        # Instantly toggle Bluetooth power state

# Status & Polybar
sys-bt status                        # Display human-readable status table
sys-bt status --json                 # Output structured JSON status
sys-bt polybar                       # Formatted status glyph/color string for Polybar (<2ms execution)

# Interactive Menu
sys-bt menu                          # 1-click Rofi connection/pairing and discovery menu

# Daemon Execution
sys-bt daemon                        # Run event-driven background powerdown daemon (default: 300s)
sys-bt daemon -t <seconds>           # Run daemon with custom inactivity timeout
```

## Auto-Powerdown Lifecycle
1. Daemon subscribes to BlueZ D-Bus signals:
   - `PropertiesChanged` on `org.bluez.Device1` (tracks `Connected` state)
   - `PropertiesChanged` on `org.bluez.Adapter1` (tracks `Powered` state)
   - `InterfacesAdded` and `InterfacesRemoved` on `org.freedesktop.DBus.ObjectManager`
2. When all devices disconnect and adapter is powered on:
   - Arms monotonic idle timer (`g_timeout_add_seconds(300, on_idle_timeout, ctx)`).
   - Writes deadline epoch to `/run/user/1000/sys-bt.json`.
   - Leaves process completely asleep in epoll wait (0.0% CPU).
3. If any device connects before timeout:
   - Cancels idle timer immediately.
   - Clears deadline in state file.
4. If timeout expires with 0 connected devices:
   - Calls `org.bluez.Adapter1.Powered = false` via D-Bus.
   - Soft-blocks HCI rfkill.
   - Dispatches desktop notification: `"Bluetooth Powered Off: Turned off radio to conserve battery"`.

## Build & Test
```bash
cd /home/vibecoder/Projects/sys-bt
make clean && make      # Strict build
make test               # Run 18-point unit & integration test suite
make install            # Install binary to ~/.local/bin/sys-bt
```
