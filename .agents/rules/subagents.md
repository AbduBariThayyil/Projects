# Subagent Execution Rules

1. **Strict Project Boundary**: A subagent must only modify files inside its assigned project directory (e.g., `sys-alarm/` or `keyholder-hud/`). Edits outside this scope are blocked by `.agents/hooks.json`.
2. **File Locking**: Coordinate file locks via `.agents/scripts/blackboard.py lock <file> <agent_id>` before beginning edits.
3. **AST Validation**: Immediately test syntax after any edit. Never leave syntax errors in modified files.
4. **Non-Intrusive Live Testing**: Verify all fixes and features live using headless virtual frames (`xvfb-run`) or background processes. Never display windows over the user's active screen or interrupt fullscreen workflows.
5. **Concise Reporting**: Report back to the orchestrator with concise execution summaries, modified file paths, and test results.
