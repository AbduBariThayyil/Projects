#!/usr/bin/env python3
"""
Journal & Memory Manager for Cross-Chat Continuity.
Allows different chat sessions to read and update shared memory without context bloat.
"""

import sys
import os
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BRAIN_DIR = BASE_DIR / "brain"
JOURNAL_MD = BRAIN_DIR / "journal.md"
MEMORY_JSON = BRAIN_DIR / "memory.json"


def read_memory():
    if not MEMORY_JSON.exists():
        return {
            "last_updated": time.time(),
            "recent_tasks": [],
            "known_quirks": {}
        }
    try:
        with open(MEMORY_JSON, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_updated": time.time(), "recent_tasks": [], "known_quirks": {}}


def write_memory(data):
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = time.time()
    tmp_file = MEMORY_JSON.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, MEMORY_JSON)


def cmd_log_task(project, summary):
    mem = read_memory()
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project": project,
        "summary": summary
    }
    mem["recent_tasks"].append(entry)
    # Keep only the last 20 tasks to avoid memory bloat
    mem["recent_tasks"] = mem["recent_tasks"][-20:]
    write_memory(mem)

    # Append to journal.md if exists
    if JOURNAL_MD.exists():
        with open(JOURNAL_MD, "a") as f:
            f.write(f"\n- **{entry['timestamp']}** `[{project}]`: {summary}")
    print(f"[Journal] Logged task for {project}: {summary}")


def cmd_session_init():
    """Generates the payload for Antigravity SessionStart hook."""
    mem = read_memory()
    recent = mem.get("recent_tasks", [])[-3:]
    summary_lines = []
    if recent:
        summary_lines.append("Recent tasks completed in prior sessions:")
        for t in recent:
            summary_lines.append(f"• [{t.get('project')}] {t.get('summary')}")
    else:
        summary_lines.append("Shared brain initialized. All 11 project contexts indexed.")

    msg = (
        "🧠 **Shared Brain Active Across Sessions**\n"
        + "\n".join(summary_lines)
        + "\n\n*Orchestrator Rules Active:* Progressive context routing, dynamic subagent sizing, zero-token hooks, and clarification-first guardrails."
    )

    output = {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": msg
                }
            }
        ]
    }
    print(json.dumps(output))


def cmd_get_summary():
    mem = read_memory()
    recent = mem.get("recent_tasks", [])[-5:]
    if not recent:
        print("No recent tasks recorded in memory.")
        return
    for t in recent:
        print(f"[{t.get('timestamp')}] ({t.get('project')}): {t.get('summary')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: journal.py <session-init|log-task|get-summary> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "session-init":
        cmd_session_init()
    elif cmd == "log-task" and len(sys.argv) >= 4:
        cmd_log_task(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "get-summary":
        cmd_get_summary()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
