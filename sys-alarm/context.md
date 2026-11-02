# Context: sys-alarm (High-Volume Native Alarm Clock & RTC Wake System)

## Overview
**sys-alarm** is a lightweight, dedicated C/GTK3 alarm clock system engineered for Arch Linux and BSPWM. It features multi-alarm scheduling, ACPI RTC suspend-wake synchronization via systemd timers, automated internal speaker detection and 150% volume unmuting, randomized music playback from `~/Music`, and a modal Snooze/Dismiss interface.

## Architecture & Technology
- **Language**: C with GTK3 (`gtk+-3.0`), GLib, `json-glib-1.0`, and Xlib.
- **Styling**: Catppuccin Mocha / TokyoNight CSS styling with semi-transparent rounded borders and JetBrainsMono typography.
- **Audio Engine**: PipeWire/PulseAudio sink introspection via `pactl` with direct playback via `mpv` mapped explicitly to the internal hardware speaker (`alsa_output.pci*` / `device.form_factor = internal`) at 150% volume.
- **Suspend/Sleep Wake**: ACPI RTC wake timer synchronization via systemd user timer `sys-alarm-wake.timer` configured with `WakeSystem=true` and direct `/sys/class/rtc/rtc0/wakealarm` fallback.
- **Configuration**: `~/.config/sys-alarm/config.json`.

## Core Features
1. **Multi-Alarm Scheduling**: Pre-configured with user wake-up times (04:00 AM primary and 04:05 AM backup), supporting daily, weekdays, weekends, or one-off repeats.
2. **Audio Blasting**: Overrides mute, forces volume to 150%, isolates the internal laptop speakers, and continuously loops a randomized track from `~/Music` (or a chosen folder/file).
3. **BSPWM Snooze / Dismiss Modal**: Centered modal popup (`sys-alarm-popup`) with keyboard shortcuts (<kbd>Space</kbd>/<kbd>Enter</kbd> to Dismiss, <kbd>S</kbd> to Snooze for 5 minutes).
4. **Persistent Daemon & Service**: Runs via `sys-alarm.service` in systemd user space.

## Commands
```bash
# Open interactive Clock GUI
sys-alarm

# View active configured alarms and next trigger countdown
sys-alarm list

# Add a new alarm
sys-alarm add 04:00 "Morning Wake Up" daily

# Test audio blast and speaker routing (5s test)
sys-alarm test

# Trigger immediate ring
sys-alarm ring

# Dismiss ringing alarm
sys-alarm dismiss

# Snooze ringing alarm
sys-alarm snooze 5

# Synchronize systemd RTC wake timer
sys-alarm sync
```
