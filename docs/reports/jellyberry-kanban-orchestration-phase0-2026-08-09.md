# Jellyberry Kanban orchestration V3 — Phase 0 completion report

> **Status:** Phase 0 completed and verified; awaiting operator acceptance
>
> **Completed:** 2026-08-09 04:24 BST
>
> **Authority:** [Jellyberry Kanban orchestration design V3](../operations/multi-agent-development/jellyberry-kanban-orchestration-design-v3.md)

## Scope

Phase 0 repaired and froze the existing Jellyberry control plane. It did not create JellySSH checkouts, boards, profiles, skills, cards, or workers, and it did not begin Phase 1.

## Applied corrections

### Board work directories

| Board | Previous value | Verified value |
| --- | --- | --- |
| `continuous-hermes-improvement` | `/home/jellybot/hermes-ops` | `/home/jellybot/dev_projects/hermes-ops` |
| `home-network` | `/home/jellybot/home-network` | `/home/jellybot/dev_projects/home-network` |
| `portfolio` | `/home/jellybot/portfolio-intel` | `/home/jellybot/dev_projects/portfolio-intel` |

Each destination exists and is a Git worktree. No repository content was changed by the board metadata update.

### Invalid ready card

Card `t_dbcf7e2c`, **Check Docker health on Jellybase**, named the nonexistent assignee `jellybase`. It was moved from `ready` to `blocked` with `block_kind=needs_input` and an audit comment explaining that it must remain non-executable until the operator explicitly rescopes, reassigns, or archives it.

The card was not silently reassigned to `jellybase_hermes`.

### Dispatcher policy

The default-profile configuration now resolves to:

```yaml
kanban:
  auto_decompose: false
  orchestrator_profile: ""
  default_assignee: ""
  max_in_progress: 1
  max_spawn: 1
```

The gateway was restarted after the policy change. Startup logs recorded `max_spawn=1` and `max_in_progress=1`.

### Active documentation

Active multi-agent guides now use `/home/jellydev/dev_projects/<repo>`, distinguish the generic `jellybase_hermes` baseline from approved project-specific routes, prohibit silent profile fallback, and prohibit skill installation or promotion during Phase 0.

The approved V3 and guide updates were independently reviewed, committed, and pushed on `docs/jellyberry-kanban-orchestration-v2`:

- `9bd89b3` — approve Jellyberry orchestration design V3
- `d0a6bf8` — align multi-agent guides with V3 governance

V1 and V2 remain unchanged historical documents.

## Verification evidence

- All named board workdirs resolve to the intended Git-backed paths.
- Card `t_dbcf7e2c` reports `status=blocked`, `assignee=jellybase`, and the Phase 0 audit comment.
- No task on any named board is currently `ready` or `running`.
- Installed profiles remain `default`, `homenetworkworker`, and `jellybase_hermes`.
- All named-board SQLite integrity checks returned `ok`.
- Gateway service is active.
- Hindsight profile routes were rechecked in fresh CLI processes:
  - `default` → `hermes-main`
  - `homenetworkworker` → `home-network-main`
  - `jellybase_hermes` → `jellybase-worker-main`, automatic retention disabled
- Expected Hindsight banks exist and the service is reachable.
- JellySSH checkout, implementation profile, reviewer profile, and board paths are absent.
- LogK repository, profiles, board, Hindsight route, and runtime were not changed.
- Independent documentation rereview returned `REREVIEW PASS`.

## Backups and rollback

Pre-change backups:

```text
/tmp/hermes-phase0-20260809-0220/
/tmp/hermes-phase0-operator-20260809-042401/
```

The first directory contains the pre-policy `config.yaml` and consistent backups of the three affected board databases. The second contains fresh board-database backups taken immediately before the board metadata commands.

To roll back the dispatcher policy, restore the saved `config.yaml` and restart the gateway. To roll back board state, stop the gateway first and use the matching SQLite backups under explicit operator control; never replace a live board database while the gateway is running. The previous board workdir values are recorded in the table above and can be restored through `hermes kanban boards set-default-workdir`.

## Execution note

The guarded helper updated all three workdirs successfully, then stopped before card mutation because its initial `block` argument order was incompatible with the installed CLI. The card was subsequently blocked with the corrected argument order and verified. The helper at `/tmp/hermes-phase0-finish.sh` was corrected and syntax-checked after this finding.

## Gate

Phase 0 completion does not authorize Phase 1. The next action is operator acceptance, revision, or rollback of this report. No skill inventory, model binding, JellySSH preparation, cloning, profile creation, board creation, or dispatch may begin without a new explicit decision.
