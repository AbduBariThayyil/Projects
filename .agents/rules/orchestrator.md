# Smart Terminal Orchestrator Rules

1. **Single Entry Point**: This terminal session is the central coordinator for all projects in `/home/vibecoder/Projects`. Never require the user to open separate chat sessions for different subprojects.
2. **Subagent Delegation**: The main terminal does not directly edit code or run heavy builds across subprojects. It decomposes tasks, consults `.agents/brain/projects.json`, and spawns specialized subagents (`invoke_subagent`).
3. **Progressive Context Scoping**: Only inject the specific project's `context.md` (or run `python3 .agents/scripts/blackboard.py get-context <project>`) into the subagent's prompt. Do NOT pollute context with unrelated project data.
4. **Dynamic Model Tiering**:
   - Assign lightweight verification, formatting, or single-file test runs to `flash`.
   - Assign complex debugging, core feature writing, or C pointer refactoring to `inherit` (Gemini 3.8 Flash High) or `pro` without compromising quality.
5. **No Guessing**: Always proactively prompt the user with clarifying questions whenever requirements or behaviors are ambiguous.
6. **Task & Lock Coordination**: Register tasks and check file locks in `.agents/brain/blackboard.json` before and after dispatching subagents.
