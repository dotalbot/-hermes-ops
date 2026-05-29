# Runbook: approved Mission Control write-action requests

Status: evaluation runbook only — execution disabled
Owner: Hermes / Mission Control operators
Last updated: 2026-05-29
Related design: `docs/decisions/guarded-mission-control-write-actions.md`

## Hard safety boundary

This runbook does not enable Mission Control to execute commands. It is an operator-review document for future guarded write actions only.

Until a separately reviewed implementation exists, Mission Control must remain read-only. Any future implementation must refuse execution unless it can prove an explicit, current, single-use user approval for the exact action, target, parameters, risk level, and command or operation descriptor.

Do not store or paste real secrets, tokens, OAuth credentials, private keys, repository passphrases, sudo passwords, or unredacted environment values into Mission Control proposals, approval records, notifications, logs, tickets, or this runbook.

## Approval model required for every candidate action

Every future write-capable request must follow this sequence:

1. Request: Mission Control prepares a structured proposal from an allowlisted action template. The browser, LLM, dashboard data, or request body must not provide arbitrary shell text.
2. Review: the approval screen shows the exact command shape or lossless operation descriptor, target host, runtime account, target service/subsystem, expected side effects, risk level, preflight checks, rollback plan, and audit destinations.
3. Approval: the user approves the exact proposal. Approval is single-use, short-lived, identity-bound, and tied to a proposal hash.
4. Revalidation: the backend rechecks the proposal hash, allowlist entry, host, parameters, risk level, and expiry immediately before execution.
5. Execution: only the validated operation runs. If command preview, redaction, audit logging, or preflight validation fails, execution stops before mutation when possible.
6. Verification: post-checks prove the expected state or identify partial failure.
7. Audit: approved, refused, failed, rolled-back, and completed attempts are recorded with secrets redacted.

## Universal preflight checklist

Run these checks before any action-specific preflight:

- Confirm the guarded executor feature flag is enabled only in the reviewed future implementation. Today it must remain disabled.
- Confirm the request action id is in the allowlist.
- Confirm the target host and runtime account match the approval screen.
- Confirm the command preview uses placeholders such as `<SERVICE>`, `<JOB_ID>`, `<RESTORE_DEST>`, or `<COMPOSE_FILE>` and contains no secrets.
- Confirm all parameters are selected from allowlists or strict schemas; no arbitrary command strings, paths, URLs, environment variables, or service names.
- Confirm logs and notifications will redact secrets and cap output size.
- Confirm rollback steps are realistic for the target action.
- Confirm the user understands risk level and expected downtime or data exposure.

## Universal audit destinations

A future implementation should write redacted audit events to these destinations, as applicable:

- Mission Control action audit store: approved/refused/executed/failed/rolled-back action records.
- Hermes dashboard or gateway logs for API request and executor lifecycle events.
- Systemd user journal on the target host for Hermes dashboard/gateway actions, when systemd is involved.
- Docker container logs for containerized Mission Control or portfolio-intel runtime processes.
- Cron job output under `/home/jellybot/.hermes/cron/output/` only when the action is explicitly a cron/job run.
- Operator notification channel summary, with redacted command preview and result only.

## Candidate action 1: restart Hermes gateway or dashboard

Action ids:

- `restart-hermes-gateway`
- `restart-hermes-dashboard`

Intended target host/service:

- Host: `<HERMES_HOST>`; current known dashboard host is `jellyberry` / `192.168.1.159` unless deployment config says otherwise.
- Runtime account: `<HERMES_RUNTIME_USER>`.
- Services: Hermes gateway process and/or `hermes-dashboard.service` user systemd unit.

Example command shape:

```bash
ssh <HERMES_RUNTIME_USER>@<HERMES_HOST> -- systemctl --user restart <HERMES_SERVICE>.service
ssh <HERMES_RUNTIME_USER>@<HERMES_HOST> -- systemctl --user status --no-pager <HERMES_SERVICE>.service
ssh <HERMES_RUNTIME_USER>@<HERMES_HOST> -- curl --fail --max-time 3 http://127.0.0.1:<DASHBOARD_PORT>/api/status
```

Do not include SSH keys, tokens, sudo passwords, or real environment values in the proposal. Do not allow arbitrary service names.

