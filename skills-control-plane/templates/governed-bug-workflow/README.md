# Governed bug warm-path canary

Use this package for the next small deterministic JellySSH bug after the warm-path controller tree has independent exact-tree certification and publication.

## Non-negotiable boundaries

- Create a fresh specification, implementation card, review card, and acceptance card.
- Review card: reviewer assignee, `workspace: scratch`, `max_runtime: 20m`, `max_retries: 1`.
- Bind exact base commit, specification commit/path/bytes digest, target commit, and target tree.
- Capability evidence is reusable only inside that exact review card/attempt and authority envelope. It is non-semantic.
- Never reuse a semantic PASS across a card, attempt, commit, tree, specification path/digest, controller source, or product change.
- The canonical per-board Hermes SQLite task/latest-run snapshot is authority; exported JSON and card prose are audit conveniences only.
- Parent-only publication commands reject `HERMES_DELEGATED_CHILD_CONTEXT`; never unset it to bypass the boundary.
- Controller/Hermes-ops defects are separate remediation work with independent exact-tree review. Do not edit controller infrastructure inside the product attempt.
- PR opening and merge remain `UNAUTHORIZED` after acceptance until separately authorized.

## Phase A — before dispatch

1. Copy the three example JSON files to an absolute work-item directory and replace every placeholder.
2. Calculate the approved specification digest from the exact specification commit/path bytes—not the target checkout file.
3. Validate full lowercase 40-character commit/tree identities and the exact product remote/tree.
4. Run the lifecycle preflight and workspace/toolchain readiness checks.
5. Start the timing ledger:

```bash
python3 skills-control-plane/scripts/governancectl.py timing-init \
  --path /absolute/workflow/timings/BUG-NNN.json \
  --work-item BUG-NNN --stage preflight --category active_execution \
  --idempotency-key BUG-NNN-preflight-start
```

## Phase B — same-attempt capability preflight

Create the fresh review card first; use its exact `t_XXXXXXXX` as the attempt ID. Generate non-semantic evidence:

```bash
python3 skills-control-plane/scripts/reviewctl.py \
  /absolute/workflow/contracts/BUG-NNN-review-spec.json \
  --attempt-id t_XXXXXXXX \
  --capability-preflight-output /absolute/workflow/evidence/BUG-NNN-t_XXXXXXXX-capability.json
```

The command must return `semantic_verdict: null`. It runs the real restricted profile/MCP/ref/specification/toolchain/check path without calling the semantic reviewer. If it blocks, do not start semantic-review timing. Close preflight and create separately measured remediation.

## Phase C — fresh semantic review

Validate the sealed same-attempt capability envelope before dispatch. This remains non-semantic and must return `semantic_verdict: null`:

```bash
python3 skills-control-plane/scripts/reviewctl.py \
  /absolute/workflow/contracts/BUG-NNN-review-spec.json \
  --attempt-id t_XXXXXXXX \
  --capability-evidence /absolute/workflow/evidence/BUG-NNN-t_XXXXXXXX-capability.json
```

Attach that exact capability JSON to the already-created fresh Kanban review card. Dispatch the normal restricted reviewer profile named by the review contract. The reviewer must independently inspect the exact target, run fresh product checks, and issue fresh Standards and Specification verdicts with zero findings. Its terminal run metadata must echo the attached capability file SHA-256 as `capability_evidence_sha256`; capability PASS cannot authorize product semantics.

After Kanban completion, normalize it from a normal parent/operator shell. The binder resolves `kanban_board` from the contract to the invoking OS account's canonical shared `~/.hermes` board database using the account database rather than caller-controlled `HOME`, opens SQLite in read-only/query-only mode, and archives the exact latest terminal run ID/profile/timestamps/metadata/parents/log path and snapshot digest. Hermes clears `tasks.current_run_id` on completion; the binder requires that null terminal pointer and authenticates the latest ended terminal run ordered by `ended_at DESC, id DESC`. Active tasks resolve only their exact `current_run_id`. It does not accept an exported terminal file or caller-selected database path:

```bash
python3 skills-control-plane/scripts/governancectl.py parent-check
python3 skills-control-plane/scripts/governancectl.py review-bind \
  --contract /absolute/workflow/contracts/BUG-NNN-review-bind.json \
  --capability /absolute/workflow/evidence/BUG-NNN-t_XXXXXXXX-capability.json \
  --output /absolute/workflow/evidence/BUG-NNN-review-authority.json
```

## Phase D — acceptance

Acceptance must be a fresh card whose exact parent set contains only the review card. Fill the acceptance request with the SHA-256 of `BUG-NNN-review-authority.json`, all required checks, the board slug, an explicit `expected_acceptance_profile` (or `null` for exact unassigned/operator mode), and the same exact authority. The canonical task assignee and latest terminal-run profile must both equal that field. Complete even an unassigned/operator card with structured metadata; free-text result or summary alone is not binder authority. Evidence must contain no secret-bearing keys or secret-shaped values and is bounded to 4096 UTF-8 bytes per check. The canonical acceptance run metadata must independently contain `verdict: PASS`, the exact review card and review-authority digest, identical authority, and the identical ordered checks. Immediately before publication, the binder recaptures both review and acceptance snapshots in one SQLite transaction. Then bind directly from canonical Kanban:

```bash
python3 skills-control-plane/scripts/governancectl.py acceptance-bind \
  --request /absolute/workflow/contracts/BUG-NNN-acceptance-bind.json \
  --review-authority /absolute/workflow/evidence/BUG-NNN-review-authority.json \
  --output /absolute/workflow/evidence/BUG-NNN-acceptance-authority.json
```

The normalized result always records `pr_opening: UNAUTHORIZED` and `merge: UNAUTHORIZED`.

## Timing categories

Maintain exactly one open interval:

- `active_execution`: implementation, tests, preflight, semantic review, acceptance checks;
- `queue_wait`: waiting for card dispatch/worker completion;
- `reviewer_remediation`: separately authorized infrastructure investigation/fix/review;
- `operator_delay`: waiting for human action/availability.

Use `timing-transition` at each boundary and `timing-finalize` once. Report category totals, stage totals, and total wall time; do not relabel wait as execution or hide remediation.

## Canary acceptance target

Compare with BUG-009, but do not turn the comparison into an authorization shortcut. The warm path passes only if:

- no known infrastructure defect recurs;
- all exact-evidence and independent-review gates remain intact;
- preflight, queue, execution, remediation, operator delay, acceptance, and total wall intervals are separately reported;
- no controller edit occurs inside the product attempt;
- the independently reviewed canary report authorizes adoption.
