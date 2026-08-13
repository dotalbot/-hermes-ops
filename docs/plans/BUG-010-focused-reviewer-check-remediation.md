# BUG-010 focused reviewer check remediation

## Problem

The merged certified reviewer warm path hard-codes `sftp-browser-test` into every `final` review. That fixed check was correct for BUG-009 but is not the changed widget/test seam for BUG-010. Dispatching BUG-010 without correcting this would defer predictable reviewer remediation until after implementation and repeat the slow BUG-009 workflow.

## Design

- Add `focused_check` to the review specification.
- Require it for `final` reviews.
- Permit only a closed enum of controller-owned check identities:
  - `sftp-browser-test`
  - `terminal-behaviour-test`
- Do not accept paths or commands from callers.
- Map `terminal-behaviour-test` internally to exactly:
  `test/screens/settings/terminal_behaviour_settings_screen_test.dart`.
- Preserve the compact, fail-closed Flutter machine-output contract.
- Preserve BUG-009 compatibility by retaining `sftp-browser-test` in the enum and command map.
- Bind the selected focused check into capability evidence through the authenticated review specification bytes.

## TDD seams

1. Review-spec parser: final review without a focused check or with an arbitrary value fails closed.
2. Required-check inventory: final review includes exactly the selected closed-enum focused check.
3. Boundary allowlist/command map: the terminal check runs only the fixed widget test path.
4. Compact reporter: the terminal focused-check identity is preserved and arbitrary identities remain invalid.
5. Integrity manifests and schemas are updated and verified.

## Security review remediation

The first adversarial lane timed out after identifying that direct in-memory
capability validation did not share the file loader's focused-check semantics.
A bounded replacement review classified this as HIGH: a hash-authenticated
non-final specification could carry an unused focused selector into the binder.

The remediated design:

- uses one `validate_review_specification()` implementation for file loading,
  capability generation, capability validation, and governance binding;
- constrains embedded review specifications in the capability JSON schema;
- requires governed review binding to consume a valid `final` specification;
- publishes both `review_type` and `focused_check` in governed review authority;
- retains the original timeout and BLOCK as non-authorizing evidence and requires
  fresh security/provenance review of the changed candidate.

## Non-goals

- No product code changes.
- No arbitrary focused-test paths.
- No model, provider, sandbox, SSH, auth, Kanban, or routing changes.
- No PR creation, merge, fleet-routing change, or deployment without separate authorization.

## Rollback

Discard branch `fix/bug010-focused-review-check` and keep production control-plane checkout at merged PR #7 (`0db01da5...`). Product implementation remains undispatched until the remediation is reviewed and adopted.
