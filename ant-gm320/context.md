# Context: ant-gm320 (Native Linux Gaming Mouse Controller)

## Overview
**ant-gm320** is a 100% native Linux GUI application written in Python (PySide6 / Qt6) to control and configure the **Ant Esports GM320 RGB Gaming Mouse** (Instant Microelectronics OEM chipset, USB VID `0x30fa`, PID `0x1440`).

## Architecture & Technology
- **Framework**: PySide6 (Qt Quick / QML + Qt Widgets), custom dark esports theme designed for BSPWM.
- **Hardware Communication**: Raw HID via `hidapi` / `pyusb`, communicating directly with mouse EEPROM for zero-latency burning (<0.3s).
- **Audio Visualizer**: Native `libpulse-simple` (PulseAudio / PipeWire) binding via ctypes for low-latency music-synced RGB backlighting without heavy external frameworks.
- **Resource Footprint**: Highly optimized for low RAM (~0.1% CPU, minimal memory footprint).

## Key Components
- `ant_gm320/gui/`: Main Qt window, custom sliders, color pickers, and tab controllers.
- `ant_gm320/core/`:
  - `dpi.py`: Dynamic DPI builder supporting arbitrary stages from 200 to 12,800 DPI.
  - `buttons.py`: 8-button interactive remapping (Left, Right, Middle, Forward, Backward, DPI, LED, Rapid Fire, Media, Macros).
  - `lighting.py`: Hardware RGB lighting effects (Ambilight, Breathing, Neon, Static, Comet Tail, etc.).
  - `audio_reactive.py`: Real-time 24-band FFT spectrum analyzer and beat detection driving lighting patterns.
  - `macro.py`: Millisecond-precision keyboard and mouse macro recorder and EEPROM compiler.
  - `profile.py`: Profile manager (`Office`, `Game I`, `Game II`, `Media`, custom JSON export/import).
- `tests/`: Automated unit tests for packet serialization, DPI boundaries, and macro bytecode.

## Build & Run
```bash
# Launch application via portable launcher
ant-gm320
# Or directly from source:
python3 -m ant_gm320.main

# Inspect or install udev rules for non-root hardware access
ant-gm320 --udev
ant-gm320 --install-udev
```
