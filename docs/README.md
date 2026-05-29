# Hermes Ops docs

Durable documentation produced by operators and Kanban workers.

## Folders

- `roadmap/` — long-lived direction, priorities, and sequencing.
- `specs/` — feature, workflow, and system specifications.
- `guides/` — how-to guides and reusable procedures.
- `bugs/` — defects, incident notes, reproduction steps, and fixes.
- `runbooks/` — operational procedures with commands and verification.
- `operations/` — local operating rules, schedules, dashboards, and service notes.
- `architecture/` — system diagrams, design notes, and integration maps.
- `decisions/` — ADRs and explicit trade-off decisions.
- `reports/` — audits, reviews, and generated analyses.
- `plans/` — implementation plans and checklists.

## Output path rule

Every durable Kanban task must name its final output path in the task body before work starts.

Good examples:

- `docs/guides/kanban/adoption-and-board-separation-policy.md`
- `docs/guides/kanban/operating-procedures.md`
- `docs/specs/kanban-durable-workspace-standard.md`
- `docs/reports/hindsight-memory-audit-hermes-main.md`
- `docs/guides/memory/source-boundaries.md`
- `docs/operations/mission-control-read-only-actions.md`
- `docs/bugs/2026-05-29-scratch-artifact-loss.md`

Bad example:

- `~/.hermes/kanban/boards/<board>/workspaces/<task>/some-file.md`

Scratch workspaces are deleted when tasks complete.
