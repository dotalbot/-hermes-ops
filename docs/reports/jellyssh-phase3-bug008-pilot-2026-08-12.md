# JellySSH Phase 3 BUG-008 pilot closeout — 2026-08-12

## Outcome

The first governed JellySSH product pilot completed successfully. BUG-008 moved through approved specification, lifecycle preflight, operator release, remote implementation, exact-commit review, bounded remediation, affected-axis rereview, acceptance, pull request, explicit merge authorization, and post-merge reconciliation.

This report records the completed pilot. It does not authorize release, signing, sideloading, installation, deployment, privilege use, secrets, LogK work, or an automatic transition to another phase.

## Product result

BUG-008 fixed successful zero-byte SFTP upload and download handling. A valid empty progress stream previously caused `Stream.last` to throw `Bad state: No element`; the accepted implementation waits for normal stream completion with `drain()` while preserving non-empty progress and stream-error propagation.

Changed product paths:

- `docs/bugs/BUG-008-zero-byte-sftp-transfers.md`
- `app/lib/screens/sftp/sftp_browser_screen.dart`
- `app/test/screens/sftp/sftp_browser_screen_test.dart`

Product authority:

- Repository: `git@github.com:dotalbot/jellyssh.git`
- Branch: `fix/bug-008-zero-byte-sftp-transfers`
- Reviewed head: `64c578a169425af01226a40ef7247add24349248`
- Reviewed tree: `256b61deb2125d8afeab31b32bc4555522eea441`
- Pull request: <https://github.com/dotalbot/jellyssh/pull/2>
- Merge commit: `eaa2974bf61746c53c5ba9cada9fbb35414e2caf`
- Merge parents: `e5afc55d43d122c1e03f64667177c12d98c91412` and `64c578a169425af01226a40ef7247add24349248`
- Merge tree: `256b61deb2125d8afeab31b32bc4555522eea441`

The merge tree exactly equals the reviewed tree, so merge-time resolution introduced no byte changes.

## Lifecycle and evidence

The lifecycle-aware preflight was exercised before implementation release:

- Negative pre-alignment evidence: `skills-control-plane/generated/evidence/bug-008-pre-alignment.json`
- Negative evidence SHA-256: `9961d5a6aab4c37be61c2f3b71a8225ea16eb444d488c21f2e391491d8c61c63`
- Aligned implementation-release evidence: `skills-control-plane/generated/evidence/bug-008-implementation-release.json`
- Aligned evidence SHA-256: `815ce3a0d8363a9bd8b1425562ad8fa4f760d8fad071f01ad2594042d50540c6`
- Aligned evidence verdict: `PASS`
- Aligned evidence source authority: control-plane commit `6d0424b89ea9a7b5cf774a9397fa38414d0a760c`

The aligned artifact is deliberately preserved as historical, time-bound evidence. Later compact-review commits changed `projectctl.py` and `runtime.yaml`; regenerating the earlier release artifact from later source would falsify its original observation boundary.

The gate proved:

- the implementation task could not dispatch before its parent completed;
- successful preflight did not itself assign or spawn implementation;
- the child remained nonspawnable until an explicit audited assignment;
- implementation, review, and acceptance remained separate stages;
- historical blocked attempts stayed inspectable.

## Verification and review

Recorded product verification:

- Focused SFTP browser tests: 17 passed.
- Full Flutter suite: 716 passed, 0 failed, 0 skipped.
- Flutter analyzer: no issues.
- Dart formatting and repository diff checks: clean.
- Restricted full-suite proof: protocol `0.1.1`, terminal `done`, exit 0, `success=true`.
- Independent Standards axis: PASS.
- Independent Specification axis: PASS.
- Final findings: zero after the stale-comment remediation and affected-axis rereview.

The compact reviewer path kept the raw Flutter machine stream inside disposable sandbox scratch and returned an 854-byte validated summary over MCP. The retained summary is `skills-control-plane/projects/jellyssh/evidence/flutter-test-compact-summary.json` (`sha256:c2118f1a86e772448dfd53cc8789c67a2a0f84bc5e596275dfc5a6db1bae0134`).

## Post-merge reconciliation

After explicit operator merge authorization:

- GitHub reported PR #2 merged and closed at `2026-08-12T08:01:02Z` by `dotalbot`.
- Jellyberry `/home/jellybot/dev_projects/jellyssh` was clean on `main` at `eaa2974bf61746c53c5ba9cada9fbb35414e2caf`.
- Jellybase `/home/jellydev/dev_projects/jellyssh` was clean on `main` at the same commit.
- Jellybase `/home/jellydev/dev_projects/jellyssh-review` was clean on `main` at the same commit.
- The corrected acceptance card received merge/tree/checkout reconciliation evidence.
- Historical blocked review `t_bc5b0bc1` and superseded acceptance `t_14d82b5b` remain preserved rather than rewritten.
- No product or control-plane worker remained ready or running at closeout.

## What the pilot proved

The pilot established that the governed route can:

1. fail closed before authority and board alignment;
2. release exactly one unassigned dependent implementation card after evidence review;
3. execute remotely in a project-bound implementation checkout;
4. independently review an immutable pushed commit in a separate restricted checkout;
5. preserve passed review axes across a comment-only remediation while rerunning affected axes;
6. carry bounded, terminally complete Flutter evidence through MCP;
7. stop at human PR and merge gates;
8. reconcile GitHub, local/remote checkouts, and Kanban without erasing failed history.

One successful pilot proves viability, not repeatability.

## Authorized next step

The operator authorized:

1. preparing and opening the Hermes-ops lifecycle-infrastructure PR, without merging it absent a separate instruction; and
2. preparing one second small JellySSH pilot with an offline deterministic seam, without dispatching product implementation before its lifecycle prerequisites and specification are accepted.

The recommended repeatability candidate is a narrow SFTP Retry single-flight bug: rapid Retry input can overlap asynchronous SFTP acquisition before the loading rebuild disables the control, allowing one service to be overwritten and leaked. Its proposed retained seam uses controlled completers and two Retry taps without an intervening pump. Selection and implementation remain separate from this closeout and require their own specification, branch, preflight evidence, review, PR, and merge gates.

LogK remains outside scope until a later explicit transition decision.
