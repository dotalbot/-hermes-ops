# Scratch artifact loss on completed Kanban tasks

## Summary

Completed tasks on `continuous-hermes-improvement` declared artifacts under deleted scratch workspaces. The worker logs still exist for most affected tasks, so some content may be recoverable from write/diff traces.

## Root cause

Hermes removes `scratch` workspaces after task completion. That is intended behavior for temporary work, but it is unsafe for durable deliverables when workers report scratch paths as final artifacts.

## Known affected artifact-producing tasks

- `t_3f6763aa` — `kanban-adoption-policy.md`
- `t_467ab8e2` — `hindsight-memory-audit-hermes-main.md`
- `t_5ac655c7` — `hindsight-bank-taxonomy-proposal.md`
- `t_8e07f1e2` — `memory-hygiene-runbook.md`, `hindsight-audit.json`, `hindsight-audit-candidates.jsonl`
- `t_8e24e2dd` — `memory-hygiene-runbook.md`
- `t_dcbf74ef` — `kanban-default-runbook.md`
- `t_ddd94f48` — `hermes-kanban-operating-procedures.md`

## Recovery approach

1. Read the worker log from:

   `~/.hermes/kanban/boards/continuous-hermes-improvement/logs/<task-id>.log`

2. Recover content from `write` / `review diff` sections where possible.
3. Save recovered documents into `/home/jellybot/hermes-ops/docs/` using the standard folder layout.
4. Commit recovered files to the Hermes Ops repo.
5. Add a comment to the original Kanban card with the new durable path.

## Prevention

Use the Kanban durable workspace standard:

`docs/specs/kanban-durable-workspace-standard.md`
