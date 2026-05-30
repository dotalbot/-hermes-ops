# Review: Kanban default runbook

Task: `t_7839db9f`
Reviewed file: `docs/runbooks/kanban-default-for-multi-step-hermes-projects.md`

## Result

The runbook meets the acceptance criteria. No required fixes were found, and no small corrections were needed.

## Acceptance criteria check

- Short runbook exists under `docs/runbooks/` and is linked from `docs/README.md`.
- The first example is the current Hermes Agent operations board: `continuous-hermes-improvement`, with durable repo `/home/jellybot/hermes-ops`.
- User commands are clear and command-oriented for board selection, assignee discovery, task creation, dependency links, dispatch, promotion, review gates, unblock/change requests, runs/logs, diagnostics, and reclaim.
- No invented worker profile names appear. The runbook uses `default`, which is present in both `hermes profile list` and `hermes kanban --board continuous-hermes-improvement assignees`.
- Profile discovery is documented with `hermes profile list` and `hermes kanban assignees`.
- Trigger rules for choosing Kanban over chat are covered.
- Standard statuses are covered: `triage`, `todo`, `ready`, `running`, `blocked`, `scheduled`, `done`, and `archived`.
- Board separation is covered for `continuous-hermes-improvement`, `home-network`, `portfolio`, cert-study/learning tracks, and new long-lived projects.
- Operational commands are covered for views, dispatch, promotion, logs/runs, diagnostics, and reclaim.
- Human-in-the-loop review gates are covered, including `review-required:` blocking, reviewer inspection, unblock approval/change requests, and dependent child dispatch after completion.

## Verification commands run

```bash
hermes kanban boards list
hermes kanban boards show
hermes kanban --board continuous-hermes-improvement assignees
hermes profile list
hermes kanban --board continuous-hermes-improvement create --help
hermes kanban --board continuous-hermes-improvement promote --help
hermes kanban --board continuous-hermes-improvement unblock --help
git diff --check
```
