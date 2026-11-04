# Workspace Shared Memory & Persistent Journal

## Current Workspace State
- **Architecture**: Single Smart Terminal Orchestrator with progressive context routing and tool-level boundary enforcement via `.agents/`.
- **Primary Branch**: `master` (synchronized with `origin/master`).
- **Active Subprojects**: 11 desktop applications/daemons (all documented in `.agents/brain/projects.json` with standardized `context.md` files).

## Recent Accomplishments
- Implemented `.agents/` orchestration framework with:
  - `.agents/brain/projects.json`: Lightweight project router catalog.
  - `.agents/brain/blackboard.json`: Real-time file locking and active agent tracking.
  - `.agents/hooks.json`: PreToolUse boundary and lock enforcement + PostToolUse automated AST/syntax checking.
  - `.agents/skills/`: 7 curated, on-demand runbooks tailored to Arch Linux desktop stack (C/GTK3/X11, PipeWire, Systemd RTC, Python IPC, Headless TDD, Git workflow, Orchestrator dispatch).
  - Context manifests added for `ani-cast` and `xmodmap-watcher`.

## Persistent Knowledge & Architectural Quirks
- **Hardware Profile**: Toshiba Portégé R700 ("Arch Xiao"), Arch Linux, BSPWM, dual internal stereo speakers (`alsa_output.pci*`).
- **Testing Standard**: Headless testing via `xvfb-run -a` is strictly mandatory for any GUI or X11 binaries to prevent stealing window focus or interrupting fullscreen applications.
- **Git Protocol**: Every task completion auto-commits with Conventional Commits and pushes to `origin master`.
