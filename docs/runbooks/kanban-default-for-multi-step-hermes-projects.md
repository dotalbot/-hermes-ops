# Make Kanban the default for multi-step Hermes projects

Use this runbook when a Hermes project is too large, risky, or long-lived for one chat. The default example is the current Hermes Agent operations board:

- Board: `continuous-hermes-improvement`
- Durable repo: `/home/jellybot/dev_projects/hermes-ops`
- Typical output path: `docs/...`
- Default assignee for general Hermes ops work: `default`

## 1. Decide whether to use Kanban

Keep work in chat only when it is short, single-session, has no durable artifact, and does not need review or visual tracking.

Use Kanban when any of these are true:

- The work has three or more meaningful steps.
- It may run unattended or span more than one focused session.
- It creates code, docs, config, deployments, or policy that needs review.
- The work must survive context loss, restart, or handoff to another worker.
- The user needs visual status tracking, blockers, dependencies, or ownership.
- Multiple lanes can run independently, such as research, implementation, and review.

## 2. Pick the right board

Use one board per durable project area. Do not mix unrelated work just because one assistant can do it.

Common boards:

- `continuous-hermes-improvement`: Hermes operating model, Kanban policy, memory/Hindsight hygiene, gateway behavior, and Hermes ops docs. Use `/home/jellybot/dev_projects/hermes-ops` unless editing Hermes Agent source code.
- `home-network`: homelab infrastructure, Docker services, monitoring, backups, network maps, and runtime deployment work. Use `/home/jellybot/dev_projects/home-network`.
- `portfolio`: portfolio intelligence, dashboards, project tracking, and progress digests. Use `/home/jellybot/dev_projects/portfolio-intel`.
- Cert study or other learning tracks: use a separate board when the work has its own syllabus, milestones, durable notes, or review cadence instead of mixing it into Hermes ops.
- New long-lived project: create or use a separate board when it has its own repo, roadmap, or independent visual tracking need.

Always name the durable output path in the card body. Avoid final artifacts in scratch workspaces because scratch is deleted after completion.

## 3. Check board and assignees

```bash
hermes kanban boards list
hermes kanban boards show    # shows the current board
hermes kanban --board continuous-hermes-improvement assignees
hermes profile list
```

Use a real profile name from `hermes profile list` or `hermes kanban assignees`. On this board, general Hermes ops tasks usually go to `default`.

## 4. Use standard statuses/columns

Hermes task statuses are the source of truth:

- `triage`: raw backlog idea; not executable yet.
- `todo`: known work, parked or waiting for dependencies/manual promotion.
- `ready`: assigned and eligible for dispatch.
- `running`: claimed by a worker.
- `blocked`: waiting for human input, credentials, review, or failure triage.
- `scheduled`: parked until a time/timing condition.
- `done`: complete with durable handoff evidence.
- `archived`: hidden from normal lists.

Useful views:

```bash
hermes kanban --board continuous-hermes-improvement list --status todo
hermes kanban --board continuous-hermes-improvement list --status ready
hermes kanban --board continuous-hermes-improvement list --status blocked
hermes kanban --board continuous-hermes-improvement stats
```

## 5. Create tasks with durable workspaces

Create a ready-to-run Hermes ops docs task:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Draft Kanban default runbook" \
  --assignee default \
  --workspace dir:/home/jellybot/dev_projects/hermes-ops \
  --body "Write docs/runbooks/kanban-default-for-multi-step-hermes-projects.md. Acceptance: short, complete, command-oriented, and reviewed."
```

Create a raw backlog/triage idea that needs scoping first:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Explore safer dashboard write actions" \
  --assignee default \
  --triage \
  --body "Raw idea; needs scope, security boundaries, and acceptance criteria."
```

Create an implementation task and a dependent next task. The next task stays parked until the implementation card passes its review gate and completes:

