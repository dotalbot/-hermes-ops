# Hermes Ops

Private operating knowledge for Dominic's Hermes setup.

This repository is the durable home for Kanban-produced operating documents, runbooks, specs, decisions, audits, and project notes that are specific to this installation.

## Repository purpose

Use this repo for:

- Hermes operating procedures and local conventions.
- Kanban board standards and worker handoff rules.
- Private assistant behavior guidance and review gates.
- Specs, plans, and runbooks for Hermes improvements.
- Audit reports and durable outputs from Kanban workers.

Do not use this repo for:

- Secrets or API keys.
- Ephemeral worker scratch output.
- Upstream Hermes Agent product docs unless the content is meant to be contributed upstream.

## Standard docs layout

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

## Kanban rule

Kanban tasks that produce durable output must write final deliverables into this repo or another assigned project repo, not into `~/.hermes/kanban/boards/.../workspaces/`.

For the `continuous-hermes-improvement` board, use this repo as the default durable folder:

`/home/jellybot/hermes-ops`

For Hermes Agent source-code changes, use the source repo instead:

`/home/jellybot/.hermes/hermes-agent`
