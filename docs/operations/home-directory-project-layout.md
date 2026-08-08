# Home directory project layout

**Created:** 2026-08-08 01:24 BST  
**Host/account:** Jellyberry, `jellybot`  
**Purpose:** record the agreed filesystem convention for local project roots so future Hermes profiles, Desktop Projects, Kanban tasks, cron jobs, and operators use the same paths.

## Decision

The `jellybot` home directory now has two project roots:

```text
/home/jellybot/dev_projects/  # Git-backed coding/development repositories
/home/jellybot/projects/      # Non-git project activity and generated/local workspaces
```

Use `dev_projects` for software repositories and agent-maintained codebases. Use `projects` for activity folders that are not currently Git repositories. A folder in `projects` can be promoted later by creating or connecting a Git repository, then moving it into `dev_projects` and updating references.

This convention should be replicated on other agent hosts where practical so profiles and workers can reason about project location consistently.

## What was moved

### Git/development roots moved to `dev_projects`

```text
/home/jellybot/dev_projects/-hermes-ops
/home/jellybot/dev_projects/3dprint_loader
/home/jellybot/dev_projects/Borg_repo_visualiser
/home/jellybot/dev_projects/diagram_creator
/home/jellybot/dev_projects/hermes-ops
/home/jellybot/dev_projects/home-network
/home/jellybot/dev_projects/logk
/home/jellybot/dev_projects/logk_old
/home/jellybot/dev_projects/pokemon-agent
/home/jellybot/dev_projects/portfolio-intel
/home/jellybot/dev_projects/portfolio-intel-logk
```

Notes:

- `diagram_creator` is a container folder; the Git repository root is `dev_projects/diagram_creator/DominicTalbot`.
- `portfolio-intel-logk` is a Git worktree of `portfolio-intel`; after the move it was repaired with `git worktree repair`.
- Existing uncommitted work in each repository was preserved.

### Non-git project/activity folders moved to `projects`

```text
/home/jellybot/projects/ab-900-prep
/home/jellybot/projects/caminao-prep
/home/jellybot/projects/cert-study-hub
/home/jellybot/projects/hindsight-cleanup
/home/jellybot/projects/home-network.kanban-homepage-20260522-223209
/home/jellybot/projects/image-pastebin
/home/jellybot/projects/ms-102-prep
/home/jellybot/projects/sc-100-prep
```

The following top-level folders intentionally stayed under `/home/jellybot` because they are not project roots: `bin`, `Downloads`, `tmux-logs`, and hidden/system folders such as `.hermes`, `.config`, `.ssh`, and `.cache`.

## Current durable workspace mapping

Use these paths for Kanban output roots and profile/project workspaces:

```text
continuous-hermes-improvement -> /home/jellybot/dev_projects/hermes-ops
home-network                  -> /home/jellybot/dev_projects/home-network
portfolio                     -> /home/jellybot/dev_projects/portfolio-intel
logk                          -> /home/jellybot/dev_projects/logk
```

Routine home-network repository work still follows the standing exception: direct `main` commits/pushes are allowed for `/home/jellybot/dev_projects/home-network` when the task is routine home-network work. Other Git repos should use feature branches unless Dominic says otherwise.

## Configuration and source references updated

The migration updated active runtime/config references in these areas:

- `~/.hermes/cron/jobs.json`
- `~/.hermes/scripts/` portfolio, dashboard, and home-network helper scripts
- `~/.config/systemd/user/portfolio-mission-control-v2.service`
- `~/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh`
- `dev_projects/hermes-ops/config/` dashboard inventory/link config
- `dev_projects/hermes-ops/scripts/` dashboard scripts
- `dev_projects/hermes-ops/docs/guides/kanban/` workspace/output docs
- `dev_projects/hermes-ops/docs/runbooks/` affected dashboard, Kanban, backup, and mission-control runbooks
- `dev_projects/hermes-ops/docs/specs/` affected Kanban/dashboard specs
- `dev_projects/home-network/inventory/services.yml`
- `dev_projects/home-network/docker/hosts/*.yaml`
- `dev_projects/home-network/systemd/*`
- `dev_projects/home-network/scripts/install-seedit4me-reverse-tunnel`
- selected `dev_projects/home-network/docs/operations/` and restore docs that named runtime source paths
- `dev_projects/portfolio-intel/config/*`
- `dev_projects/portfolio-intel/scripts/*`
- selected `dev_projects/portfolio-intel` operator documentation

