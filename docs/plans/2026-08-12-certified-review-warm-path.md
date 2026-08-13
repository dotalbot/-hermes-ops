# Certified Review Warm Path Implementation Plan

> **For Hermes:** Implement directly in the isolated `feat/certified-review-warm-path` worktree using TDD, then independently review the exact candidate tree before publication.

**Goal:** Make future governed Kanban bugs use a pre-certified, measured reviewer path without weakening exact authority, independent review, acceptance, PR, or merge gates.

**Architecture:** Add two deep modules. `reviewctl.py` owns an exact-attempt capability-evidence envelope that runs the existing restricted MCP/toolchain readiness path before semantic review. The operator validates and attaches that authenticated non-semantic envelope to a fresh Kanban review card; the reviewer performs fresh semantic analysis and policy-required product checks, then echoes the exact capability-file digest in terminal metadata. `governancectl.py` authenticates that cross-artifact binding and owns parent-context checks plus an atomic timing state machine that reports active execution, queue/wait, reviewer remediation, operator delay, and total wall time without overlap or double counting.

**Tech Stack:** Python standard library, existing MCP/reviewer controller, JSON Schema Draft 2020-12, unittest, Git exact-object authority, atomic filesystem publication.

---

## Decisions

1. Implement the reusable machinery before another product bug.
2. Validate it during the next small real bug as a measured canary.
3. Do not modify reviewer infrastructure inside that product attempt. A newly discovered infrastructure defect becomes a separately timed and independently reviewed Hermes-ops remediation.
4. Capability evidence is not a semantic verdict. It never contains or authorizes `PASS` for product meaning.
5. Capability evidence may be consumed only by the same exact attempt and exact base/specification/path/target envelope, with unchanged authenticated controller bytes and repository metadata.
6. Exact product review, manual acceptance, PR opening, and merge remain separate gates.
7. Parent/operator Kanban mutation fails immediately when `HERMES_DELEGATED_CHILD_CONTEXT` is present.
8. Canonical per-board Kanban SQLite task/current-run state is authoritative; caller-exported terminal JSON and card prose are audit conveniences only.

## Task 1: RED — capability envelope contract

**Files:**
- Create: `skills-control-plane/schemas/reviewer-capability-evidence.schema.json`
- Modify: `skills-control-plane/tests/test_projectctl.py`

1. Specify a closed envelope containing kind/version, attempt ID, exact review specification and canonical digest, authenticated controller source/schema digests, approved specification path/digest, bounded MCP evidence and digest, repository metadata, UTC creation identity, and `PASS|BLOCK` capability verdict.
2. Add tests proving unknown keys, substituted attempt/base/specification/path/target, altered evidence, altered controller bytes, and old semantic result replay all fail closed.
3. Prove capability generation does not call the semantic model.
4. Prove capability validation does not rerun expensive checks but does revalidate profile, controller bytes, exact repository metadata, cleanliness, and envelope digests.

## Task 2: GREEN — certified capability preflight

**Files:**
- Modify: `skills-control-plane/scripts/reviewctl.py`
- Modify: `skills-control-plane/projects/jellyssh/runtime.yaml`
- Modify: `skills-control-plane/generated/fleet-status.json`

1. Add `--capability-preflight-output ABSOLUTE_JSON --attempt-id t_<id>` to run profile/repository verification and the real restricted MCP evidence collector without invoking the semantic model.
2. Publish the envelope atomically and fail closed on symlinks, unsafe paths, partial writes, schema drift, or source drift.
3. Add `--capability-evidence ABSOLUTE_JSON --attempt-id t_<id>` to validate the sealed envelope before Kanban dispatch without invoking semantic review.
4. Authenticate one bounded byte snapshot, validate its schema and all exact bindings, and revalidate live immutable/runtime boundaries. Attach the exact file to the fresh review card; do not reuse its readiness checks as the semantic verdict or product-test evidence.
5. Keep the legacy direct semantic path for compatibility, but the new Kanban warm-path template must require capability-file attachment and terminal digest echo.

## Task 3: RED/GREEN — authoritative timing and parent context

**Files:**
- Create: `skills-control-plane/scripts/governancectl.py`
- Create: `skills-control-plane/schemas/governance-timing.schema.json`
- Create: `skills-control-plane/tests/test_governancectl.py`

