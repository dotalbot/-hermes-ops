# Hermes Kanban operating procedures

Scope: operator-facing CLI procedures for Hermes Kanban. Dispatcher-spawned worker agents should use their `kanban_*` tools, not shell out to `hermes kanban`.

Verified on this host with:

```bash
hermes kanban --help
hermes kanban create --help
hermes kanban list --help
hermes kanban assign --help
hermes kanban dispatch --help
hermes kanban unblock --help
hermes kanban runs --help
hermes kanban log --help
hermes kanban assignees --json
hermes profile list
```

## Ground rules

- Always discover real profiles before assigning work. Do not invent profile names.
- Prefer `--board <slug>` on scripted commands so you do not accidentally operate on the currently selected board.
- The dispatcher normally runs inside the Hermes gateway. If the gateway is down, `ready` tasks stay ready until a dispatcher pass runs.
- Use durable workspaces for durable output: `dir:/absolute/path` or `worktree:/absolute/path`. The default `scratch` workspace is deleted when the task completes.
- Humans and scripts use `hermes kanban ...`; workers use `kanban_show`, `kanban_complete`, `kanban_block`, `kanban_comment`, etc.

## Board selection

Show the active board:

```bash
hermes kanban boards show
```

List boards:

```bash
hermes kanban boards list
```

Switch the active board for later CLI calls:

```bash
hermes kanban boards switch continuous-hermes-improvement
```

Operate on a board without switching:

```bash
hermes kanban --board continuous-hermes-improvement list
```

Board resolution order is:

1. `HERMES_KANBAN_DB`, if set, pins an explicit SQLite DB path and bypasses normal board-slug resolution.
2. Explicit `--board <slug>`.
3. `HERMES_KANBAN_BOARD`.
4. The current-board pointer set by `hermes kanban boards switch <slug>`.
5. `default`.

## Discover available profiles before assignment

List profiles that exist on disk:

```bash
hermes profile list
```

List known Kanban assignees and their task counts on the active board:

```bash
hermes kanban assignees
```

List known assignees on a specific board:

```bash
hermes kanban --board continuous-hermes-improvement assignees
```

Machine-readable profile roster for scripts:

```bash
hermes kanban --board continuous-hermes-improvement assignees --json
```

Use a name from the `Profile` column of `hermes profile list`, or the `name` field from `hermes kanban assignees --json`, as the assignee. On this host at verification time, real on-disk profiles were `default`, `hindsightpilot`, and `homenetworkworker`; re-run discovery before creating new work because profiles can change.

## Status / column usage

Hermes task statuses are the source of truth; dashboard columns are views over those statuses.

- Backlog: there is no literal CLI status named `backlog`. Use `triage` for backlog/raw ideas that need specification before dispatch.
- `triage`: not executable yet. Create with `--triage`; then use `hermes kanban specify <id>` or `hermes kanban decompose <id>` to turn it into executable work.
- `todo`: known work that is not dispatchable yet. Common cases: waiting on parent dependencies, intentionally parked by the operator, or not manually promoted yet.
- `ready`: assigned and eligible for the dispatcher to claim.
- `running`: claimed by a dispatcher-spawned worker process.
- `blocked`: waiting for human input, credentials, review, or failure triage. For code/doc changes needing human review, use reason prefix `review-required:`.
- `scheduled`: parked until a time or external timing condition; unblock when it should run.
- `review`: accepted by `list --status`, but the current durable review gate normally uses `blocked` with `review-required:` plus a comment containing handoff metadata.
- `done`: complete with durable handoff evidence.
- `archived`: hidden from normal lists unless requested.

List tasks by status:

```bash
hermes kanban --board continuous-hermes-improvement list --status ready
hermes kanban --board continuous-hermes-improvement list --status blocked
hermes kanban --board continuous-hermes-improvement list --status todo
```

Get board counts by status and assignee:

```bash
hermes kanban --board continuous-hermes-improvement stats
hermes kanban --board continuous-hermes-improvement stats --json
```

## Add tasks

Create a simple task assigned to a discovered profile:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Draft memory boundary guide" \
  --assignee default \
  --body "Write docs/guides/memory/boundaries.md with examples."
```

Create a task with a durable directory workspace:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Document Kanban operating procedures" \
  --assignee default \
  --workspace dir:/home/jellybot/hermes-ops \
  --body "Output path: docs/guides/kanban/operating-procedures.md"
```

Create a code task in a pinned git worktree:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Add Mission Control read-only action API" \
  --assignee default \
  --workspace worktree:/home/jellybot/worktrees/mission-control-actions \
  --branch feat/mission-control-readonly-actions \
  --body "Implement and test the read-only action API."
```

Create a backlog/triage item that is not ready for workers yet:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Explore safer dashboard write actions" \
  --assignee default \
  --triage \
  --body "Raw idea; needs scope and security boundaries."
```

Create an idempotent task for automation or webhooks:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Nightly ops review" \
  --assignee default \
  --idempotency-key "nightly-ops-$(date -u +%Y-%m-%d)" \
  --json
