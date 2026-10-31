# Repository Guidelines & Automation Rules

## Automated Git Commit & Push Workflow
Whenever the agent completes a bugfix, implements a feature, or modifies code/configurations in this repository:
1. **Verify**: Check `git status` and test the fix/changes to ensure no unintended edits or broken syntax.
2. **Auto-Commit**: Stage the relevant modified files and commit them using the Conventional Commits specification:
   - `fix(<scope>): <short description of the bug fixed>`
   - `feat(<scope>): <short description of the feature>`
   - `refactor(<scope>): <description>`
3. **Auto-Push**: Immediately push the new commit to GitHub:
   ```bash
   git push origin master
   ```
4. **Clean State**: Never leave uncommitted changes or detached worktree branches behind after completing a task.

## Execution Guardrails
- **Structural Validation**: Verify changed files via structural ast/lint checks immediately after the first edit.
- **Consecutive Failure Halting**: If an automated fix fails twice consecutively, halt background execution and surface the diff overview immediately.
- **Clarification Over Assumptions**: Proactively prompt with clarification questions whenever behavior parameters are ambiguous; do not assume unlikely implementation traits.
- **Non-Intrusive Live Testing**: Verify fixes took place by live testing without covering the user's screen (e.g., execute in another desktop workspace, run headless via `xvfb-run`, or in the background). Do not interrupt fullscreen applications.

