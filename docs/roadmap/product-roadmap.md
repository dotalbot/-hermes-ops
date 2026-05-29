# Product roadmap

This roadmap tracks improvements to Dominic's local Hermes operating model.

## Current priorities

- [x] Create a durable Hermes Ops repository for local operating knowledge.
- [x] Establish a standard docs folder layout for Kanban outputs.
- [x] Set Kanban board default work directories to durable project folders.
- [x] Require completed durable-output Kanban tasks to commit and push after verification.
- [ ] Recover important missing artifacts from completed scratch Kanban task logs.
- [ ] Add a Kanban task-creation checklist that requires an explicit output path.
- [ ] Prefer `dir:` or `worktree:` workspaces for durable tasks.
- [ ] Review existing blocked/todo cards and add concrete output paths before unblocking.

## Board to durable folder mapping

- `continuous-hermes-improvement` -> `/home/jellybot/hermes-ops`
- `home-network` -> `/home/jellybot/home-network`
- `portfolio` -> `/home/jellybot/portfolio-intel`

## Notes

The Kanban dashboard is useful for execution state, but durable project memory belongs in project repositories under `docs/`.