Preflight checks:

- Confirm `<HERMES_SERVICE>` is allowlisted, for example `hermes-dashboard`; no broad wildcard restart patterns.
- Confirm active sessions and expected downtime are displayed.
- Confirm the target host identity matches the approved host.
- Confirm service unit path and ExecStart match the expected deployment record.
- Confirm health route is known before restart.

Approval requirement:

- Required for every restart.
- Risk level: medium for dashboard-only restart; high if gateway restart can interrupt active chat/session handling.
- High-risk restart should show a second confirmation phrase or explicit downtime acknowledgement in a future UI.

Execution notes:

- Restart exactly one allowlisted service per approval.
- Refuse if the service name, host, account, or port differs from the approved proposal.
- Do not run package updates, config writes, `hermes update`, or `hermes doctor --fix` as part of this action.

Rollback steps:

- If restart fails, run status/log collection only:
  - `systemctl --user status --no-pager <HERMES_SERVICE>.service`
  - `journalctl --user -u <HERMES_SERVICE>.service -n <LINES> --no-pager`
- If the prior unit file or config was changed by a separate deployment, roll back from the reviewed prior commit/config snapshot, then restart with a new approval.
- If no config changed and the service remains down, stop execution and escalate to manual operator recovery.

Expected logs:

- Mission Control action audit store.
- Hermes dashboard/gateway application logs.
- User systemd journal for `<HERMES_SERVICE>.service`.
- Operator notification summary.

## Candidate action 2: rerun selected collectors

Action ids:

- `rerun-portfolio-collector`
- `rerun-mission-control-collector`
- `rerun-portfolio-event-refresh`
- `rerun-portfolio-digest-render`

Intended target host/service:

- Host: `<PORTFOLIO_HOST>`; current runtime host is `jellyberry` unless config says otherwise.
- Repository/runtime path: `/home/jellybot/portfolio-intel` or approved deployment path.
- Service/subsystem: portfolio-intel collector scripts and generated dashboard data.

Example command shape:

```bash
cd /home/jellybot/portfolio-intel
<PYTHON> scripts/<ALLOWLISTED_COLLECTOR>.py --config <CONFIG_PATH>
```

For scripts without config arguments, the command preview must still show the exact fixed argv. Do not expose GitHub tokens, OAuth credentials, or API keys.

Preflight checks:

- Confirm the collector script name is allowlisted.
- Confirm whether the collector writes `data/latest.json`, `mission-control-v2/data/roadmap.json`, `data/hermes.json`, caches, databases, or digest artifacts.
- Confirm whether external APIs will be called and whether rate-limit or quota impact is expected.
- Confirm current generated artifact timestamps and make a rollback copy if the action writes files.
- Confirm no uncommitted repo changes would be overwritten by generated output.

Approval requirement:

- Required for collectors that write files, update databases, trigger external API side effects, push commits, or refresh served dashboard data.
- Risk level: low when only local generated JSON is replaced and rollback copy exists; medium when external API usage, repo-tracked artifacts, or dashboard-visible data changes are involved.
- Read-only dry runs may be exposed separately only if they cannot mutate local or remote state.

Execution notes:

- Run one allowlisted collector per approval unless the proposal explicitly lists a reviewed pipeline sequence.
- Capture bounded stdout/stderr tails; do not log full API responses if they may contain sensitive metadata.
- Never use this action to run arbitrary Python, shell, git push, deploy, Docker, or credential refresh commands.

Rollback steps:

- Restore the preflight backup copy of generated artifacts when output is malformed or stale.
- If repo-tracked files changed unexpectedly, stop and preserve `git diff --stat` for review; do not auto-commit or push.
- If external API quota was consumed, record the failed run and avoid immediate retry loops.

Expected logs:

- Mission Control action audit store.
- Collector stdout/stderr tail in the executor log with output caps.
- Portfolio-intel runtime logs or container logs when run in the deployed container.
- Generated artifact metadata such as path, previous mtime, new mtime, and checksum, with no secrets.

## Candidate action 3: trigger backup health checks

Action ids:

- `run-hermes-backup-healthcheck`
- `run-borgmatic-healthcheck`

Intended target host/service:

