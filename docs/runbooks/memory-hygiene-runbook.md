# Memory hygiene runbook for Hermes operations

Purpose: keep Hermes memory useful, source-boundary-safe, and reversible. Use this checklist when auditing prompt memory, Hindsight banks, repository docs, Honcho, or session history.

Scope:
- Built-in prompt memory and user profile.
- Hindsight long-term memory banks, especially `hermes-main`.
- Repository documentation under `docs/`.
- Historical conversation retrieval via `session_search`.
- Honcho as the proven fallback until Hindsight is demonstrated reliable in normal work.

Related source docs:
- Audit: `docs/reports/hindsight-memory-audit-hermes-main.md`
- Source boundaries: `docs/guides/memory/source-boundaries.md`
- Bank taxonomy: `docs/reports/hindsight-bank-taxonomy-proposal.md`
- Reversible cleanup plan: `docs/guides/memory/reversible-cleanup-plan.md`

## Operator quick rules

- Prompt memory is for compact, stable facts that should steer every future assistant run.
- Hindsight is searchable assistant memory, not the canonical source of truth for procedures.
- Repository docs are the canonical place for runbooks, policies, specs, checklists, audits, and decisions that must be reviewed and versioned.
- `session_search` is historical evidence from prior conversations; verify against current docs or live state before acting.
- Honcho remains active until Hindsight proves it can reliably recover needed workflow context during ordinary Hermes use.
- Never store secrets, token values, browser storage state, raw credentials, or private API payloads in memory, docs, or Kanban handoffs.
- Do not retain transient task state: PIDs, `/tmp` paths, one-off task IDs, temporary branches, current board counts, health snapshots, or commit SHAs unless they are part of a dated audit or incident report.
- Prefer one clean canonical durable fact over many repeated near-duplicates.

## What goes where?

Use this routing checklist before retaining, editing, or documenting knowledge.

### Built-in prompt memory / user profile

Store only if all are true:
- The fact is stable for weeks or longer.
- It should influence most future sessions automatically.
- It is short enough to stay useful in every prompt.
- It is not a detailed procedure, raw task log, secret, or status snapshot.

Good examples:
- Communication and channel preferences.
- Durable repo workflow defaults.
- Stable service roles or project roots.
- High-leverage assistant behavior preferences.

Avoid:
- Completed task logs, PR numbers, issue numbers, commits, temporary paths, PIDs, branch names, or run outcomes.
- Multi-step runbooks. Put those in docs or skills.

### Hindsight long-term memory

Store if:
- The fact is useful for future recall but does not need to be injected into every prompt.
- It is durable context, a lesson learned, or a relationship between entities.
- It can be summarized cleanly without transient status or secrets.

Use Hindsight as:
- Semantic recall for project/operator context.
- A way to find durable facts and relevant docs.
- A supplement to repository docs, not a replacement for them.

Avoid:
- Raw logs and transcripts.
- Temporary status.
- Detailed operating procedures that should be reviewed in git.
- Duplicate wording already captured in a cleaner fact.

### Repository docs

Use docs for canonical and auditable knowledge:
- Runbooks and checklists.
- Source-boundary rules.
- Architecture and integration notes.
- Specs, plans, decisions, and reports.
- Cleanup manifests and review packets that need version control.

Docs may record secret locations only when the location is a restore prerequisite and does not expose secret values. Never commit secret values.

### `session_search`

Use `session_search` when the question is historical:
- "What did we decide about X?"
- "Where did we leave Y?"
- "Did we already discuss Z?"

Treat results as transcript evidence. Before acting, verify against repository docs, Hindsight, or live state.

### Current session and Kanban comments

Use current session context for immediate tool outputs and task-local facts. Use Kanban comments for durable handoff details that another worker needs, but avoid storing secrets or noisy logs.

### Honcho

Keep Honcho active as source of truth or fallback while any of these are true:
- Hindsight recall is noisy, stale, duplicate-heavy, or missing key workflow facts.
- Workers still need Honcho to recover operator/project context safely.
- High-risk workflows depend on the knowledge: credentials, backups, homelab changes, restores, or privileged operations.
- There is no documented fallback path from repository docs plus Hindsight.