```bash
impl_id=$(hermes kanban --board continuous-hermes-improvement create \
  "Implement Mission Control read action" \
  --assignee default \
  --workspace worktree:/home/jellybot/worktrees/mission-control-read-action \
  --branch feat/mission-control-read-action \
  --body "Implement read-only action, commit/push, then block with review-required handoff before completion." \
  --json | jq -r '.task_id')

hermes kanban --board continuous-hermes-improvement create \
  "Document Mission Control read action" \
  --assignee default \
  --parent "$impl_id" \
  --workspace dir:/home/jellybot/dev_projects/hermes-ops \
  --body "After implementation is reviewed and done, document usage and verification notes."
```

If you prefer to create tasks first, add the dependency explicitly:

```bash
hermes kanban --board continuous-hermes-improvement link t_impl123 t_next456
```

## 6. Dispatch work

Normal path: make sure the gateway is running. The dispatcher usually runs inside it.

```bash
hermes gateway status
hermes gateway start
```

Preview and run one dispatcher pass manually when needed:

```bash
hermes kanban --board continuous-hermes-improvement dispatch --dry-run --max 3
hermes kanban --board continuous-hermes-improvement dispatch
```

Prefer manually keeping most cards in `todo`, then promoting only the next selected cards to `ready`:

```bash
hermes kanban --board continuous-hermes-improvement promote \
  t_abc12345 \
  "Operator selected this as the next Kanban task"
```

## 7. Use the human-in-the-loop review gate

For reviewable implementation work, the worker should not mark the task done immediately. The expected pattern is:

1. Implementation task writes/commits/pushes the artifact.
2. Worker adds a handoff comment with changed files, tests, branch/commit, and review notes.
3. Worker blocks the card with `review-required: ...`.
4. Human or reviewer inspects the output while the card is blocked.
5. Reviewer unblocks with approval or a change request.
6. Dispatcher reclaims the same implementation card so the worker can either finish the approved handoff or make requested changes.
7. After approval, the worker completes the implementation card; parent/child dependencies then allow the next task to dispatch.

Commands:

```bash
hermes kanban --board continuous-hermes-improvement show t_impl123
hermes kanban --board continuous-hermes-improvement runs t_impl123
hermes kanban --board continuous-hermes-improvement log t_impl123 --tail 20000

# Approve and continue. The dispatcher will resume this same task;
# after the worker completes it, dependent child tasks can dispatch.
hermes kanban --board continuous-hermes-improvement unblock \
  t_impl123 \
  --reason "Review approved; worker may complete final handoff"
hermes kanban --board continuous-hermes-improvement dispatch --dry-run
hermes kanban --board continuous-hermes-improvement dispatch

# Or request changes and let the worker retry
hermes kanban --board continuous-hermes-improvement comment \
  t_impl123 \
  "Change request: add rollback notes and rerun git diff --check."
hermes kanban --board continuous-hermes-improvement unblock \
  t_impl123 \
  --reason "Reviewer requested changes"
```

## 8. Inspect logs, runs, and blockers

Use these before reclaiming, retrying, or changing a stuck card:

```bash
hermes kanban --board continuous-hermes-improvement show t_abc12345
hermes kanban --board continuous-hermes-improvement runs t_abc12345
hermes kanban --board continuous-hermes-improvement log t_abc12345 --tail 20000
hermes kanban --board continuous-hermes-improvement tail t_abc12345
hermes kanban --board continuous-hermes-improvement diagnostics
```

If a worker died or a claim is stale, reclaim then dispatch again:

```bash
hermes kanban --board continuous-hermes-improvement reclaim \
  t_abc12345 \
  --reason "Worker died; release stale running claim"

hermes kanban --board continuous-hermes-improvement dispatch --dry-run
hermes kanban --board continuous-hermes-improvement dispatch
```

## Quick checklist

Before dispatching a new multi-step Hermes project, confirm:

- Correct board selected.
- Real assignee profile selected.
- Durable output path or source repo named.
- Workspace is `dir:/absolute/path` or `worktree:/absolute/path` for durable output.
- Acceptance criteria are in the card body.
- Dependencies are modeled with parent/child links.
- Reviewable implementation work uses `review-required:` blocking before final completion.
- Logs/runs inspection commands are available for recovery.
