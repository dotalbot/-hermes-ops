# JellySSH Phase 3.5 consolidation plan

> **For Hermes:** Preserve historical evidence, make the operational projection truthful, and leave no dispatchable work behind.

**Goal:** Reconcile the completed JellySSH pilot board and control-plane artifacts after BUG-011, without changing product code, profiles, adapters, or LogK.

**Architecture:** Git and the live JellySSH board are the authorities for completed product work. The Phase 2 `project.yaml` and `runtime.yaml` remain frozen bootstrap authority, so their generated `jellyssh-status.*` projection is retained as a historical setup snapshot rather than rewritten to claim current operations. A separate operational snapshot records live board/Git facts and links the immutable baseline.

**Scope:** Board reconciliation, documentation, generated status projection, and durable evidence tracking in `hermes-ops` only.

**Non-goals:** Product edits, dispatch, profile/skill/runtime changes, Claude adapter changes, PR creation, merge, release, deployment, secrets, sudo, or LogK work.

## Tasks

- [x] Inspect live JellySSH board, product `main`, BUG-011 branch/merge history, and control-plane worktree state.
- [x] Archive only four superseded blocked cards with no downstream dependency that must remain live: `t_bdd86be5`, `t_4bfb3176`, `t_47ca853d`, and `t_5e689251`.
- [x] Preserve the BUG-008 blocked review and dependency-held TODO as nonspawnable historical evidence; add explicit reconciliation comments rather than archiving them.
- [x] Create a new intentional control-plane branch from the merged `docs/kanban-workspace-standard` line.
- [x] Preserve the four generated BUG-010/BUG-011 preflight artifacts for tracking; they become durable tracked evidence only in the final commit.
- [x] Add a current operational status projection, timestamped with timezone, that distinguishes live status from the frozen Phase 2 baseline.
- [x] Record the BUG-011 merge reconciliation and update the multi-agent guide index.
- [x] Run control-plane tests, scoped document/JSON validation, independent review, commit, push, and final readback. The full control-plane suite has one environment dependency failure (`mcp.server.fastmcp` unavailable to its subprocess seam); the focused Claude-adapter suite passed 66 tests with one Landlock skip.

## Verification

- `hermes kanban --board jellyssh stats` shows no ready or running card and no stale diagnostics.
- Product `main` contains the BUG-011 merge commit, while the implementation branch remains inspectable.
- `git diff --check` passes.
- The updated status projection parses as JSON and clearly labels sources and observation time.
- Relevant control-plane tests pass and an independent review reports no blocking finding.
