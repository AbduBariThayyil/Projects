# Ant Esports GM320 RGB - Native Linux Master Controller

A 100% native Linux application (PySide6 / Qt6) for the **Ant Esports GM320 RGB Gaming Mouse** (Instant Microelectronics, USB VID `0x30fa`, PID `0x1440`). 

Designed with zero web wrappers, zero Electron, near-zero CPU footprint (~0.1%), and a modern dark esports aesthetic tailored for Arch / bspwm / tiling window managers.

---

## Key Features

### 1. Dynamic DPI Builder (No Hardcoded Stages)
- Fully customizable DPI stages: add, delete, or toggle any stage on/off.
- Precise DPI slider & numeric entry from **200 to 12,800 DPI** in 100 DPI steps.
- Per-stage custom RGB color selector with esports presets and custom hex picker.
- Quick preset buttons: FPS (400, 800, 1600), Balanced (800, 1600, 3200), High-Res (1400..8000).

### 2. Interactive 8-Button Mapping
- Interactive mouse diagram with glowing numbered callout badges (1–8).
- Remap all 8 physical buttons: Left Click, Right Click, Middle Click, Forward, Backward, DPI Loop, LED Loop, Rapid Fire, Multimedia (Play/Pause, Next, Prev, Volume, Mute), Desktop, Macro Triggers, or Disabled.
- Rapid Fire tuning: fine-tune burst click delay down to 10 ms.

### 3. Native Audio-Reactive RGB Lighting (Music Sync)
- Built on `libpulse-simple` (PipeWire / PulseAudio) with ctypes—no heavy external audio frameworks.
- Real-time animated 24-band frequency spectrum visualizer and rhythmic beat ripple detector.
- 4 Audio Modes:
  - **Bass Pulse**: Pulses primary lighting with transient flashes on kick drums.
  - **RGB Spectrum**: Frequency bands drive low (Red), mid (Green), and high (Blue) tones.
  - **Neon Tempo Flow**: Audio tempo smoothly accelerates color wheel rotations.
  - **Strobe Beat**: High-energy beat-drop strobe.
- Sensitivity / Audio Gain slider and customizable primary / accent colors.

### 4. Reimagined Macro Engine
- Rock-solid event recorder: records keyboard and mouse events with millisecond-precision timestamps.
- Timeline editor: insert, reorder, delete, and double-click to edit delays.
- Execution modes:
  - Cycle until key released
  - Cycle until key clicked again (toggle)
  - Specified cycle times (repeat count)
- Compiles directly to mouse EEPROM hardware bytecode and provides a live sandbox test area.

### 5. RGB Backlight Control
- Hardware modes: Ambilight (Rainbow Streamer), Breathing, Neon, Static, Single Breath, Comet Tail (Flowing Water), Button Response, DPI Breath, and Off.
- Speed slider (1–10), Brightness (1–5), Direction (Clockwise / Counter-Clockwise), Symmetry toggle.
- 7-Color Custom Spectrum Palette editor.

### 6. Profile Management
- Profiles: `Office`, `Game I`, `Game II`, `Media`, plus unlimited custom profiles.
- Single-click Apply (burns EEPROM in <0.3s) and Cancel.
- Import and Export JSON profiles.
- Factory reset to OEM defaults.

---

## Launching the App

From terminal or rofi/dmenu:
```bash
ant-gm320
```

Desktop entry:
- Shows up under Application menu as **Ant Esports GM320**.
