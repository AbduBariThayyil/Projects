---
name: git-auto-workflow
description: >-
  Use when completing a task, feature, or bugfix to verify, commit, and push changes to GitHub.
---

# Automated Git Commit & Push Runbook

Enforces the core repository automation rule:
*"Auto-Commit & Auto-Push to origin master on completion."*

## Execution Steps

1. **Verify State**:
   - Check `git status` to ensure only expected files are changed:
     ```bash
     git status --short
     ```
   - Ensure no leftover scratch files or temporary build artifacts are untracked.

2. **Structural Validation Check**:
   - Verify all edited files have passed AST / syntax compilation:
     - Python: `python3 -m py_compile <file>`
     - C: `gcc -fsyntax-only -Wall <file>`
     - Bash: `bash -n <file>`

3. **Stage & Commit**:
   - Use Conventional Commits formatting:
     - `feat(<scope>): <short description>`
     - `fix(<scope>): <short description>`
     - `refactor(<scope>): <short description>`
   - Example:
     ```bash
     git add <modified_files>
     git commit -m "feat(sys-alarm): add speaker detection fallback"
     ```

4. **Auto-Push to Master**:
   - Immediately push commit to origin:
     ```bash
     git push origin master
     ```
   - Verify working tree is clean and `git status` reports up to date with `origin/master`.