- Host: `<BACKUP_SOURCE_HOST>` such as jellyberry, jellyhome, jellybase, or another approved source host.
- Backup repository/service: `<BACKUP_REPOSITORY_ID>` or `<BORG_REPO_ALIAS>` from inventory.
- Runtime account: `<BACKUP_RUNTIME_USER>`.

Example command shape:

```bash
/home/jellybot/.hermes/scripts/check_backup_status.sh
borgmatic --config <BORG_CONFIG_PATH> check --repository <BORG_REPO_ALIAS>
```

The proposal must not contain Borg passphrases, SSH private keys, repository encryption keys, webhook URLs, or raw secret file paths beyond approved placeholder paths.

Preflight checks:

- Confirm the command is non-mutating. Avoid repair, prune, compact, delete, recreate, initialize, or lock-breaking options unless a separate high-risk action exists.
- Confirm target repository alias and source host match inventory.
- Confirm the runtime user has read-only check permissions expected for the target.
- Confirm expected duration and possible repository lock behavior.
- Confirm stale-lock handling is documented but not automatically mutating.

Approval requirement:

- Required before any backup-health command runs.
- Risk level: medium, because checks may touch backup repositories, hold locks, or expose operational metadata.
- Any mutating repair/prune/compact/unlock action is out of scope for this first guarded model.

Execution notes:

- Prefer read-only status scripts and `borgmatic check` modes that do not repair or prune.
- Cap output and redact hostnames/paths only if the chosen audit policy classifies them as sensitive.
- Do not run the actual backup script as remediation after a failed status check.

Rollback steps:

- If a check fails, collect bounded logs and mark backup health as failed/stale; do not repair automatically.
- If a stale lock is detected, create a separate high-risk manual task; do not break locks through this action.
- If a check consumes too much time or I/O, stop future retries and require operator review.

Expected logs:

- Mission Control action audit store.
- Backup health script or Borgmatic stdout/stderr tail.
- Cron output only if the future implementation intentionally triggers a cron-backed healthcheck job.
- System journal if Borgmatic is run via systemd.

## Candidate action 4: trigger restore drills

Action ids:

- `run-hermes-restore-drill`
- `run-borgmatic-restore-drill`

Intended target host/service:

- Host: `<RESTORE_HOST>`; must be an approved drill/staging host or the source host using a staging path.
- Backup source: `<BACKUP_REPOSITORY_ID>` and `<SNAPSHOT_ID_OR_POLICY>`.
- Destination: `<RESTORE_DEST>` under an approved drill path, never production data.

Example command shape:

```bash
mkdir -p <RESTORE_DEST>
borgmatic --config <BORG_CONFIG_PATH> extract --repository <BORG_REPO_ALIAS> --archive <SNAPSHOT_ID> --destination <RESTORE_DEST> --path <RESTORE_SOURCE_PATH>
<VALIDATION_COMMAND> <RESTORE_DEST>
```

Do not show passphrases, SSH keys, raw repository secrets, or restored file contents in the proposal or logs.

Preflight checks:

- Confirm `<RESTORE_DEST>` is an allowlisted drill/staging path and does not overlap production directories.
- Confirm enough disk space exists for the expected restore size.
- Confirm the selected snapshot/archive is valid and recent enough for the drill objective.
- Confirm restored data may contain sensitive files and must be permission-restricted.
- Confirm cleanup plan and retention time for restored artifacts.
- Confirm validation command reads only the staged restore output.

Approval requirement:

- Required for every restore drill.
- Risk level: high, because restore drills read backup contents and create recovered files.
- A future UI should require an explicit confirmation phrase that the destination is a drill path and not production.

Execution notes:

- Refuse if the destination path is `/`, `/home/jellybot`, `/opt/docker`, any production appdata path, or any path not in the restore-drill allowlist.
- Set restrictive permissions on restore destinations.
- Do not overwrite existing restore destinations unless the approval specifically includes a cleanup step for that drill path.

Rollback steps:

- Delete only the approved drill destination path after validation and retention requirements are met.
- If validation fails, quarantine the staged restore path and record the failure for manual inspection.
- If production overlap is detected at any point, stop immediately and escalate; do not continue cleanup automatically except for clearly isolated temp paths.

Expected logs:

