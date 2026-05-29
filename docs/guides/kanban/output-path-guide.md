# Kanban output path guide

Use this guide when creating or reviewing Kanban cards.

## Quick checklist

Before moving a card to `ready`:

- [ ] The card belongs on the right board.
- [ ] The board has a durable folder assigned.
- [ ] The card uses `dir:` or `worktree:` for durable work.
- [ ] The card body has an `Output path` section.
- [ ] The output path is inside the assigned repo/project folder.
- [ ] The card does not ask the worker to save final artifacts only inside scratch.

## Board folders

```text
continuous-hermes-improvement -> /home/jellybot/hermes-ops
home-network                  -> /home/jellybot/home-network
portfolio                     -> /home/jellybot/portfolio-intel
```

## Folder choice

- `docs/roadmap/` — priorities, product direction, sequencing.
- `docs/specs/` — concrete requirements and acceptance criteria.
- `docs/guides/` — reusable how-to guidance.
- `docs/bugs/` — defects, incident notes, reproduction, remediation.
- `docs/runbooks/` — operator procedures with commands and checks.
- `docs/operations/` — service operations, schedules, dashboards, local rules.
- `docs/architecture/` — diagrams, integration maps, component boundaries.
- `docs/decisions/` — ADRs and trade-off records.
- `docs/reports/` — audits, reviews, generated analyses.
- `docs/plans/` — implementation plans and checklists.

## Example card body

```text
Goal:
Document how Kanban workers should handle durable artifacts.

Output path:
- Primary deliverable: docs/guides/kanban/output-path-guide.md
- Supporting output: none
- Do not write final deliverables under ~/.hermes/kanban/boards/.../workspaces/.

Acceptance criteria:
- The guide explains board folder mapping.
- The guide includes examples for docs/specs/guides/bugs/runbooks.
- Verification includes checking the file exists in the repo.
```

## Example create commands

Continuous Hermes improvement doc task:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Write Kanban output path guide" \
  --workspace dir:/home/jellybot/hermes-ops \
  --body "Output path: docs/guides/kanban/output-path-guide.md"
```

Home-network task:

```bash
hermes kanban --board home-network create \
  "Document homepage rollback procedure" \
  --workspace dir:/home/jellybot/home-network \
  --body "Output path: docs/runbooks/homepage-rollback.md"
```

Portfolio task:

```bash
hermes kanban --board portfolio create \
  "Draft portfolio refresh spec" \
  --workspace dir:/home/jellybot/portfolio-intel \
  --body "Output path: docs/specs/portfolio-refresh.md"
```

Hermes Agent source-code task:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Warn when completing scratch artifact tasks" \
  --workspace worktree:/home/jellybot/worktrees/hermes-agent-scratch-artifact-warning \
  --branch feat/scratch-artifact-warning \
  --body "Repo: /home/jellybot/.hermes/hermes-agent. Output: source change plus docs under website/docs if upstream-facing."
```
