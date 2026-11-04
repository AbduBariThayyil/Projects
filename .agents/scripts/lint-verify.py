#!/usr/bin/env python3
"""
PostToolUse Hook: Runs structural AST/syntax validation immediately after file modifications.
Enforces rule: 'Verify changed files via structural ast/lint checks immediately after the first edit.'
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")
        return

    tool_call = payload.get("toolCall", {})
    tool_args = tool_call.get("args", {})
    target_path_str = tool_args.get("Path", "")

    if not target_path_str:
        print("{}")
        return

    path = Path(target_path_str)
    if not path.exists():
        print("{}")
        return

    suffix = path.suffix.lower()
    # Python AST validation
    if suffix == ".py":
        try:
            subprocess.run(["python3", "-m", "py_compile", str(path)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"\n[Syntax Error] Python compilation failed for {path.name}:\n{e.stderr}\n")

    # Shell script validation
    elif suffix == ".sh" or path.name in ("ani-cast", "ani-cast-menu", "mpv-chromecast", "LyricViewLauncher"):
        try:
            subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"\n[Syntax Error] Bash syntax check failed for {path.name}:\n{e.stderr}\n")

    # JSON validation
    elif suffix == ".json":
        try:
            with open(path, "r") as f:
                json.load(f)
        except Exception as e:
            sys.stderr.write(f"\n[Syntax Error] JSON syntax check failed for {path.name}:\n{e}\n")

    # C source validation
    elif suffix in (".c", ".h"):
        # Run clang or gcc syntax-only if available
        try:
            subprocess.run(["gcc", "-fsyntax-only", "-Wall", str(path)], capture_output=True, text=True)
        except Exception:
            pass

    print("{}")

if __name__ == "__main__":
    main()
