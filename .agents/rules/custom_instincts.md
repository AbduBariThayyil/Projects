# Execution Guardrails
- Verify changed files via structural ast/lint checks immediately after the first edit.
- Zero-Polling & Event-Driven Architecture: Always design system monitors, daemons, and tools with zero CPU polling (e.g., listen to kernel uevents, UPower/system D-Bus signals, or X11 socket events instead of sleep loops). Eliminate constant idle background activities.
- If an automated fix fails twice consecutively, halt background execution and surface the diff overview immediately.
- Proactively prompt with clarification questions whenever behavior parameters are ambiguous; do not assume unlikely implementation traits.
- Verify the fix took place by live testing, but ensure it does not cover the user's screen or interrupt fullscreen workflows (e.g., execute in another desktop workspace, run headless via `xvfb-run`, or run in the background).
