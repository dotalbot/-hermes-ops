# Reversible cleanup plan for duplicate and stale Hindsight memories

Date: 2026-05-30
Status: proposed
Related inputs:
- `docs/reports/hindsight-memory-audit-hermes-main.md`
- `docs/guides/memory/source-boundaries.md`
- `docs/reports/hindsight-bank-taxonomy-proposal.md`

## Goal

Reduce duplicate inflation and stale operational noise in `hermes-main` without taking a destructive first step. The first pass must be exportable, reviewable, reversible, and safe to pause after any stage.

## Safety rules

1. No direct deletions in phase 0 or phase 1.
2. Every candidate change starts from an exported snapshot or query result that can be replayed.
3. Human approval is required before any write that removes or materially rewrites stored memories.
4. Keep `hermes-main` readable during cleanup; do not block ordinary recall work while preparing candidates.
5. Prefer consolidating many repeated memories into one durable canonical fact only after the replacement text is reviewed.
6. When in doubt, retain and tag for later review instead of deleting.

## Cleanup targets from the audit

The audit identified three main noise classes that this plan must handle.

### A. Exact-text duplicate clusters

Examples from the audit:
- 16 copies of the host identity sentence
- 10 copies of the running-task-limit sentence
- 9 copies of the dashboard-operational sentence

Action bias:
- safest to identify first
- usually easiest to dry-run and review
- often eligible for merge or delete after a canonical replacement exists

### B. Normalized near-duplicate clusters

Definition for cleanup review:
- memories that differ only by appended `When:` metadata, task IDs, `/tmp/...` paths, actor markers, or similar formatting noise

Action bias:
- review manually before any mutation
- often best handled by keeping one clean durable version and retiring the noisy variants

### C. Stale or perishable operational memories

Categories called out by the audit:
- embedded timestamps
- Kanban task IDs
- `/tmp` paths
- PIDs
- transient ports and service health snapshots
- tmux routing notes
- commits and worker-process chatter
- ready/running task counts and one-off board state

Action bias:
- usually not memory-worthy unless preserved as part of a dated incident report or audit
- often should be deleted or moved out of memory only after review confirms there is no durable rule hidden inside

## Decision framework: retain, edit, merge, or delete

Use the source-boundary rules before touching any record.

### Retain as-is

Keep the memory unchanged when all are true:
- the fact is durable for weeks or longer
- it is still useful for recall
- it does not expose secrets or fragile runtime state
- the wording is already clean and canonical

Examples:
- stable user preferences
- durable workflow conventions
- long-lived service roles or repo-location facts

### Edit into a cleaner canonical fact

Edit when the fact is worth keeping but the stored text is noisy.

Typical triggers:
- includes a timestamp, PID, task ID, `/tmp` path, or run-specific wording around an otherwise durable fact
- mixes the durable rule with one-off status
- duplicates another fact but this version contains the best wording

Edit rule:
- rewrite only after export and human review
- preserve the original text in the review bundle so rollback can restore it exactly

### Merge into a single canonical fact

Merge when several memories express the same durable idea.

Typical triggers:
- exact-text duplicate clusters
- normalized duplicates where differences are clearly non-semantic
- repeated experience/observation pairs describing the same stable fact

Merge rule:
- propose one canonical replacement record
- mark all contributing memory IDs in the review bundle
- do not delete source records until the replacement is confirmed present and approved

### Delete

Delete only when all are true:
- the memory is perishable or redundant
- no durable rule would be lost by removing it
- the fact is already captured elsewhere if it matters at all, such as repo docs, session history, or an audit report
- the deletion candidate appears in a human-approved batch with rollback coverage

Typical delete candidates:
- one-off PIDs
- `/tmp` artifact paths
- transient board counts
- worker/process status snapshots
- task-specific chatter that cannot help a future session

## Reversible workflow

### Phase 0: freeze the evidence, no mutations

Outputs:
- full export or bank snapshot of the target scope
- candidate reports for duplicate and stale-memory clusters
- a dated review manifest stored in the repo or adjacent operator workspace

Steps:
1. Export the target bank before cleanup starts.
2. Generate a duplicate report with both exact-text and normalized clusters.
3. Generate a stale-memory report keyed to the audit categories above.
4. Store the raw export and reports with timestamps so the exact pre-cleanup state can be reconstructed.
5. Record the export path, generation time, bank name, and report hashes in the review manifest.

Why this is safe:
- no writes to memory
- rollback is simply "do nothing" because the bank is untouched
- later changes can be compared against a fixed pre-cleanup snapshot

### Phase 1: build a dry-run review bundle, still no deletions

Outputs:
- `retain.csv` or equivalent candidate list
- `edit.csv` candidate list with proposed canonical text
- `merge.csv` candidate list with source IDs and replacement text
- `delete.csv` candidate list with explicit reason codes

Required columns for each candidate row:
- memory ID
- current text
- candidate category: retain/edit/merge/delete
- duplicate cluster ID or stale-category label
- proposed canonical text, if any
- rationale
- reviewer decision field
- rollback note

Review rules:
- exact-text duplicate clusters may be batch-reviewed together
- normalized duplicates require spot checks and preferably line-by-line examples
- stale operational memories must be sampled by category so the reviewer can confirm no durable guidance is being removed

Why this is safe:
- still no destructive actions
- all proposed changes are inspectable before approval
- the reviewer can downgrade any candidate from delete to retain or edit

### Phase 2: human approval gate