Historical logs, cron output archives, session transcripts, and old skill backup archives were not rewritten. Those are evidence/history, not current configuration.

## Verification performed during the migration

Checks completed successfully:

- Confirmed no moved project folders remain directly under `/home/jellybot`.
- Confirmed every moved Git root resolves with `git rev-parse --show-toplevel`.
- Repaired and verified the `portfolio-intel-logk` Git worktree.
- Parsed JSON successfully for:
  - `~/.hermes/cron/jobs.json`
  - `dev_projects/hermes-ops/config/dashboard-inventory.json`
  - `dev_projects/hermes-ops/config/dashboard-links.json`
- Compiled updated Python helper scripts with `python3 -m py_compile`.
- Syntax-checked updated shell scripts with `bash -n`.
- Reloaded user systemd units with `systemctl --user daemon-reload`.
- Verified `portfolio-mission-control-v2.service` now points at `/home/jellybot/dev_projects/portfolio-intel`.
- Verified the updated Jellyberry compose file with `docker compose -f dev_projects/home-network/docker/hosts/jellyberry.yaml config --quiet`.
- Verified referenced migrated project roots in compose/inventory/dashboard config exist.
- Checked that no active process was still running from the old project-root paths.
- Listed Hermes cron jobs successfully after the migration.

Known unrelated blocker observed during verification:

- `docker compose -f dev_projects/home-network/docker/hosts/jellyhome.yaml config --quiet` failed because `/opt/docker/.secrets/hindsight/hindsight.env` was missing on this host. That failure is not caused by the path migration.

## Future operating rules

1. New coding repositories should be cloned under `/home/jellybot/dev_projects/<repo>`.
2. New non-git project folders should start under `/home/jellybot/projects/<project>`.
3. If a non-git project becomes a coding project, promote it by moving it to `dev_projects`, creating/connecting Git, and updating runtime/docs references in the same change.
4. Hermes Desktop Projects should point at the Jellyberry-visible path, not a Mac-local path.
5. Kanban task bodies should name the durable output path in the appropriate repo under `dev_projects`.
6. Cron scripts should avoid hard-coded old root paths; prefer explicit environment overrides where practical.
7. Do not rewrite historical logs or completed cron output solely to change old paths.

## Quick validation commands

```bash
# Show top-level project roots.
find /home/jellybot/dev_projects -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
find /home/jellybot/projects -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort

# Check current durable workspace repos.
git -C /home/jellybot/dev_projects/hermes-ops status --short --branch
git -C /home/jellybot/dev_projects/home-network status --short --branch
git -C /home/jellybot/dev_projects/portfolio-intel status --short --branch
git -C /home/jellybot/dev_projects/logk status --short --branch

# Search active config/scripts for stale old roots, excluding history.
rg -n --hidden \
  --glob '!**/.git/**' \
  --glob '!**/logs/**' \
  --glob '!**/output/**' \
  '/home/jellybot/(hermes-ops|home-network|portfolio-intel|3dprint_loader|diagram_creator|logk|sc-100-prep|ms-102-prep|cert-study-hub|image-pastebin)' \
  /home/jellybot/.hermes/cron/jobs.json \
  /home/jellybot/.hermes/scripts \
  /home/jellybot/.config/systemd/user \
  /home/jellybot/dev_projects/hermes-ops \
  /home/jellybot/dev_projects/home-network \
  /home/jellybot/dev_projects/portfolio-intel
```
