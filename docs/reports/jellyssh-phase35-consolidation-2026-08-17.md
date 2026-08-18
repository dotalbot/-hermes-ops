# JellySSH Phase 3.5 consolidation — 2026-08-17

## Purpose

Reconcile the JellySSH pilot's completed operational history after BUG-011 so that the board and control-plane documentation remain useful without erasing failed or superseded evidence.

This report is an operations record. It does not authorize product implementation, dispatch, a pull request, merge, release, signing, installation, deployment, privilege use, secrets, or LogK work.

## Authorities consulted

1. Live JellySSH Kanban board on Jellyberry.
2. JellySSH Git remote and clean Jellybase source checkout.
3. The Phase 2 bootstrap manifests in `skills-control-plane/projects/jellyssh/`.
4. Existing Phase 3 BUG-008 closeout report.

Git and the live board override older card prose and generated snapshots when they disagree.

## Reconciled product state

JellySSH `main` is at `dd1f313d8247cdb8800e2d973bf0b2aab24f0272` and includes the BUG-011 merge:

```text
b2208ee Merge pull request #4 from dotalbot/fix/bug-011-sftp-transfer-exit-lifecycle
37899dd docs: record BUG-011 verification
609557f fix: BUG-011 clean up SFTP transfer UI on exit
```

The merged BUG-011 target is `37899ddfda6a1d13867d8e4fb25420e1692972ed`. Its Kanban chain recorded an implementation PASS, independent Standards and Specification PASS rereview, and acceptance evidence. Earlier acceptance-card prose saying that a PR or merge remained unauthorized is historical at the time it was written and is not current authority.

The inspected dedicated Claude checkout at `/home/jellyclaude/dev_projects/jellyssh` was clean on `main` at `dd1f313`.

## Board reconciliation

Four blocked cards were archived after a reconciliation comment established that later accepted exact-target chains superseded them:

- `t_bdd86be5` — BUG-009 first review.
- `t_4bfb3176` — BUG-009 second review.
- `t_47ca853d` — BUG-010 placeholder review.
- `t_5e689251` — BUG-010 auto-created review before immutable binding.

Two BUG-008 records deliberately remain unarchived:

- `t_bc5b0bc1` is immutable historical BLOCK evidence.
- `t_14d82b5b` is its dependency-held TODO child and remains nonspawnable.

They were given explicit reconciliation comments. The later corrected acceptance `t_9473e5f1` remains the authoritative completed BUG-008 path.

After reconciliation the board has 26 done cards, one blocked historical record, one nonspawnable TODO historical record, and zero ready or running cards. Board diagnostics report no active warnings.

## Projection policy

`skills-control-plane/projects/jellyssh/project.yaml` and `runtime.yaml` are Phase 2 bootstrap authority. Their state intentionally describes an old, frozen setup boundary. Therefore `skills-control-plane/generated/jellyssh-status.{md,json}` is retained as a historical derived projection and must not be read as current operational status.

The replacement operational projection is:

- `skills-control-plane/generated/jellyssh-operational-status.md`
- `skills-control-plane/generated/jellyssh-operational-status.json`

Those files point back to this report and explicitly distinguish their live observation from the retained bootstrap baseline.

## Control-plane repository reconciliation

The primary `hermes-ops` checkout had been detached at `f9fbc6b`. It was placed on `chore/jellyssh-phase35-consolidation`, based on merged `origin/docs/kanban-workspace-standard`, which contains the governed Claude adapter merge. The following untracked generated evidence artifacts were retained for review and tracking rather than discarded:

- `bug-010-final-controller-preflight.json`
- `bug-010-implementation-release.json`
- `bug-011-lifecycle-preflight-initial.json`
- `bug-011-lifecycle-preflight.json`

## Remaining follow-up

The next technical decision is separate from this consolidation: whether to formalize the governed Claude adapter as an approved normal implementation/review route, or keep the Hermes OpenAI-Codex worker route primary. LogK remains a later Jellyhome/OpenCode adapter transition and is not affected by this work.