```

Useful create options verified by `hermes kanban create --help`:

- `--body BODY`
- `--assignee PROFILE`
- `--parent TASK_ID` (repeatable)
- `--workspace scratch|dir:/absolute/path|worktree|worktree:/absolute/path`
- `--branch BRANCH`
- `--tenant TENANT`
- `--priority N`
- `--triage`
- `--idempotency-key KEY`
- `--max-runtime 30m`
- `--skill SKILL` (repeatable; force-loads skills in the worker)
- `--max-retries N`
- `--initial-status blocked|running`
- `--json`

## Assign or reassign tasks

Assign an existing task to a discovered profile:

```bash
hermes kanban --board continuous-hermes-improvement assign t_abc12345 default
```

Unassign a task:

```bash
hermes kanban --board continuous-hermes-improvement assign t_abc12345 none
```

Reassign a non-running task:

```bash
hermes kanban --board continuous-hermes-improvement reassign t_abc12345 hindsightpilot
```

Reassign a running or claimed task by explicitly reclaiming it first:

```bash
hermes kanban --board continuous-hermes-improvement reassign \
  t_abc12345 homenetworkworker \
  --reclaim \
  --reason "Move to the home-network specialist profile"
```

If a running task's worker died and you only need to release the claim:

```bash
hermes kanban --board continuous-hermes-improvement show t_abc12345
hermes kanban --board continuous-hermes-improvement runs t_abc12345
hermes kanban --board continuous-hermes-improvement reclaim \
  t_abc12345 \
  --reason "Worker process is gone; release claim"
```

## Dependencies and promotion

Create a child task blocked on a parent by passing `--parent`:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Review the Kanban guide" \
  --assignee default \
  --parent t_parent12 \
  --workspace dir:/home/jellybot/hermes-ops \
  --body "Review docs/guides/kanban/operating-procedures.md against acceptance criteria."
```

Add a parent-to-child dependency between existing tasks:

```bash
hermes kanban --board continuous-hermes-improvement link t_parent12 t_child34
```

Remove a dependency:

```bash
hermes kanban --board continuous-hermes-improvement unlink t_parent12 t_child34
```

Manually promote a `todo` or `blocked` task to `ready` when it is safe to dispatch:

```bash
hermes kanban --board continuous-hermes-improvement promote \
  t_abc12345 \
  "Spec is complete; ready for worker"
```

Dry-run a promotion first:

```bash
hermes kanban --board continuous-hermes-improvement promote \
  t_abc12345 \
  "Check whether dependencies are clear" \
  --dry-run
```

Force promotion only when you intentionally override dependencies:

```bash
hermes kanban --board continuous-hermes-improvement promote \
  t_abc12345 \
  "Override dependency after manual operator review" \
  --force
```

## Dispatch work

Normal path: start or verify the gateway, because the dispatcher runs there by default.

```bash
hermes gateway status
hermes gateway start
```

Run one dispatcher pass manually:

```bash
hermes kanban --board continuous-hermes-improvement dispatch
```

Preview what a dispatcher pass would do without spawning workers:

```bash
hermes kanban --board continuous-hermes-improvement dispatch --dry-run --max 3
```

Run one pass with JSON output:

```bash
hermes kanban --board continuous-hermes-improvement dispatch --dry-run --json
```

The standalone daemon command exists but `hermes kanban --help` marks it deprecated because the dispatcher now runs in the gateway:

```bash
hermes kanban daemon --help
```

Use `hermes gateway start` unless you are debugging a special case.

## Block, schedule, and unblock tasks

Block a task with a reason. The reason is also appended as a comment:

```bash
hermes kanban --board continuous-hermes-improvement block \
  t_abc12345 \
  "Need GitHub deploy key before pushing the branch"
```

Block several tasks with the same reason:

```bash
hermes kanban --board continuous-hermes-improvement block \
  t_abc12345 \
  "Waiting for operator decision" \
  --ids t_def67890 t_ghi24680
```

Schedule/park a task until a timing condition is met:

```bash
hermes kanban --board continuous-hermes-improvement schedule \
  t_abc12345 \
  "Run after the 03:00 backup completes"
```

Unblock a task, recording the reason as a comment first. If parent dependencies are satisfied, the task returns to `ready`; if parent dependencies are still open, it returns to `todo` rather than bypassing the dependency gate.

```bash
hermes kanban --board continuous-hermes-improvement unblock \
  t_abc12345 \
  --reason "Deploy key added; retry push"
```

Unblock multiple tasks:

```bash
hermes kanban --board continuous-hermes-improvement unblock \
  t_abc12345 t_def67890 \
  --reason "Operator approved the revised scope"
```

## Comments and worker handoffs

Append a comment:

```bash
hermes kanban --board continuous-hermes-improvement comment \
  t_abc12345 \
  "Reviewer note: verify git diff --check and include pushed branch in handoff."
```

Set an explicit comment author:

```bash
hermes kanban --board continuous-hermes-improvement comment \
  t_abc12345 \
  --author operator \
  "Please keep the final artifact under docs/."
```

Show the full task state, including comments, events, children, and run history:

