# JellySSH Compact Flutter Test Evidence Implementation Plan

> **For Hermes:** Implement this plan directly with one red/green slice per contract case, then run independent review.

> **Status (2026-08-12):** implemented, verified, affected-axis rereview passed, and exercised by the accepted BUG-008 pilot.

**Goal:** Make the restricted JellySSH `flutter-test` check return bounded, machine-readable, fail-closed evidence that survives the MCP bridge while preserving the existing sandbox and exact-commit controls.

**Architecture:** Run Flutter with its JSON machine reporter inside the existing disposable network-none container, redirect the unbounded event stream to sandbox scratch, and summarize it there before any output crosses SSH/MCP. The trusted controller accepts only a versioned exact JSON summary with a terminal `done` event, internally consistent counts, zero failures, successful process exit, and bounded diagnostics.

**Tech Stack:** Python standard library, Flutter/Dart machine reporter, Docker sandbox, MCP controller, unittest, YAML/JSON governance manifests.

---

## Scope and seams

Public seams under test:

1. `run_readonly_check("flutter-test")` / `ReviewRepository.run_check("flutter-test")` returns the compact JSON contract rather than raw Flutter progress.
2. The fixed reporter program consumes synthetic Flutter JSON event streams and exits success only for a complete, internally consistent successful run.
3. `reviewctl._validate_check_output("flutter-test", ...)` accepts only the exact compact success contract used by controller evidence collection.

Non-goals:

- No JellySSH product or checkout changes.
- No relaxation of exact materialization, read-only mounts/root, network-none, tmpfs/storage, PID/memory/swap/CPU, timeout, no-new-privileges, pinned transport, or sequential checks.
- No parsing of human-readable Flutter progress and no substring-based `PASS` acceptance.

## Task 1: RED — specify the compact reporter contract

**Files:**
- Modify: `skills-control-plane/tests/test_review_boundary.py`
- Modify: `skills-control-plane/tests/test_projectctl.py`

1. Add a synthetic event stream large enough to demonstrate raw-output truncation risk.
2. Assert the reporter returns one bounded JSON object with schema/check/reporter/protocol, original exit, terminal marker, success, pass/fail/skip/total counts, and bounded diagnostics.
3. Add malformed, missing-terminal, duplicate/contradictory terminal, failed-test, and nonzero-exit cases; each must fail closed.
4. Assert controller validation rejects raw `PASS`, malformed JSON, contradictory counts, missing/incorrect terminal state, nonzero exit, failed totals, and oversized diagnostics.
5. Run the focused cases and confirm RED because the fixed command still emits raw progress and the controller has no Flutter-test output contract.

## Task 2: GREEN — summarize the machine reporter inside the sandbox

**Files:**
- Modify: `skills-control-plane/scripts/review_boundary.py`
- Modify: `skills-control-plane/scripts/reviewctl.py`

1. Add a bounded standard-library reporter program for newline-delimited Flutter JSON events.
2. Run only `flutter test --machine --no-pub` for `flutter-test`, capturing its event stream in disposable `/workspace` scratch.
3. Pass the real Flutter exit code to the reporter and emit only its canonical compact JSON summary across Docker/SSH/MCP.
4. Require exactly one valid start, exactly one final done event, no events after done, valid non-hidden test completion results, no duplicate completions, consistent totals, `done.success=true`, exit `0`, no failed tests, and at least one visible test.
5. Keep diagnostics count/string/output byte limits fixed; malformed input must emit a compact failure summary and return nonzero.
6. Update controller validation to parse and validate the exact success contract.
7. Run each focused test after its minimal implementation and confirm GREEN.

## Task 3: Governance, documentation, and retained evidence

**Files:**
- Modify: `skills-control-plane/README.md`
- Modify: `docs/reports/jellyssh-phase2-routing-2026-08-09.md`
- Modify: `skills-control-plane/projects/jellyssh/runtime.yaml`
- Modify only if required by retained-evidence fields: `skills-control-plane/schemas/runtime-state.schema.json`, `skills-control-plane/scripts/projectctl.py`
- Create: `skills-control-plane/projects/jellyssh/evidence/flutter-test-compact-summary.json`

1. Document the JSON reporter and fail-closed terminal/count semantics.
2. Run the real restricted check at frozen JellySSH target `da96d24bf57daf47ee5f8a238e8c5f940f3cae3d` and retain its compact summary, output byte count, exact target, sandbox controls, and before/after board/checkout invariance without raw logs or secrets.
3. Bind retained evidence and changed governed source hashes in runtime authority; update schema/control validation only where required.
4. Recompute hashes mechanically and run integrity tests.

## Task 4: Verification, review, and delivery

1. Run focused boundary/controller tests.
2. Run the complete relevant control-plane suite and repository test suite, Python compilation, and `git diff --check`.
3. Re-run the real sandboxed Flutter suite and prove the compact output is bounded and has exact totals/terminal success.
4. Confirm CHI and JellySSH board task-ID counts/digests and all local/remote JellySSH checkout states match the initial snapshots.
5. Independently review the exact diff for security, fail-closed semantics, test quality, governance consistency, and preservation of sandbox controls; remediate blocking findings.
6. Commit and push `feat/lifecycle-aware-dispatch-preflight`. Do not open a PR, merge, release, or deploy.
7. Comment the exact target/tree/diff/tests/rollback handoff and block the card with `review-required:` for affected-axis review.

## Completion evidence

- Focused RED/GREEN reporter and controller tests pass, including malformed JSON, incomplete protocol versions, missing/duplicate/contradictory terminal records, nonzero exit, failed/hidden/incomplete tests, unknown event types, malformed progress records, and Unicode diagnostic byte bounds.
- `106` control-plane tests and all `8` repository tests pass. Repository tests validate checked-in schema, authority, hashes, and retained evidence hermetically; live mutable profile, checkout, MCP, board, network, and rollback drift remains an explicit `projectctl scan`/per-ticket preflight gate.
- `python3 -m py_compile skills-control-plane/scripts/*.py`, `git diff --check`, and `managerctl.py verify` pass.
- The actual MCP `run_readonly_check("flutter-test")` against frozen target `da96d24bf57daf47ee5f8a238e8c5f940f3cae3d` returns an `854`-byte summary with `716` passed, zero failed/skipped, `terminal=done`, and `success=true`.
- Independent review found hidden/masked/incomplete failure acceptance, unknown-event acceptance, Unicode byte expansion, and incomplete protocol acceptance; all findings were remediated and regression-tested.
- Final board task-ID sets and both remote JellySSH checkout head/status snapshots match the retained before/after evidence.

## Rollback

Revert the latest compact-protocol remediation commit to restore its prior producer grammar and governed hashes/evidence binding. This reintroduces acceptance of incomplete protocol versions, but does not modify either live board, any JellySSH checkout, profile, deployment, or product source.
