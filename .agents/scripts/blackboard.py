#!/usr/bin/env python3
"""
Blackboard Manager for Antigravity Multi-Agent Orchestration.
Maintains active agent states, file locks, and cross-agent coordination.
"""

import sys
import os
import json
import time
import fcntl
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BRAIN_DIR = BASE_DIR / "brain"
BLACKBOARD_FILE = BRAIN_DIR / "blackboard.json"
PROJECTS_FILE = BRAIN_DIR / "projects.json"


def acquire_file_lock(fd):
    fcntl.flock(fd, fcntl.LOCK_EX)


def release_file_lock(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)


def read_blackboard():
    if not BLACKBOARD_FILE.exists():
        return {"active_agents": {}, "file_locks": {}, "session_tasks": []}
    try:
        with open(BLACKBOARD_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"active_agents": {}, "file_locks": {}, "session_tasks": []}


def write_blackboard(data):
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = BLACKBOARD_FILE.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, BLACKBOARD_FILE)


def cmd_register_agent(agent_id, role, project):
    with open(BLACKBOARD_FILE, "r+") if BLACKBOARD_FILE.exists() else open(BLACKBOARD_FILE, "w+") as f:
        acquire_file_lock(f.fileno())
        try:
            bb = read_blackboard()
            bb["active_agents"][agent_id] = {
                "role": role,
                "project": project,
                "registered_at": time.time(),
                "status": "active"
            }
            write_blackboard(bb)
            print(f"[Blackboard] Agent {agent_id} registered for project '{project}' with role '{role}'.")
        finally:
            release_file_lock(f.fileno())


def cmd_unregister_agent(agent_id):
    with open(BLACKBOARD_FILE, "r+") if BLACKBOARD_FILE.exists() else open(BLACKBOARD_FILE, "w+") as f:
        acquire_file_lock(f.fileno())
        try:
            bb = read_blackboard()
            if agent_id in bb["active_agents"]:
                del bb["active_agents"][agent_id]
            # Release all locks held by this agent
            bb["file_locks"] = {
                f: lock for f, lock in bb["file_locks"].items() if lock.get("agent_id") != agent_id
            }
            write_blackboard(bb)
            print(f"[Blackboard] Agent {agent_id} unregistered and all associated locks released.")
        finally:
            release_file_lock(f.fileno())


def cmd_lock(file_path, agent_id):
    resolved = str(Path(file_path).resolve())
    with open(BLACKBOARD_FILE, "r+") if BLACKBOARD_FILE.exists() else open(BLACKBOARD_FILE, "w+") as f:
        acquire_file_lock(f.fileno())
        try:
            bb = read_blackboard()
            existing = bb["file_locks"].get(resolved)
            if existing and existing.get("agent_id") != agent_id:
                print(f"[Conflict] File '{resolved}' is already locked by agent '{existing.get('agent_id')}'.", file=sys.stderr)
                sys.exit(1)
            bb["file_locks"][resolved] = {
                "agent_id": agent_id,
                "locked_at": time.time()
            }
            write_blackboard(bb)
            print(f"[Blackboard] File '{resolved}' locked for agent '{agent_id}'.")
        finally:
            release_file_lock(f.fileno())


def cmd_unlock(file_path, agent_id):
    resolved = str(Path(file_path).resolve())
    with open(BLACKBOARD_FILE, "r+") if BLACKBOARD_FILE.exists() else open(BLACKBOARD_FILE, "w+") as f:
        acquire_file_lock(f.fileno())
        try:
            bb = read_blackboard()
            existing = bb["file_locks"].get(resolved)
            if existing and existing.get("agent_id") == agent_id:
                del bb["file_locks"][resolved]
                write_blackboard(bb)
                print(f"[Blackboard] File '{resolved}' unlocked.")
            else:
                print(f"[Blackboard] File '{resolved}' was not locked by agent '{agent_id}'.")
        finally:
            release_file_lock(f.fileno())


def cmd_check_lock(file_path, agent_id=None):
    resolved = str(Path(file_path).resolve())
    bb = read_blackboard()
    existing = bb["file_locks"].get(resolved)
    if existing:
        locked_by = existing.get("agent_id")
        if agent_id and locked_by == agent_id:
            print("ALLOWED_OWNER")
            sys.exit(0)
        else:
            print(f"LOCKED_BY:{locked_by}")
            sys.exit(2)
    print("UNLOCKED")
    sys.exit(0)


def cmd_status():
    bb = read_blackboard()
    print(json.dumps(bb, indent=2))


def cmd_get_context(project_name):
    if not PROJECTS_FILE.exists():
        print(f"Projects file not found at {PROJECTS_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(PROJECTS_FILE, "r") as f:
        proj_data = json.load(f)
    p = proj_data.get("projects", {}).get(project_name)
    if not p:
        print(f"Project '{project_name}' not recognized. Available: {list(proj_data.get('projects', {}).keys())}", file=sys.stderr)
        sys.exit(1)
    ctx_path = Path(BASE_DIR.parent) / p.get("context", "")
    if ctx_path.exists():
        with open(ctx_path, "r") as f:
            print(f.read())
    else:
        print(f"# Context for {project_name}\n{p.get('description')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: blackboard.py <status|register-agent|unregister-agent|lock|unlock|check-lock|get-context> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
    elif cmd == "register-agent" and len(sys.argv) >= 5:
        cmd_register_agent(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "unregister-agent" and len(sys.argv) >= 3:
        cmd_unregister_agent(sys.argv[2])
    elif cmd == "lock" and len(sys.argv) >= 4:
        cmd_lock(sys.argv[2], sys.argv[3])
    elif cmd == "unlock" and len(sys.argv) >= 4:
        cmd_unlock(sys.argv[2], sys.argv[3])
    elif cmd == "check-lock" and len(sys.argv) >= 3:
        agent_id = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_check_lock(sys.argv[2], agent_id)
    elif cmd == "get-context" and len(sys.argv) >= 3:
        cmd_get_context(sys.argv[2])
    else:
        print(f"Invalid command or arguments: {' '.join(sys.argv)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
