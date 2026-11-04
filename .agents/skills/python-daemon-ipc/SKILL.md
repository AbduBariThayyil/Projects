---
name: python-daemon-ipc
description: >-
  Use when developing Linux Python daemons, PySide6/Qt6 GUIs, session D-Bus interfaces,
  or socket IPC in projects like ani-cast, ant-gm320, or sys-notif-center.
---

# Python Daemons & D-Bus / IPC Runbook

Use this skill when building or modifying Python applications that interface with system services or desktop window managers.

## Best Practices

1. **PySide6 / Qt6 Minimal Footprint**:
   - Avoid heavy WebEngine components; use native Qt widgets (`QWidget`, `QPainter`).
   - For dark theming, apply CSS stylesheets dynamically via `.setStyleSheet(...)`.
   - Prevent blocking the Qt event loop: delegate I/O, scraping, or network requests to `QThread` or `QThreadPool`.

2. **D-Bus Session Monitoring**:
   - Connect to standard session bus interfaces (MPRIS2, FreeDesktop Notifications) without polling.
   - Use `jeepney` or `dbus-python` with `GLib.MainLoop` for high-performance signal listeners.

3. **Clean Process Lifecycle**:
   - Handle `SIGINT` and `SIGTERM` gracefully.
   - Use atomic PID files or Unix domain sockets in `/tmp` or `$XDG_RUNTIME_DIR` to prevent multiple daemon instances.