Minimum approvals before writes:
1. Approve the export/backup evidence exists and is readable.
2. Approve the dry-run candidate bundle.
3. Approve the batch size for the first live write.

Recommended first live batch:
- only exact-text duplicates with obvious redundancy
- small enough to verify manually, for example 10 to 25 clusters rather than hundreds

Hard stop conditions:
- uncertainty about whether a fact is durable
- disagreement about canonical wording
- candidate cluster contains mixed meanings after normalization
- no reliable rollback path for the proposed mutation

### Phase 3: low-risk live pilot

Pilot sequence:
1. Apply approved edits/merges/deletes only for the first small batch.
2. Re-export the affected IDs immediately after the write.
3. Compare before/after results against the review bundle.
4. Run recall checks on representative queries to confirm recall quality did not get worse.
5. Pause for human sign-off before expanding scope.

Success criteria for the pilot:
- the approved mutations match the dry-run bundle exactly
- replacement canonical facts are present where expected
- no accidental removal of durable rules
- sample recall is at least as good, and ideally less noisy

### Phase 4: staged expansion

Expand only after the pilot succeeds.

Recommended order:
1. exact-text duplicates
2. normalized near-duplicates with clear canonical replacements
3. stale operational memories that clearly fail the source-boundary test
4. ambiguous mixed cases only if they still matter after the easy wins

Do not bulk-delete all stale categories at once. Cheap mistakes are cheaper than expensive confidence.

## Rollback strategy

Rollback must exist at three levels.

### Level 1: candidate rollback before writes

If review quality is poor or categories look wrong:
- discard the dry-run bundle
- regenerate from the untouched export
- tighten rules before trying again

### Level 2: batch rollback after a pilot write

If the live pilot removes something important or the replacement wording is bad:
- use the pre-cleanup export plus the affected-ID manifest to recreate the removed or edited entries exactly
- revert only the affected batch, not the whole bank
- re-run recall checks before attempting a revised pilot

### Level 3: full rollback

If the cleanup process causes broad recall degradation or confidence collapses:
- stop further writes
- restore from the original bank export if the storage/API supports full import restore
- otherwise replay only the approved pre-cleanup records from the export into a fresh recovery bank and compare before cutover

Rollback prerequisites:
- export format is restorable, not just human-readable
- affected IDs are recorded per batch
- proposed replacement text is versioned in the review bundle
- post-write verification is done immediately, not days later

## Review workflow

### Reviewer packet

Each approval round should include:
- the pre-cleanup export reference
- summary counts by category
- top duplicate clusters by size
- examples from each stale-memory category
- proposed canonical replacements for merge/edit cases
- a list of "do not touch" categories, such as preferences, durable conventions, and secrets-related restore notes

### Suggested reviewer questions

1. Does this candidate contain a durable rule that belongs in memory or docs?
2. Is the apparent duplicate truly the same fact, or only superficially similar?
3. Would deleting this memory make a future worker less safe?
4. Should this be edited into a stable fact rather than deleted?
5. Is the canonical replacement text better than the existing versions?

### Escalation rule

If a reviewer cannot decide in under a minute, mark the item retain-for-now and move on. The cleanup should harvest obvious wins first.

## Category-specific guidance

### Exact duplicate clusters

Default action:
- retain one canonical record
- delete the rest only after approval and verification

Exception:
- if duplicates exist across intentionally different fact types and the distinction matters, edit or retain instead of collapsing blindly

### Normalized near-duplicates

Default action:
- prefer edit or merge, not immediate delete
- keep the cleanest wording as the canonical candidate

Exception:
- if normalization hides a meaningful distinction, split the cluster and review manually

### Timestamps, task IDs, PIDs, `/tmp` paths, and board-state chatter

Default action:
- delete after review unless the fact is part of a dated audit, incident report, or repository artifact

Exception:
- if the text contains a durable policy hidden inside transient status, extract that policy into a clean canonical memory or docs before deleting the noisy source

### Host/infra facts that duplicate many times

Default action:
- keep one clean durable statement
- remove redundant copies

Exception:
- if the fact changes over time and the history matters, move the history to a dated report rather than keeping many indistinguishable memory entries

## Relationship to source boundaries and bank taxonomy

This cleanup plan assumes:
- repository docs remain the source of truth for runbooks, audits, policy, and reviewable operational guidance
- Hindsight remains searchable assistant memory, not the only canonical source
- `hermes-main` should become narrower and cleaner even if future bank splitting happens later
- bank splitting should not be used as a substitute for duplicate cleanup; otherwise the noise just spreads sideways

## Minimum acceptance checklist before any destructive batch

- [ ] Pre-cleanup export exists and was verified readable.
- [ ] Duplicate and stale-category reports were generated from the same snapshot.
- [ ] Candidate bundle names every affected memory ID and reason code.
- [ ] A human reviewed the bundle and approved the exact batch.
- [ ] Replacement canonical text exists for every merge/edit case.
- [ ] Rollback method was tested or at least command-walked on a small sample.
- [ ] Post-write verification queries are defined in advance.
- [ ] The first batch is small and low-risk.

## First recommended next action

Do not delete anything yet.

Start with phase 0 and phase 1 only:
- export `hermes-main`
- generate duplicate and stale-memory candidate reports
- assemble a human-review packet
- approve a tiny exact-duplicate pilot batch before any live cleanup

That sequence is slow on purpose. The memory of a cleanup plan should not itself need cleaning up next week.