- Mission Control action audit store.
- Borgmatic/extract stdout/stderr tail with contents redacted and capped.
- Restore validation result summary.
- Cleanup confirmation event naming only the approved drill path placeholder or sanitized path.

## Candidate action 5: recreate selected Docker services

Action ids:

- `recreate-docker-service`
- `pull-and-recreate-docker-service`

Intended target host/service:

- Host: `<DOCKER_HOST>` such as jellyhome, jellybase, or jellyberry when explicitly allowlisted.
- Compose project: `<COMPOSE_PROJECT>`.
- Compose file: `<COMPOSE_FILE>` under the approved source-of-truth checkout or runtime path.
- Service: `<DOCKER_SERVICE>` selected from an allowlist.

Example command shape:

```bash
ssh <DOCKER_RUNTIME_USER>@<DOCKER_HOST> -- \
  'cd <COMPOSE_PROJECT_DIR> && docker compose -f <COMPOSE_FILE> up -d --no-deps <DOCKER_SERVICE>'

ssh <DOCKER_RUNTIME_USER>@<DOCKER_HOST> -- \
  'cd <COMPOSE_PROJECT_DIR> && docker compose -f <COMPOSE_FILE> ps <DOCKER_SERVICE>'
```

Do not include `.env` contents, secret mounts, registry credentials, private image tokens, or raw container environment values.

Preflight checks:

- Confirm host, compose project, compose file, and service are allowlisted.
- Confirm `docker compose config` succeeds before recreation.
- Confirm expected image tag or digest and whether a pull/build is included.
- Confirm affected ports, volumes, networks, secrets, and dependencies are displayed.
- Confirm current container id/image and health state are recorded for rollback.
- Confirm no broad `docker compose down`, volume removal, image prune, orphan cleanup, or all-service recreation is requested.

Approval requirement:

- Required before any container recreate, rebuild, pull, restart, or deployment command.
- Risk level: high, because services may become unavailable or connect to persistent volumes.
- Pull/build variants should be shown as higher risk than same-image recreate.

Execution notes:

- Recreate exactly the approved service only.
- Use `--no-deps` unless the proposal explicitly names allowlisted dependencies.
- Do not remove volumes, networks, images, or orphans in this first guarded model.
- Run health checks after recreation and record partial failure clearly.

Rollback steps:

- Re-run the prior known-good compose checkout/image tag with a separate approved rollback proposal, or manually restore the previous image tag/commit if recorded.
- If recreation fails and the old container still exists, consider manual start only after operator review.
- If data volumes are affected, stop automated rollback and require manual inspection.

Expected logs:

- Mission Control action audit store.
- Docker compose stdout/stderr tail with secrets redacted and capped.
- Docker container logs for the selected service when needed for post-checks.
- Source repo commit id or compose config checksum used for the action.

## Explicitly prohibited in the first write-action model

These actions must not be enabled by the future first guarded implementation:

- Arbitrary shell commands.
- Commands sourced from LLM output, dashboard JSON, or browser request text.
- `docker compose down`, volume deletion, image pruning, orphan cleanup, broad all-service restarts, or unscoped rebuilds.
- Backup prune, compact, repair, unlock, repository initialization, or destructive maintenance.
- Production restore overwrite paths.
- Secret reveal, rotation, copying, or writing.
- `hermes doctor --fix`, `hermes update`, config writes, plugin install/remove/update, cron mutation, firewall/routing/DNS/Tailscale changes, chmod/chown, or sudo password handling.
- Git commit, push, deploy, or merge actions from Mission Control unless a separate design and approval model is written.

## Operator evaluation checklist for future action requests

Before approving any future action request, answer these questions:

- Is the action in the allowlist, and is its action id correct?
- Does the preview show the exact command or descriptor and the exact target host/service/path?
- Are all secrets redacted or represented as placeholders?
- Are the preflight checks completed and visible?
- Is the risk level appropriate for the operation and target?
- Is rollback realistic, or does the approval text explicitly state that rollback is manual/not possible?
- Will audit records be written even if the action is refused or fails?
- Does the action avoid every prohibited operation listed above?
- Would a stale, replayed, or modified approval be refused?

If any answer is no, refuse the request and keep Mission Control read-only. Safety first; dashboards should not become "oopsboards."