Hindsight can become primary for a workflow only after repository docs are canonical, ordinary workers successfully use Hindsight for that workflow, recall quality is repeatably good, and the operator agrees Honcho can be demoted.

## Recurring hygiene workflow

Cadence:
- Lightweight check: monthly, or after major Hermes memory/provider changes.
- Targeted check: after a user says recall is wrong, stale, noisy, or missing.
- Deep cleanup: only after export, dry-run review, and approval.

Checklist:
- [ ] Pick a target scope: prompt memory, a Hindsight bank, one domain, or one recall problem.
- [ ] Define the expected source of truth: memory, docs, Honcho, `session_search`, or live state.
- [ ] Sample recent and high-impact memories for duplicates, stale state, and source-boundary violations.
- [ ] Search for known noise patterns: task IDs, `/tmp`, PIDs, current counts, one-off branches, timestamps, and completed-work logs.
- [ ] Identify high-value facts that should be consolidated into one canonical memory or promoted to docs.
- [ ] Identify docs/runbooks that are missing, outdated, or not linked from `docs/README.md`.
- [ ] Run the recall quality check pattern below against representative normal workflows.
- [ ] Record findings in a dated report or Kanban handoff, not in prompt memory.
- [ ] If cleanup is needed, follow the reversible cleanup process before any mutation.

## Pre-cleanup checklist

Do not mutate memory until this checklist is complete.

- [ ] Confirm the target bank or memory store and why cleanup is needed.
- [ ] Confirm source boundaries: what belongs in prompt memory, Hindsight, docs, session history, or Honcho.
- [ ] Export or snapshot the target memory scope in a restorable or replayable form.
- [ ] Verify the export is readable.
- [ ] Generate exact duplicate and normalized duplicate candidate reports from the same snapshot.
- [ ] Generate stale/noisy candidate reports for timestamps, task IDs, `/tmp` paths, PIDs, transient health/port checks, tmux routing, commits, and worker chatter.
- [ ] Build a dry-run review bundle with memory ID, current text, category, proposed action, rationale, reviewer decision, and rollback note.
- [ ] Mark each candidate as retain, edit, merge, or delete.
- [ ] Create canonical replacement text for every edit or merge candidate.
- [ ] Human-review the dry-run bundle before live writes.
- [ ] Start with a tiny low-risk pilot, preferably exact-text duplicates only.

Hard stops:
- No readable export.
- No affected-ID manifest.
- Unclear rollback method.
- Ambiguous candidate whose durable value is uncertain.
- Proposed deletion might remove a safety-critical preference, credential location, backup rule, or homelab guardrail.

## Cleanup safety process summary

Use the reversible cleanup plan as the authoritative process.

Safe sequence:
1. Phase 0: export the target bank and generate evidence; do not mutate anything.
2. Phase 1: build the dry-run review bundle; still no deletions.
3. Phase 2: get human approval for the exact first batch and batch size.
4. Phase 3: run a low-risk live pilot; immediately re-export affected IDs.
5. Phase 4: expand gradually only after recall checks and reviewer sign-off.

Action rules:
- Retain clean durable facts.
- Edit noisy but valuable facts into stable canonical wording.
- Merge repeated durable facts into one canonical record after replacement is confirmed.
- Delete only reviewed, approved, redundant or perishable records with rollback coverage.

Rollback levels:
- Before writes: discard the candidate bundle and regenerate from the untouched export.
- After pilot writes: restore only the affected batch from the export and affected-ID manifest.
- Broad failure: stop writes, restore from the full export if supported, or replay approved pre-cleanup records into a recovery bank and compare before cutover.

## Post-cleanup validation

Run this immediately after a pilot or batch.

