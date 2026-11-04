---
name: orchestrator-dispatch
description: >-
  Use when planning and delegating tasks from the main smart terminal to specialized subagents.
  Handles project context routing, dynamic model tiering, file locking, and conflict prevention.
---

# Smart Terminal Orchestrator Dispatch Protocol

As the primary terminal session in `/home/vibecoder/Projects`, your role is to act as the **Smart Terminal Orchestrator**. You coordinate tasks, maintain the global brain, and dispatch concrete coding or debugging tasks to subagents.

## Core Dispatch Workflow

1. **Identify the Target Subproject**:
   - Check `.agents/brain/projects.json` to find which subproject matches the user's request.
   - If ambiguous or touching multiple domains unexpectedly, **ask the user clarifying questions first**.

2. **Retrieve Scoped Context on Demand (Zero Bloat)**:
   - Run `python3 .agents/scripts/blackboard.py get-context <project_name>` or read `<project_name>/context.md`.
   - **Never inject unneeded project contexts into the prompt.** Subagents receive only the context relevant to their mission.

3. **Select the Optimal Model Tier**:
   - **`flash`**: Use for simple syntax checks, lightweight linting, formatting, minor typo fixes, or isolated test runs.
   - **`inherit`** (Gemini 3.8 Flash High): Use for standard feature implementation, refactoring, and general coding.
   - **`pro`**: Use for deep algorithmic work, complex C pointer/memory debugging, architectural designs, or intricate race conditions.

4. **Acquire Locks & Spawn Subagent**:
   - Register the subagent on the blackboard:
     `python3 .agents/scripts/blackboard.py register-agent <subagent_id> <role> <project>`
   - Pass the scoped context and explicit boundaries to the subagent via `invoke_subagent`.
   - Workspace mode: Use `Workspace: 'inherit'` with active file locking.

5. **Coordinate & Close**:
   - Collect the subagent's summary/diff.
   - Run structural AST/syntax validation and verify live testing requirements.
   - Unregister agent and release file locks:
     `python3 .agents/scripts/blackboard.py unregister-agent <subagent_id>`
   - Auto-commit and auto-push to `origin master`.
