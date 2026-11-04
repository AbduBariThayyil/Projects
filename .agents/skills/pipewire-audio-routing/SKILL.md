---
name: pipewire-audio-routing
description: >-
  Use when interacting with PipeWire, PulseAudio, pactl, or MPV for audio playback, sink routing,
  and hardware speaker unmuting (e.g., in sys-alarm or audio tools).
---

# PipeWire & PulseAudio Routing Runbook

Use this skill when handling audio streaming, volume control, or hardware speaker routing across Arch Linux desktop tools.

## Key Procedures

1. **Hardware Speaker Introspection**:
   - Query available sinks via `pactl`:
     ```bash
     pactl list sinks short
     ```
   - Identify internal laptop speakers by filtering for `alsa_output.pci*` with `device.form_factor = "internal"`.

2. **Volume Override & Unmuting**:
   - In alarm or critical notifications, ensure audio overrides current mute status:
     ```bash
     pactl set-sink-mute <sink_id> 0
     pactl set-sink-volume <sink_id> 150%
     ```

3. **MPV Dedicated Sink Playback**:
   - Direct audio playback explicitly to a specific hardware sink without disrupting default user audio:
     ```bash
     mpv --no-video --audio-device=pulse/<sink_name> --volume=150 /path/to/sound.mp3
     ```
