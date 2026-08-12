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
- `decisions/` — Architecture Decision Records (ADRs); start from `decisions/0000-adr-template.md`. See [decisions/README.md](decisions/README.md) for when and how to add one.
- `reports/` — audits, reviews, and generated analyses.
- `plans/` — implementation plans and checklists.

## Output path rule

Every durable Kanban task must name its final output path in the task body before work starts.

Good examples:

- `docs/guides/kanban/adoption-and-board-separation-policy.md`
- `docs/guides/kanban/operating-procedures.md`
- `docs/runbooks/kanban-default-for-multi-step-hermes-projects.md`
- `docs/specs/kanban-durable-workspace-standard.md`
- `docs/reports/hindsight-memory-audit-hermes-main.md`
- `docs/guides/memory/source-boundaries.md`
- `docs/reports/hindsight-bank-taxonomy-proposal.md`
- `docs/guides/memory/reversible-cleanup-plan.md`
- `docs/runbooks/memory-hygiene-runbook.md`
- `docs/reports/memory-hygiene-final-handoff.md`
- `docs/operations/mission-control-read-only-actions.md`
- `docs/runbooks/dashboard-link-no-agent-watchdog.md`
- `docs/specs/dashboard-health-check-inventory-contract.md`
- `docs/reports/dashboard-link-no-agent-validation.md`
- `docs/reports/recurring-chat-checks-no-agent-conversion-plan.md`
- `docs/reports/backup-metadata-sources.md`
- `docs/reports/jellyssh-phase3-bug008-pilot-2026-08-12.md`
- `docs/plans/backup-freshness-check.md`
- `docs/runbooks/backup-freshness-check.md`
- `docs/plans/dashboard-link-no-agent-watchdog.md`
- `docs/operations/dominic-hermes-operating-manual.md`
- `docs/operations/home-directory-project-layout.md`
- `docs/bugs/2026-05-29-scratch-artifact-loss.md`

Bad example:

- `~/.hermes/kanban/boards/<board>/workspaces/<task>/some-file.md`

Scratch workspaces are deleted when tasks complete.