```bash
hermes kanban --board continuous-hermes-improvement show t_abc12345
```

Print the exact worker context for diagnosis:

```bash
hermes kanban --board continuous-hermes-improvement context t_abc12345
```

## Inspect logs and runs

Show attempt history for a task:

```bash
hermes kanban --board continuous-hermes-improvement runs t_abc12345
```

Show attempt history as JSON:

```bash
hermes kanban --board continuous-hermes-improvement runs t_abc12345 --json
```

Filter runs by status or outcome:

```bash
hermes kanban --board continuous-hermes-improvement runs \
  t_abc12345 \
  --state-type outcome \
  --state-name timed_out
```

Print the worker log for a task:

```bash
hermes kanban --board continuous-hermes-improvement log t_abc12345
```

Print only the last bytes of the worker log:

```bash
hermes kanban --board continuous-hermes-improvement log t_abc12345 --tail 20000
```

Follow one task's event stream:

```bash
hermes kanban --board continuous-hermes-improvement tail t_abc12345
```

Watch all board events:

```bash
hermes kanban --board continuous-hermes-improvement watch
```

Watch only blocked/completed events:

```bash
hermes kanban --board continuous-hermes-improvement watch \
  --kinds blocked,completed,gave_up,crashed,timed_out
```

Run board diagnostics:

```bash
hermes kanban --board continuous-hermes-improvement diagnostics
```

## Complete or archive tasks

Complete a task with a short result:

```bash
hermes kanban --board continuous-hermes-improvement complete \
  t_abc12345 \
  --summary "Wrote docs/guides/kanban/operating-procedures.md and verified CLI examples." \
  --metadata '{"changed_files":["docs/guides/kanban/operating-procedures.md"],"verification":["git diff --check"]}'
```

Complete several tasks with the same result string:

```bash
hermes kanban --board continuous-hermes-improvement complete \
  t_abc12345 t_def67890 \
  --result "Batch cleanup complete"
```

Archive a task when it should disappear from normal lists:

```bash
hermes kanban --board continuous-hermes-improvement archive t_abc12345
```

List archived tasks too:

```bash
hermes kanban --board continuous-hermes-improvement list --archived
```

## Common operator workflows

### Create manually gated work

Use this when you want the card visible but do not want the dispatcher to claim it yet. Create it blocked with an explicit reason:

```bash
hermes kanban --board continuous-hermes-improvement create \
  "Draft approval model" \
  --assignee default \
  --workspace dir:/home/jellybot/hermes-ops \
  --initial-status blocked \
  --body "Draft docs/specs/approval-model.md; wait for operator to unblock."
```

When you are ready, unblock it. If it has no open parent dependencies, it becomes `ready`:

```bash
hermes kanban --board continuous-hermes-improvement unblock \
  t_abc12345 \
  --reason "Operator selected this as next work"
```

For raw backlog ideas that need scoping instead of execution, use `--triage` rather than `--initial-status blocked`.

### Recover from a blocked review-required task

Inspect the work and comments:

```bash
hermes kanban --board continuous-hermes-improvement show t_abc12345
hermes kanban --board continuous-hermes-improvement runs t_abc12345
```

If approved, unblock with an audit note:

```bash
hermes kanban --board continuous-hermes-improvement unblock \
  t_abc12345 \
  --reason "Review approved; worker may complete final handoff"
```

If changes are needed, comment and unblock:

```bash
hermes kanban --board continuous-hermes-improvement comment \
  t_abc12345 \
  "Change request: include rollback steps and rerun git diff --check."
hermes kanban --board continuous-hermes-improvement unblock \
  t_abc12345 \
  --reason "Reviewer requested changes"
```

### Debug a task stuck in running

```bash
hermes kanban --board continuous-hermes-improvement show t_abc12345
hermes kanban --board continuous-hermes-improvement runs t_abc12345
hermes kanban --board continuous-hermes-improvement log t_abc12345 --tail 20000
```

If the process is gone or the claim is stale, reclaim it:

```bash
hermes kanban --board continuous-hermes-improvement reclaim \
  t_abc12345 \
  --reason "Worker died; release stale running claim"
```

Then dispatch again or wait for the gateway dispatcher:

```bash
hermes kanban --board continuous-hermes-improvement dispatch --dry-run
hermes kanban --board continuous-hermes-improvement dispatch
```

## Worker equivalents

Use CLI commands only from a human terminal or script. Inside a dispatched worker, use tool calls:

- Orient: `kanban_show()`.
- Add durable context: `kanban_comment(task_id="t_...", body="...")`.
- Signal progress: `kanban_heartbeat(note="...")`.
- Create child work: `kanban_create(title="...", assignee="real-profile", parents=[...])`.
- Link existing tasks: `kanban_link(parent_id="t_parent", child_id="t_child")`.
- Block for input: `kanban_block(reason="specific decision needed")`.
- Complete: `kanban_complete(summary="...", metadata={...})`.

Workers should not use the CLI fallback unless explicitly debugging the CLI itself; the tools are board-aware, structured, and work across terminal backends.
