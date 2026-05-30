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
- [ ] The card tells the worker to commit and push after verifying the durable output.

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
- `docs/decisions/` — ADRs and trade-off records; use `docs/decisions/0000-adr-template.md` as the default template for Hermes Ops / CHI / Mission Control decision documentation.
- `docs/reports/` — audits, reviews, generated analyses.
- `docs/plans/` — implementation plans and checklists.

## Default decision-record rule

For Hermes Ops, CHI, Mission Control, Kanban workflow, gateway, memory, dashboard, and operator-process documentation, create an ADR under `docs/decisions/` whenever the work records a durable decision or trade-off that future workers should follow.

Default flow:

1. Copy `docs/decisions/0000-adr-template.md`.
2. Save the new file as `docs/decisions/NNNN-short-kebab-case-title.md`.
3. Keep `Status: Proposed` until the operator accepts the decision.
4. Link the ADR from related specs, runbooks, operating-manual sections, or Kanban completion comments.

Use normal specs/plans/runbooks instead when the document is only implementation steps or temporary project status.

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
- Completion includes commit id, pushed branch, output path, and verification result.
```

## Completion handoff rule

Before marking a durable-output task complete, the worker must:

1. Verify the final file is in the declared project repo path.
2. Run verification, at least `git diff --check` for docs-only changes.
3. Commit the intended files.
4. Push the branch/default branch according to that repo's workflow.
5. Report the output path, commit id, pushed branch, and verification result.

If push cannot be completed, block the card instead of completing it. The block reason should name the output path, local commit id if present, and the exact push issue.

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
