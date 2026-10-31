# Context: Toshiba Portégé R700 ("Arch Xiao" System Guide)

## Overview
This directory contains the core hardware specifications, system architecture, and desktop environment configurations for the host laptop (**Toshiba Portégé R700** / "Arch Xiao").

## Hardware Specifications
- **CPU**: Intel Core i5 / i3 (x86_64 architecture).
- **RAM**: 4 GB Physical RAM (3.6 GiB usable).
  - High-priority ZRAM partition (`/dev/zram0`, 1.8 GB).
  - Secondary fallback swapfile (`/swapfile`, 4.0 GB).
- **Storage**: 250 GB SSD (`/dev/sda`).
  - `/dev/sda1`: Live Boot partition (15.3 GB).
  - `/dev/sda3`: Main Arch Linux root filesystem (208.3 GB, UUID `63c7202b-6b96-4567-b548-b9c0e0f5eccf`).

## Software & Desktop Environment
- **Operating System**: Arch Linux (rolling release, kernel 6.x).
- **Window Manager**: BSPWM (Binary Space Partitioning Window Manager).
  - Dotfiles: Heavily customized `gh0stzk` dotfiles.
  - Configuration path: `~/.config/bspwm/`, `~/.config/bspwm/bin/`, `~/.local/bin/`.
- **Display Server**: X11 (`xorg`).
- **Compositor**: Picom (with GLX/XRender backend).
- **Audio Server**: PipeWire with PulseAudio compatibility layer (`pipewire-pulse`).

## Engineering Guidelines for this Machine
1. **Low-Memory Priority**: With ~1 GB free RAM baseline, avoid Electron apps or heavy IDEs whenever possible. Favor native C binaries (`sys-control`, `sys-notif`, `keyholder-hud`) and terminal tools.
2. **BSPWM Tiling**: All GUI apps should respect BSPWM floating/tiling window rules defined in `~/.config/bspwm/bspwmrc`.
3. **Execution Guardrails**: Tests and commands must run non-intrusively without blocking the screen or interrupting fullscreen sessions.
