# Memory hygiene final handoff

Date: 2026-05-30
Task: `t_8e07f1e2`

## Outcome

The durable memory hygiene deliverables are now in `/home/jellybot/hermes-ops/docs/` rather than an ephemeral Kanban scratch workspace.

Primary runbook:
- `docs/runbooks/memory-hygiene-runbook.md`

Supporting artifacts:
- `docs/reports/hindsight-memory-audit-hermes-main.md`
- `docs/guides/memory/source-boundaries.md`
- `docs/reports/hindsight-bank-taxonomy-proposal.md`
- `docs/guides/memory/reversible-cleanup-plan.md`

## Live Hindsight verification

Read-only checks performed from this repo on 2026-05-30:

- `hermes memory status` reports built-in memory active, provider `hindsight`, plugin installed, and status available.
- `GET http://jellyhome:18888/version` returned API `0.6.2`.
- `GET http://jellyhome:18888/v1/default/banks` returned banks including:
  - `hermes-main` with 2,566 facts.
  - `home-network-main` with 36 facts.
  - `portfolio-intel-main` with 17 facts.
  - `global-dominic` with 18 facts.
  - Other existing banks: `discord-main`, `jellyssh-main`, `logk-main`, `jellyfood-main`, `Agent_buider`, `Excalidraw_designs`.

The dated audit report remains the canonical analysis snapshot. The live check confirms the service and active bank still exist; the fact count has moved since the audit, so cleanup should use a fresh export before any mutation.

## Acceptance criteria mapping

- Memory hygiene runbook/checklist exists: `docs/runbooks/memory-hygiene-runbook.md`.
- Duplicate cleanup approach is safe and reversible: `docs/guides/memory/reversible-cleanup-plan.md` requires export-first backups, dry-run candidate bundles, human approval gates, pilot batches, and rollback paths.
- Recommendations distinguish memory vs docs vs `session_search`: `docs/runbooks/memory-hygiene-runbook.md` and `docs/guides/memory/source-boundaries.md` define what belongs in built-in prompt memory, Hindsight, repository docs, and session history.
- Hindsight banks and `hermes-main` were audited: `docs/reports/hindsight-memory-audit-hermes-main.md` records duplicate/stale-memory findings, and this handoff records a fresh read-only service/bank check.
- Separate-bank recommendation exists: `docs/reports/hindsight-bank-taxonomy-proposal.md` recommends domain banks such as `hermes-main`, `home-network-main`, `portfolio-intel-main`, and a proposed `cert-study-main`/cert-study equivalent.
- Bank naming note: the live deployment currently uses bank IDs such as `home-network-main` and `portfolio-intel-main`; the taxonomy document discusses the same domains conceptually as `home-network` and `portfolio`.
- Honcho remains active until Hindsight proves itself: the runbook keeps Honcho as fallback until normal workflow recall checks pass.
- “What did you remember about this?” pattern exists: the runbook includes the recall quality check pattern and routing steps for memory vs docs vs session search.

## Recommended next operating step

Do not delete memories immediately. Run the documented export-first cleanup process, produce a dry-run candidate bundle from a fresh `hermes-main` export, review exact deletes/merges/retentions with a human, then apply a small pilot batch and verify recall quality before scaling up. Memory hygiene is a marathon, not a sprint; stale facts have sneaky sneakers.