1. Add `parent-check`, which rejects delegated-child context and emits canonical JSON.
2. Add atomic timing commands: `timing-init`, `timing-transition`, and `timing-finalize`.
3. Record one non-overlapping interval at a time with category `active_execution`, `queue_wait`, `reviewer_remediation`, or `operator_delay`.
4. Bind every transition to a unique idempotency key; exact repeats are no-ops and conflicting replays block.
5. Record UTC, monotonic nanoseconds, and boot identity; reject cross-boot monotonic finalization.
6. Report category totals, stage totals, total wall time, and any unattributed gap. Require the interval sum plus explicit gap to equal total wall time within nanosecond arithmetic.
7. Never reinterpret timeout/BLOCK as PASS.

## Task 4: Fixture and reusable workflow template

**Files:**
- Create: `skills-control-plane/fixtures/reviewer-capability/specification.md`
- Create: `skills-control-plane/fixtures/reviewer-capability/README.md`
- Create: `skills-control-plane/templates/governed-bug-workflow/README.md`
- Create: `skills-control-plane/templates/governed-bug-workflow/review-card.md`
- Create: `skills-control-plane/templates/governed-bug-workflow/acceptance-card.md`
- Modify: `skills-control-plane/README.md`

1. Document deterministic/offline fixture tests for ref closure, authenticated specification bytes, result schema, tamper/replay rejection, and timing transitions.
2. Document the live capability preflight as a separate timed stage before semantic review.
3. Document structural cacheability versus per-attempt freshness.
4. Require fresh review and acceptance cards, `max_runtime: 20m`, `max_retries: 1`, and `workspace: scratch` for each semantic product review.
5. Require a canonical per-board Hermes SQLite task/latest-terminal-run snapshot as authority, archived with exact run/profile/timestamps/metadata/parents/log path and detection timestamps. Match Hermes lifecycle semantics: terminal tasks have `current_run_id = NULL`, and authority comes from the latest ended terminal run ordered by `ended_at DESC, id DESC`; active tasks resolve only their exact `current_run_id`. Require structured metadata; exported JSON and free-text completion prose are audit conveniences only. Keep parent-only mutation entry checks.
6. Keep PR opening and merge as separately authorized actions.
7. Resolve the shared Hermes root from the invoking OS account database, not caller-controlled `HOME`; bind acceptance to an explicit producer/null mode, the exact single review parent, and one final transaction covering both review and acceptance snapshots.
8. Treat atomic rename as the publication commit point across every authoritative/generated single-file output, including manager, status, lifecycle, capability, timing, review, and acceptance outputs. Open the directory handle before rename; failures before rename leave no new PASS target and public CLI seams translate them to structured BLOCK, while post-commit directory durability/cleanup is best effort and cannot turn exposed PASS into a reported failure. Do not attempt fallible unlink/truncate repair after exposure.

## Task 5: Verification and independent certification

1. Run focused capability/timing tests.
2. Run the complete control-plane suite and repository suite.
3. Run Python compilation, JSON Schema validation, manager verification, credential scan, and `git diff --check`.
4. Run one real capability preflight against the already accepted immutable BUG-009 authority as a non-semantic route proof. It must not create a review card or emit a semantic verdict.
5. Seal the exact candidate tree.
6. Run independent integration/schema and security/provenance reviews against that exact tree.
7. Remediate findings in a new exact tree and rereview affected axes. A prior tree's PASS never authorizes a later tree.
8. Commit and push the exact independently authorized tree. Do not open or merge a Hermes-ops PR without separate authorization.

## Task 6: Next small bug canary

1. Choose a small deterministic JellySSH bug with no new trust boundary.
2. Run capability preflight before semantic-review timing.
3. Use fresh exact specification, implementation, review, and acceptance cards.
4. Forbid Hermes-ops/controller edits inside the product attempt.
5. Compare active execution, queue/wait, remediation, operator delay, semantic review, acceptance, and total wall time with BUG-009.
6. Promote the template to the normal path only after the canary passes and a separately reviewed report confirms no gate was weakened.

## Acceptance

- Capability preflight fails before semantic review on profile/MCP/ref/specification/toolchain/schema drift.
- Exact preflight evidence is authenticated, attempt-bound, and non-semantic.
- Fresh semantic Kanban review authenticates the attached same-attempt capability-file digest while independently running semantic analysis and policy-required product checks.
- Replay across attempt, commit, specification path/digest, controller tree, or evidence bytes is rejected.
- Timing dimensions are authoritative, non-overlapping, idempotent, and sum to total wall time.
- Parent-only scripts reject delegated-child context rather than unsetting it.
- Existing exact-ref closure, authenticated byte snapshots, independent review, fail-closed acceptance, deterministic tests, and separate PR/merge gates remain intact.

## Rollback

Before merge, delete the feature worktree/branch. After merge, revert the warm-path commit and use the existing direct reviewer path. Never roll back by widening ref access, reusing a semantic PASS, bypassing delegated-child context, or mutating Kanban SQLite directly.
