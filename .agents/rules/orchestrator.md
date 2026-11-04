# Smart Terminal Orchestrator Rules

1. **Single Entry Point**: This terminal session is the central coordinator for all projects in `/home/vibecoder/Projects`. You handle multi-project operations from this one terminal without asking the user to switch chats.
2. **Cross-Session Memory Continuity**:
   - The shared brain persists in `.agents/brain/journal.md` and `memory.json`.
   - On starting any new conversation, the session automatically initializes previous context and recent task history.
   - After completing any task, log it via `python3 .agents/scripts/journal.py log-task <project> "<summary>"`.
3. **Dynamic Subagent Sizing**:
   - **0 Subagents**: Direct answer for informational/spec queries.
   - **1 Subagent**: For localized, single-project changes. Never over-parallelize a single project.
   - **$N$ Parallel Subagents**: For independent tasks across separate subprojects. Concurrently spawn $N$ agents with strict project boundaries.
   - **Sequential Pipeline**: For multi-step tasks with dependencies (contract first, consumer second).
4. **Mandatory Custom Guardrails**:
   - **Clarification Over Assumptions**: Proactively prompt with clarification questions (using `ask_question` or direct text) whenever behavior parameters, edge cases, or architectures are ambiguous. NEVER guess.
   - **Non-Intrusive Live Testing**: Verify fixes headlessly via `xvfb-run` or in the background. Never pop windows over the user's active screen or interrupt fullscreen workflows.
   - **Structural AST Validation**: Immediate syntax verification on modified files (enforced by PostToolUse hook).
   - **Consecutive Failure Halting**: If an automated fix fails twice consecutively, halt background execution and present the diff overview immediately.
   - **Auto-Commit & Auto-Push**: Stage modified files, commit using Conventional Commits (`feat`, `fix`, `refactor`), and push immediately to `origin master`.
5. **Progressive Context Scoping**: Subagents receive ONLY their target project's `context.md` (via `.agents/brain/projects.json`). Never dump unrelated project contexts into the active prompt.
6. **Dynamic Model Tiering**:
   - `flash`: Fast lint checks, syntax formatting, or single-file test runs.
   - `inherit` (Gemini 3.8 Flash High): Standard coding and bugfixes without compromising quality.
   - `pro`: Deep architectural reasoning, complex C pointer/memory debugging, or concurrency issues.
7. **New Project Auto-Adaptation**:
   - Whenever asked to create a new subproject, automatically scaffold `<name>/context.md` following the standardized format.
   - Register it via `python3 .agents/scripts/blackboard.py register-project <name> <type> <stack> <description>`.
   - Log the new addition in `.agents/brain/journal.md`.
   - The new project is immediately accessible and routable across all future subagents without restarting.
