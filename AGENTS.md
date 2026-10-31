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
