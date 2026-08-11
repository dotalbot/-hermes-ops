# JellySSH lifecycle-aware dispatch preflight

**Status:** Proposed prerequisite design for BUG-008
**Date:** 2026-08-11
**Repository:** `dotalbot/-hermes-ops`
**Base:** `0523e6d414a515d3009d12e5e6abc32d96aa3451`

## Problem

`projectctl scan` correctly verifies the immutable Phase-2 bootstrap authority, but its live checks also require every JellySSH checkout to remain on the original intake commit and the board to remain empty. A completed work cycle therefore appears as drift. Native Kanban dispatch has no project-preflight argument, so an ordinary Ready card is not linked to control-plane evidence.

BUG-008 must not bypass these failures. The process correction is a prerequisite and remains separate from JellySSH product code.

## Design

Keep bootstrap/static scanning and per-work-item lifecycle validation as separate interfaces.

Add:

```text
projectctl.py --project <project.yaml> --json \
  preflight --contract <work-item.json> --output <evidence.json>
```

The contract is a short-lived controller-owned input for one project phase. It is not a replacement for the approved bug specification or the immutable runtime manifest.

The command must:

1. Validate the contract with a checked-in JSON Schema and reject unknown fields.
2. Reuse static control-plane validation without enforcing obsolete bootstrap-only checkout and empty-board expectations.
3. Validate each declared checkout against exact remote, SHA, branch/detached state, cleanliness, transport, and configured path.
4. run exact-ref operations with `GIT_NO_REPLACE_OBJECTS=1`.
5. Validate local and remote bridge resolution, approved profiles, model/provider/fallback policy, skill hashes, pinned host identity, reviewer sandbox/toolchain, and conservative concurrency.
6. Read the named board without mutation and validate the declared task IDs, parent links, assignees, workspaces, and permitted statuses.
7. Reject an implementation-release contract unless its preflight parent exists and the implementation task is both dependent on that parent and sticky-blocked for operator release.
8. Write evidence atomically beneath the control plane's generated/evidence directory. Evidence includes the contract digest, observed exact state, check results, source digests, timestamp, and PASS/BLOCK verdict.
9. Return non-zero on every schema, authority, observation, or write failure.

## Kanban gate

For each JellySSH implementation:

1. Create an unassigned preflight parent card.
2. Create the implementation card assigned to `jellybase_jellyssh`, dependent on that parent, and initially sticky-blocked.
3. Run `projectctl preflight` against a contract naming both cards.
4. Attach/comment the exact evidence path and digest, then complete the preflight parent only on PASS.
5. The implementation card remains blocked after the parent completes.
6. The operator explicitly unblocks/promotes the implementation card.
7. The dispatcher and claim path independently reject the child if its parent is not done unless an operator deliberately uses the audited `--force` override.

Review and acceptance cards remain separate children. Exact target/base fields are introduced only after implementation produces a pushed immutable commit.

## BUG-008 implementation-phase contract

The first real contract must bind:

- Project: `jellyssh`
- Work item: `BUG-008`
- Phase: `implementation-release`
- Repository: `git@github.com:dotalbot/jellyssh.git`
- Base: `e5afc55d43d122c1e03f64667177c12d98c91412`
- Approved specification: `f6ba58ddeb204437e5a1ec392bb47d892839ef16`
- Branch: `fix/bug-008-zero-byte-sftp-transfers`
- Coordinator and implementation checkouts: approved specification commit on the feature branch, clean
- Coordinator-review and reviewer checkouts: merged base on `main`, clean
- Board: `jellyssh`
- Implementation assignee: `jellybase_jellyssh`
- Implementation status before release: sticky `blocked`
- Concurrency: one spawn and one in-progress item

## Tests

Add focused tests that prove:

1. the current bootstrap `scan` behavior remains unchanged;
2. a valid lifecycle contract passes with mocked local/SSH/board observations;
3. unknown contract fields fail closed;
4. checkout SHA, branch, remote, dirty-tree, and replacement-ref drift block;
5. missing/wrong parent links block;
6. a Ready or Running implementation card before operator release blocks;
7. wrong assignee/workspace/board blocks;
8. evidence output cannot escape the controlled directory and is atomic;
9. no evidence is written with verdict PASS when any check fails;
10. CLI exit codes and JSON output are deterministic.

Run the focused control-plane suite, full control-plane suite, Python compilation, and `git diff --check`.

## Scope limits

- No JellySSH production or test code.
- No Hermes Agent core change.
- No global Kanban dispatcher disablement.
- No automatic operator approval.
- No merge, release, deployment, signing, installation, or credential mutation.
- No attempt to model every future project lifecycle phase in this change.

## Rollback

Before merge, delete the feature branch and generated local evidence. After merge, revert the process commit; existing boards and profiles remain usable because the new preflight interface is additive. Never roll back by modifying live board SQLite directly.

## Acceptance

- Independent review finds no blocking issue in the exact process commit.
- A negative BUG-008 contract fails before checkout/card alignment.
- The aligned BUG-008 contract passes and produces digest-addressed evidence.
- The dependent implementation card cannot dispatch before parent completion and remains blocked after parent completion until the operator releases it.
