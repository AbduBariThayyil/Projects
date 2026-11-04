---
name: orchestrator-dispatch
description: >-
  Use when planning and delegating tasks from the main smart terminal to specialized subagents.
  Handles dynamic task sizing (0, 1, or N subagents), context routing, file locking, and zero-token guardrails.
---

# Smart Terminal Orchestrator Dispatch & Sizing Protocol

As the primary terminal session in `/home/vibecoder/Projects`, you coordinate the entire multi-project workspace. You keep the context clean by decomposing tasks into properly sized subagent missions.

## Dynamic Subagent Sizing Matrix

Before spawning any subagent, analyze the user's prompt using this sizing heuristic:

| Task Characteristics | Subagent Allocation | Strategy & Workflow |
| :--- | :--- | :--- |
| **Purely Informational / Q&A** | **0 Subagents** | Answer directly from memory or read `.agents/brain/projects.json`. No subagent overhead. |
| **Atomic / Single-Project Change** | **1 Subagent** | Dedicate exactly 1 subagent to that project. DO NOT over-parallelize (prevents lock conflicts and token waste). |
| **Independent Multi-Project Tasks** | **$N$ Parallel Subagents** | Partition by project boundary. Spawn $N$ subagents simultaneously, each locked strictly to its own directory (`ASSIGNED_PROJECT=<name>`). |
| **Dependent Multi-Step Pipeline** | **Sequential Chain** | Execute sequentially. Subagent 1 writes interface/contracts to `.agents/brain/contracts.md`; Subagent 2 consumes it. |

---

## The 5-Step Orchestration Cycle

### 1. Ambiguity & Clarification Check (MANDATORY RULE)
- **Zero-Guessing Policy**: If behavior parameters, design choices, or implementation options are ambiguous, **STOP and ask clarifying questions immediately** (using `ask_question` or concise conversational prompt).
- Never assume unlikely traits or proceed on guesswork.

### 2. Context Routing & Progressive Disclosure
- Identify target project(s) via `.agents/brain/projects.json`.
- Fetch *only* the target project's `context.md` (`python3 .agents/scripts/blackboard.py get-context <project>`).
- Inject only that specific context into the subagent. Keep all other projects out of the context window.

### 3. Dynamic Model Tiering (No Compromise on Quality)
- **`flash`**: Use for simple syntax checks, lightweight linting, formatting, or single-file test runs.
- **`inherit`** (Gemini 3.8 Flash High): Use for standard feature implementation, refactoring, and general programming.
- **`pro`**: Use for complex C pointer/memory debugging, architectural designs, or intricate race conditions.

### 4. Lock Acquisition & Boundary Confinement
- Register the task in `.agents/brain/blackboard.json`:
  ```bash
  python3 .agents/scripts/blackboard.py register-agent <subagent_id> <role> <project>
  ```
- Subagent executes with `Workspace: 'inherit'`.
- Tool-level hooks in `.agents/hooks.json` automatically prevent unauthorized file edits and cross-project collisions with zero prompt tokens.

### 5. Verification & Memory Journaling
- Subagent runs non-intrusive tests headlessly (`xvfb-run` for GUI/X11; never interrupt user's screen).
- Structural AST checks run automatically via PostToolUse hook (`.agents/scripts/lint-verify.py`).
- Release locks:
  ```bash
  python3 .agents/scripts/blackboard.py unregister-agent <subagent_id>
  ```
- Update shared cross-session memory:
  ```bash
  python3 .agents/scripts/journal.py log-task <project> "<summary of changes>"
  ```
- Auto-commit with Conventional Commits (`feat(...)`, `fix(...)`, `refactor(...)`) and push to `origin master`.
