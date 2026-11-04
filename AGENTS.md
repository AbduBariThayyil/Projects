# Repository Guidelines & Automation Rules

## Smart Terminal Orchestrator Architecture
This workspace operates under a **Single Smart Terminal Orchestration** model powered by `.agents/`:
1. **Central Terminal Entrypoint**: The primary terminal acts as the lead orchestrator across all subprojects (`ani-cast`, `ant-gm320`, `keyholder-hud`, `polybar-music`, `qt-music`, `sys-alarm`, `sys-control`, `sys-notif`, `sys-notif-center`, `Toshiba Porteger r700`, `xmodmap-watcher`).
2. **Subagent Delegation**: The main terminal decomposes complex user requests and spawns specialized subagents (`invoke_subagent`). Subagents execute directly in the workspace with active file locking.
3. **Progressive Context Routing**: Subagents are supplied only with their target project's `context.md` (via `.agents/brain/projects.json`). Context is never dumped indiscriminately into the main context window.
4. **Zero-Token Guardrails (`.agents/hooks.json`)**: PreToolUse and PostToolUse hooks enforce file locks, project boundary confinement, and structural AST lint checks automatically with zero prompt token overhead.
5. **Dynamic Model Tiering**:
   - `flash`: Lightweight verification, syntax linting, formatting, or single-file test runs.
   - `inherit` (Gemini 3.8 Flash High): Standard coding, bugfixes, and feature development.
   - `pro`: Deep architectural reasoning, complex C pointer/memory debugging, or concurrency issues.

## Automated Git Commit & Push Workflow
Whenever the agent completes a bugfix, implements a feature, or modifies code/configurations in this repository:
1. **Verify**: Check `git status` and test the fix/changes to ensure no unintended edits or broken syntax.
2. **Auto-Commit**: Stage the relevant modified files and commit them using the Conventional Commits specification:
   - `fix(<scope>): <short description of the bug fixed>`
   - `feat(<scope>): <short description of the feature>`
   - `refactor(<scope>): <short description>`
3. **Auto-Push**: Immediately push the new commit to GitHub:
   ```bash
   git push origin master
   ```
4. **Clean State**: Never leave uncommitted changes or detached worktree branches behind after completing a task.

## Execution Guardrails
- **Structural Validation**: Verify changed files via structural ast/lint checks immediately after the first edit.
- **Zero-Polling & Event-Driven Architecture**: Always design system monitors, daemons, and tools with zero CPU polling (e.g., listen to kernel uevents, UPower/system D-Bus signals, or X11 socket events instead of sleep loops). Eliminate constant idle background activities.
- **Consecutive Failure Halting**: If an automated fix fails twice consecutively, halt background execution and surface the diff overview immediately.
- **Clarification Over Assumptions**: Proactively prompt with clarification questions whenever behavior parameters are ambiguous; do not assume unlikely implementation traits.
- **Direct Answer First & Inquiry Confirmation**: When the user asks a question, always provide a direct, informative answer first. If the question involves or implies a code fix, feature, or design change, answer the inquiry first and ask the user for confirmation or clarifying design choices before dispatching subagents or altering code.
- **Desktop Task Completion Notification**: Whenever an agent or subagent completes a user-requested task, feature, or bugfix, immediately send a native desktop notification via `sys-notif` (e.g. `notify-send "Task Complete" "<summary>"`) so the user is immediately alerted.
- **Non-Intrusive Live Testing**: Verify fixes took place by live testing without covering the user's screen (e.g., execute in another desktop workspace, run headless via `xvfb-run`, or in the background). Do not interrupt fullscreen applications.
