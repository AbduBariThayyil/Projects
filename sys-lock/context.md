# Context: sys-lock (Instant native PAM-authenticated screen locker with concurrent fingerprint unlock and Catppuccin UI)

## Overview
`sys-lock` is a high-performance, native C99 PAM-authenticated screen locker engineered for Arch Linux and BSPWM on the Toshiba Portege R700. It replaces the legacy `i3lock` + `maim` + `magick` shell script pipeline with wire-speed in-memory rendering, simultaneous biometric fingerprint authentication via `fprintd` D-Bus, and a Catppuccin Mocha aesthetic.

## Architecture & Technology
- **Stack**: C99, X11 (`Xlib`, `Xrandr`, `Xinerama`, `Xext`/`XShm`), Cairo, Pango / PangoCairo, GIO 2.0 (D-Bus), PAM (`libpam`), GdkPixbuf
- **Compiler Flags**: `-O2 -Wall -Wextra -Wpedantic -std=c99`
- **Binary Target**: `/home/vibecoder/.local/bin/sys-lock`

## Core Modules & Design Pattern
1. **Window Management & Input Grab (`grab.c` / `grab.h`)**:
   - Queries multi-head bounds via Xinerama/XRandR.
   - Creates an override-redirect fullscreen window covering all displays.
   - Acquires exclusive keyboard and pointer grabs via retry loop (100 iterations x 10ms).
   - Generates an invisible 1x1 bitmap cursor to prevent distracting mouse cursors while locked.
2. **Wire-Speed In-Memory Blur (`blur.c` / `blur.h`)**:
   - Captures root window directly via MIT-SHM (`XShmGetImage`) with fallback to `XGetImage`.
   - 4x downsampling followed by a 3-pass horizontal + vertical 1D box blur using sliding window accumulators ($O(1)$ per pixel).
   - Executes in < 5ms on CPU with zero external processes or temporary files on disk.
   - Scales back up using Cairo bilinear interpolation with Catppuccin Mocha dark overlay (`rgba(30, 30, 46, 0.70)`).
3. **Wallpaper & Rice Integration (`wallpaper.c` / `wallpaper.h`)**:
   - `--rice`: Dynamically reads `~/.config/bspwm/.rice`, checks `~/.config/bspwm/rices/<rice>/walls` or `~/.fehbg`.
   - `--wallpaper <path>`: Directly scales and paints any image file via GdkPixbuf and Cairo.
   - `--dark`: Solid `#1e1e2e` Catppuccin Mocha canvas.
4. **Catppuccin Mocha UI (`ui.c` / `ui.h`)**:
   - Digital Clock: Large bold JetBrainsMono NF font (`%H:%M`).
   - Date: Subtitle `%A, %B %d`.
   - Battery: Live direct sysfs query (`/sys/class/power_supply/BAT1/capacity` & `status`) with adaptive Nerd Font glyphs (`󰂄`, `󰁹` .. `󰁺`).
   - Password Indicator: Animated filled circles in Mauve (`#cba6f7`) with Lavender glow ring (`#b4befe`).
   - Visual Shake Feedback: Smooth decaying sinusoidal shake on failed authentication ($\pm 18\text{px}$ over 350ms at 60 FPS).
5. **Concurrent Authentication**:
   - **PAM Password Authentication (`auth_pam.c` / `auth_pam.h`)**:
     - Executes in detached background `pthread` against `i3lock` PAM service with fallback to `system-local-login`.
     - Zeroes sensitive password memory with `explicit_bzero` immediately after handoff.
   - **Concurrent Biometric Fingerprint (`auth_fprint.c` / `auth_fprint.h`)**:
     - Connects to system D-Bus (`net.reactivated.Fprint.Manager` / `/net/reactivated/Fprint/Device/0`).
     - Auto-claims device and calls `VerifyStart("any")`.
     - Subscribes to `VerifyStatus(result, done)` signal. Instant unlock on `"verify-match"`.
     - Automatically restarts verification on non-matching or swipe errors (`"verify-swipe-too-short"`, `"verify-finger-not-centered"`).
     - Releases device cleanly on exit.
6. **Hotkeys Support**:
   - Allows volume (`XF86AudioRaiseVolume`, `XF86AudioLowerVolume`, `XF86AudioMute`), brightness (`XF86MonBrightnessUp`, `XF86MonBrightnessDown`), and media playback (`XF86AudioPlay`, `XF86AudioNext`, `XF86AudioPrev`) while locked without requiring password input.

## Commands & Build
```bash
# Build
make

# Run unit & headless integration test suite
make test

# Install to ~/.local/bin/sys-lock
make install

# Lock commands
sys-lock                    # Instant in-memory blurred desktop (default)
sys-lock --blur             # Explicit blur mode
sys-lock --rice             # Lock with current rice wallpaper
sys-lock --wallpaper <file> # Lock with custom wallpaper
sys-lock --dark             # Solid Catppuccin Mocha background
sys-lock --test             # Headless verification run
```
