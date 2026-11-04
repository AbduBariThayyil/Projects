---
name: linux-desktop-c-gtk
description: >-
  Use when developing, modifying, or debugging native C applications using X11, GTK3, Cairo, or Pango
  in the Arch Linux / BSPWM desktop environment.
---

# Linux Desktop C & GTK3 / X11 Development Runbook

Use this skill when working on native C projects in this repository (`keyholder-hud`, `polybar-music`, `sys-alarm`, `sys-control`, `sys-notif`, `xmodmap-watcher`).

## Standards & Best Practices

1. **Compilation & Compiler Flags**:
   - Always use `-O2 -Wall -Wextra -Wpedantic` for production builds.
   - Use `pkg-config --cflags --libs <packages>` in Makefiles.
   - For GTK3: `pkg-config --cflags --libs gtk+-3.0 glib-2.0 x11 cairo pango`.

2. **X11 & Event Loops**:
   - Zero-latency event processing: Avoid busy-waiting loops. Always use blocking event queues with timeout or `select()`/`poll()` on the X11 connection socket (`ConnectionNumber(display)`).
   - Rate-limiting / Debounce: When handling hotplug or window state events, debounce with `clock_gettime(CLOCK_MONOTONIC)` to prevent high CPU spikes.

3. **Memory Safety & Leaks**:
   - When modifying C code, ensure every `malloc` / `calloc` / `strdup` / `XGetModifierMapping` is paired with its appropriate free function (`free`, `XFreeModifiermap`, `g_free`, `cairo_destroy`).
   - Run memory checks headlessly:
     ```bash
     valgrind --leak-check=full --error-exitcode=1 ./<binary> --test
     ```

4. **Desktop Aesthetics**:
   - Follow Catppuccin Mocha / TokyoNight dark palette styling.
   - For GTK3, use CSS providers (`GtkCssProvider`) loaded via `gtk_style_context_add_provider_for_screen`.
