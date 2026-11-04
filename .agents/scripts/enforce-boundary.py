#!/usr/bin/env python3
"""
PreToolUse Hook: Enforces file ownership and project boundaries across agents.
Consumes zero prompt tokens during normal execution.
"""

import sys
import os
import json
from pathlib import Path

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Fallback allow if payload parsing fails
        print(json.dumps({"decision": "allow"}))
        return

    tool_call = payload.get("toolCall", {})
    tool_args = tool_call.get("args", {})
    target_path_str = tool_args.get("Path", "")

    if not target_path_str:
        print(json.dumps({"decision": "allow"}))
        return

    target_path = Path(target_path_str).resolve()
    current_agent = os.environ.get("AGENT_ID")
    assigned_project = os.environ.get("ASSIGNED_PROJECT")

    # Read blackboard
    brain_file = Path(__file__).resolve().parent.parent / "brain" / "blackboard.json"
    if brain_file.exists():
        try:
            with open(brain_file, "r") as f:
                bb = json.load(f)
            
            file_locks = bb.get("file_locks", {})
            target_str = str(target_path)
            
            if target_str in file_locks:
                lock_info = file_locks[target_str]
                lock_owner = lock_info.get("agent_id")
                if current_agent and lock_owner != current_agent:
                    print(json.dumps({
                        "decision": "deny",
                        "reason": f"File '{target_path.name}' is currently locked by agent '{lock_owner}'. Concurrent edits blocked."
                    }))
                    return
        except Exception:
            pass

    # Boundary check if assigned to a specific project
    if assigned_project:
        workspace_root = Path(__file__).resolve().parent.parent.parent
        project_dir = (workspace_root / assigned_project).resolve()
        brain_dir = (workspace_root / ".agents").resolve()

        # Allow edits within assigned project or within .agents brain/scratch
        is_in_project = project_dir in target_path.parents or target_path == project_dir
        is_in_agents = brain_dir in target_path.parents or target_path == brain_dir

        if not (is_in_project or is_in_agents):
            print(json.dumps({
                "decision": "deny",
                "reason": f"Boundary Violation: Agent is restricted to '{assigned_project}'. Modification of '{target_path.name}' outside this boundary is forbidden."
            }))
            return

    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
