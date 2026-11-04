---
name: systemd-rtc-timers
description: >-
  Use when configuring systemd user services, timers, RTC wake alarms, and ACPI suspend-wake synchronization.
---

# Systemd RTC Wake & Timers Runbook

Use this skill when managing scheduled jobs, alarms, or wake-from-suspend events (such as `sys-alarm`).

## Core Configuration & Guidelines

1. **Systemd User Timer with WakeSystem**:
   - Location: `~/.config/systemd/user/<unit>.timer`
   - Unit spec:
     ```ini
     [Unit]
     Description=Wake system for alarm
     
     [Timer]
     OnCalendar=*-*-* 04:00:00
     WakeSystem=true
     Persistent=true
     
     [Install]
     WantedBy=timers.target
     ```

2. **Direct Hardware RTC Synchronization**:
   - Direct RTC wakealarm fallback:
     ```bash
     echo 0 > /sys/class/rtc/rtc0/wakealarm
     echo <epoch_seconds> > /sys/class/rtc/rtc0/wakealarm
     ```
   - Verify active wakealarm:
     ```bash
     cat /proc/driver/rtc | grep -i alarm
     ```

3. **Reloading User Units**:
   - Reload and enable:
     ```bash
     systemctl --user daemon-reload
     systemctl --user restart <unit>.timer
     systemctl --user list-timers
     ```
