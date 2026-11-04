---
name: tdd-headless-testing
description: >-
  Use when writing unit tests or running live verifications for GUI, C binaries, and system tools
  without interrupting the user's screen or stealing window focus.
---

# Non-Intrusive & Headless Live Testing Runbook

Enforces the core repository guardrail:
*"Verify the fix took place by live testing, but ensure it does not cover the user's screen or interrupt fullscreen workflows."*

## Execution Guidelines

1. **Headless X11 Verification with `xvfb-run`**:
   - For any GUI application (GTK3, Qt, PySide6, Xlib), never launch directly into the user's active display (`:0`).
   - Run under a virtual framebuffer:
     ```bash
     xvfb-run -a -s "-screen 0 1920x1080x24" ./<binary_or_script>
     ```

2. **Automated GUI Smoke Testing**:
   - Start the process in the virtual screen, wait 2-3 seconds to verify initialization and socket binding, then terminate cleanly:
     ```bash
     xvfb-run -a -s "-screen 0 1920x1080x24" timeout 3s ./<binary_or_script>
     ```

3. **Background Daemon Testing**:
   - Run services with stdout/stderr redirected to temporary files in `/tmp` rather than cluttering terminal pipes.
   - Inspect exit code ($?) and logs for errors.
