# Kanban durable workspace standard

## Problem

Completed Kanban tasks on `continuous-hermes-improvement` produced artifacts under scratch workspaces such as:

`~/.hermes/kanban/boards/continuous-hermes-improvement/workspaces/t_ddd94f48/...`

Hermes deletes scratch workspaces when tasks complete. The task event log preserves the path and sometimes a diff, but the artifact file itself is not durable.

## Decision

Every active Kanban board must have an assigned durable project folder, usually a git repository with a standard `docs/` layout.

Kanban tasks that produce lasting output must write final deliverables into the assigned folder, not into scratch.

## Current board mapping

| Board | Durable folder | Use for |
|---|---|---|
| `continuous-hermes-improvement` | `/home/jellybot/dev_projects/hermes-ops` | Hermes operating docs, local standards, guides, reports, plans, decisions |
| `home-network` | `/home/jellybot/dev_projects/home-network` | Homelab configuration, runbooks, operations docs, specs |
| `portfolio` | `/home/jellybot/dev_projects/portfolio-intel` | Portfolio/project-awareness roadmap, specs, operations, architecture, plans |

## Required docs layout

Each durable folder should use this layout where applicable:

```text
docs/
  roadmap/
  specs/
  guides/
  bugs/
  runbooks/
  operations/
  architecture/
  decisions/
  reports/
  plans/
```

## Task creation rule

A task expected to produce durable output must include an `Output path` section.

Template:

```text
Output path:
- Primary deliverable: docs/<folder>/<slug>.md
- Supporting output: docs/<folder>/<slug>.json or none
- Do not write final deliverables under ~/.hermes/kanban/boards/.../workspaces/.
```

## Workspace rule

Use one of these for durable work:

```bash
--workspace dir:/home/jellybot/dev_projects/hermes-ops
--workspace dir:/home/jellybot/dev_projects/home-network
--workspace dir:/home/jellybot/dev_projects/portfolio-intel
```

Use `worktree:` for isolated Hermes Agent source-code changes:

```bash
--workspace worktree:/home/jellybot/worktrees/hermes-agent-<short-name> \
--branch feat/<short-name>
```

Use `scratch` only for throwaway experiments where deleting files at task completion is acceptable.

## Completion rule

A task should not be marked done if its only artifact path is under:

`~/.hermes/kanban/boards/<board>/workspaces/<task>/`

Acceptable completion evidence includes:

- A file committed and pushed under a durable project repo.
- A report saved under `docs/reports/`.
- A guide/runbook saved under `docs/guides/` or `docs/runbooks/`.
- A spec or decision saved under `docs/specs/` or `docs/decisions/`.
- A code change in the correct source repo or worktree with verification output.

## Commit and push rule

After a worker verifies that durable output was written in the correct assigned repo/folder, the worker must commit and push the change before completing the task.

Required sequence:

1. Verify the artifact exists at the declared durable output path.
2. Run the repo's relevant verification, or at minimum `git diff --check` for documentation-only changes.
3. Inspect `git status --short --branch` and stage only the intended files.
4. Commit with a concise conventional message.
5. Push the branch or repo default according to that repo's workflow.
6. Include the commit id, pushed branch, output path, and verification command/result in the task completion summary.

If the repo has no remote, push fails, or credentials are missing, do not silently mark the task complete. Block the task with the durable output path, local commit id if one exists, and the exact push blocker.

Repo-specific push behavior:

- `/home/jellybot/dev_projects/home-network`: commit and push `main` directly for routine home-network work.
- `/home/jellybot/dev_projects/hermes-ops`: commit and push the active branch when a remote is configured.
- `/home/jellybot/dev_projects/portfolio-intel`: follow the repo's current branch workflow; do not merge unless Dominic asks.
- `/home/jellybot/.hermes/hermes-agent`: use a feature/worktree branch for source-code changes and push that branch; do not merge unless Dominic asks.

## Existing-card review rule

Before unblocking existing cards, review the card body and add a comment naming the durable output path if one is missing.