- [ ] Re-export affected IDs or the target scope.
- [ ] Compare live changes against the approved dry-run bundle.
- [ ] Confirm canonical replacement facts are present.
- [ ] Confirm deleted or retired duplicates are gone only where approved.
- [ ] Run representative Hindsight recall queries and compare quality against pre-cleanup examples.
- [ ] Confirm repository docs still contain canonical runbooks and policy.
- [ ] Confirm prompt memory remains compact and has not gained task logs or temporary state.
- [ ] Confirm Honcho remains available as fallback unless the workflow has explicitly passed Hindsight confidence gates.
- [ ] Record validation results in a dated report or Kanban comment.
- [ ] Stop and rollback the batch if recall is worse, a durable fact disappeared, or the mutation does not match the approved bundle.

## Recall quality check pattern

Use this pattern in normal Hermes workflows to test whether memory is helping.

Trigger phrases:
- "What did you remember about this?"
- "Why did you choose that source?"
- "Where is the source of truth for this?"
- "What would you check before acting?"

Reusable check:
1. Ask the assistant to state the remembered facts it used.
2. Require each fact to name its source class: prompt memory, Hindsight, repository docs, `session_search`, current tool output, Kanban handoff, or Honcho.
3. Ask whether any remembered fact might be stale, duplicated, or too broad.
4. Ask what canonical source should be checked before action.
5. Verify the canonical source with a tool when the next step has side effects.
6. If recall was wrong or noisy, record the issue and route it to memory hygiene cleanup instead of silently working around it.

Example prompt:

```text
Before acting, tell me what you remembered about this workflow. For each item, say whether it came from prompt memory, Hindsight, repository docs, session_search, current context, Kanban handoff, or Honcho. Then say which source is canonical and what you will verify before making changes.
```

Good answer shape:
- Remembered: "Feature branches by default except `/home/jellybot/home-network` direct-main."
- Source class: prompt memory plus repo workflow docs.
- Canonical source to verify: repository docs and current `git status`.
- Staleness risk: low for the convention, high for any current branch/status details.
- Action: inspect repo state before editing.

Bad answer shape:
- "I remember task `t_12345678` completed and commit `abc123` passed, so I will proceed."
- Problem: task IDs and commits are stale operational state unless verified in git/docs.

## Bank taxonomy operating guidance

Current recommendation:
- Keep `hermes-main` as the shared/default bank for cross-cutting Hermes and user/operator context.
- Pilot a separate `home-network` bank first because homelab operational facts have a strong domain boundary and high noise pressure.
- Consider `portfolio` later only if the `home-network` pilot improves recall and portfolio recall remains noisy.
- Defer `cert-study` until recurring study work creates enough durable recall volume.

Bank split rule:
- A new bank is justified only when the domain boundary is stable, shared-bank noise materially hurts recall, and future queries are usually domain-scoped enough to benefit from isolated recall.

Migration posture:
- Do not bulk-move historical `hermes-main` immediately.
- Route new memories conservatively.
- Manually migrate only a small set of obviously durable, high-value facts.
- Reassess after 2-4 weeks using actual recall quality, routing mistakes, and duplicate pressure.

## Audit findings to keep watching

The 2026-05-29 audit of `hermes-main` found:
- 2,466 memory nodes.
- 293 exact-text duplicate clusters covering 740 memories.
- 536 normalized duplicate clusters covering 1,415 memories.
- Heavy stale-state pressure from embedded timestamps, Kanban task IDs, `/tmp` paths, PIDs, ports, tmux notes, commits, worker chatter, and board-state snapshots.
- Same-session amplification from a few large parent sessions.

Use those categories as the default search terms for future hygiene passes.

## Final operator checklist

Before closing a memory hygiene task:
- [ ] The durable artifact lives under `docs/`, not a scratch workspace.
- [ ] `docs/README.md` links the artifact if it is a new canonical doc.
- [ ] The runbook distinguishes prompt memory, Hindsight, docs, `session_search`, current context, Kanban comments, and Honcho.
- [ ] Honcho remains active until Hindsight is proven through normal workflow.
- [ ] Cleanup instructions require export, dry-run review, human approval, pilot writes, post-cleanup validation, and rollback coverage.
- [ ] The recall quality check pattern is included.
- [ ] Verification ran, including at least `git diff --check` for docs-only changes.
- [ ] Changes were committed and pushed, or the task was blocked with the exact push blocker.
