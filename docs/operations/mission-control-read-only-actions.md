# Mission Control read-only action and approval model

Date: 2026-05-30
Status: operator documentation
Scope: Hermes Mission Control controls that are safe to expose without mutation privileges, plus the approval model required before any future write-capable action exists.

## Executive summary

Mission Control is read-only today.

The live `/#/hermes` route currently exposes status panels and links only. It does not expose restart, deploy, run-command, backup-trigger, restore, firewall, secret, Docker, or arbitrary shell controls. The read-only action list below is the approved contract for future UI/API controls that may be implemented without write approval because they only read fixed routes, fixed files, or fixed diagnostic command output.

Anything that changes service state, files, repositories, cron definitions, firewall/routing, secrets, backups, restore data, Docker state, or deployments is a write action. Future write actions require explicit user approval, auditability, allowlists, redaction, short-lived single-use approvals, and stronger safeguards before implementation.

Related docs:

- Future guarded-write ADR: `docs/decisions/guarded-mission-control-write-actions.md`
- Future audit logging spec: `docs/specs/mission-control-guarded-write-audit-logging.md`
- Operator runbook for future approved write requests: `docs/runbooks/approved-mission-control-actions.md`

## Verified live route and API status

Verification date: 2026-05-30, from `jellyberry` against local runtime routes.

Mission Control static route and data:

| Route | Result |
|---|---|
| `GET http://127.0.0.1:8787/` | `200 text/html`, 29,706 bytes |
| `GET http://127.0.0.1:8787/data/hermes.json` | `200 application/json`, 11,363 bytes, `generated_at=2026-05-30T06:30:26Z` |
| `GET http://127.0.0.1:8787/data/roadmap.json` | `200 application/json`, 346,460 bytes, 6 projects |

Hermes dashboard read-only API routes:

| Route | Result |
|---|---|
| `GET /api/status` | `200 application/json`, 608 bytes |
| `GET /api/config/defaults` | `200 application/json`, 9,338 bytes |
| `GET /api/config/schema` | `200 application/json`, 41,621 bytes |
| `GET /api/model/info` | `200 application/json`, 295 bytes |
| `GET /api/dashboard/themes` | `200 application/json`, 714 bytes |
| `GET /api/dashboard/plugins` | `200 application/json`, 679 bytes |

Plugin static assets advertised by `/api/dashboard/plugins`:

| Plugin asset | Result |
|---|---|
| `hermes-achievements/dist/index.js` | `200 application/javascript`, 46,829 bytes |
| `hermes-achievements/dist/style.css` | `200 text/css`, 17,984 bytes |
| `kanban/dist/index.js` | `200 application/javascript`, 153,361 bytes |
| `kanban/dist/style.css` | `200 text/css`, 43,297 bytes |

Other verified read-only checks:

- Backup status script completed in read-only mode and reported: `Backup status: ran at 2026-05-30 03:01:04`; restore test status `ok`, files `6417`.
- Cron output root and jobs registry exist at `/home/jellybot/.hermes/cron/output/` and `/home/jellybot/.hermes/cron/jobs.json`.
- Source inspection of live Mission Control v2 route found the UI text: `Read-only v0.1. No restart, deploy, or run-command buttons are exposed.`

Note: a predecessor verification card was archived because the upstream implementation path was removed. This section records fresh live route/API checks for this documentation task.

## Runtime constants and config keys

Use these as the concrete read targets unless deployment config overrides them.

- Mission Control LAN page: `http://192.168.1.159:8787/#/hermes`
- Mission Control Tailnet page: `http://100.68.81.120:8787/#/hermes`
- Mission Control local data files served by the static app:
  - `http://127.0.0.1:8787/data/hermes.json`
  - `http://127.0.0.1:8787/data/roadmap.json`
- Hermes dashboard local base URL: `http://127.0.0.1:9119`
- Hermes dashboard LAN base URL: `http://192.168.1.159:9119`
- Hermes dashboard service command source: `/home/jellybot/.config/systemd/user/hermes-dashboard.service`, `ExecStart=/home/jellybot/.local/bin/hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build --insecure`
- Backup status script: `/home/jellybot/.hermes/scripts/check_backup_status.sh`
- Daily backup cron job id/name/script: `e5448d934cf9` / `daily-hermes-backup-to-github` / `backup_hermes_to_github.sh`
- Backup status cron job id/name/script: `2377afc113bf` / `weekly-hermes-backup-healthcheck` / `check_backup_status.sh`
- Cron output root: `/home/jellybot/.hermes/cron/output/`
- Home-network service inventory source for external links: `/home/jellybot/home-network/inventory/services.yml`
- External UI targets from inventory:
  - Homepage primary: `http://192.168.1.1`
  - Homepage secondary: `http://192.168.1.2`
  - Homepage jellyhome Tailnet: `http://100.90.175.59`
  - Homepage jellybase Tailnet: `http://100.125.86.118`
  - Prometheus: `http://192.168.1.2:9090`
  - Grafana: `http://192.168.1.2:3001`
  - Hindsight UI: `http://192.168.1.1:9999`
  - Hindsight API: `http://192.168.1.1:18888`
  - Hindsight Tailnet UI: `http://100.90.175.59:9999`
  - Hindsight Tailnet API: `http://100.90.175.59:18888`

## Read-only boundary

Allowed read-only actions may only:

- perform HTTP GET or HEAD requests against fixed known routes;
- read local files under fixed allowlisted paths;
- run fixed diagnostic commands with literal argv arrays and no user-supplied arguments;
- return bounded status/output summaries to the caller;
- update browser-local/in-memory display state.

Allowed read-only actions must not:

- call POST, PUT, PATCH, or DELETE endpoints;
- run `hermes doctor --fix`, `hermes update`, `hermes gateway restart`, `systemctl restart`, `docker compose up/down/restart`, `git push`, backup scripts, restore scripts, firewall commands, deploy commands, delete commands, secret rotation, credential reveals, or config writes;
- accept arbitrary command text, arbitrary file paths, arbitrary service names, or arbitrary URLs from the browser;
- mutate source repos, runtime data, cron job definitions, dashboard config, plugin enablement, secrets, firewall rules, service state, or backup repositories.

Important nuance: `refresh-mission-control-view` means refreshing the browser/API view from already-generated JSON. It does not mean running collectors that rewrite `hermes.json`, `roadmap.json`, caches, repos, or dashboard data. Runtime generation remains the existing cron/container responsibility.

## Allowed read-only actions

These are the current allowed read-only actions for future controls. If a future UI/API implementation exposes buttons for them, it must use this contract and stay inside the read-only boundary above.

### 1. Refresh Mission Control data view

- Action id: `refresh-mission-control-view`
- Label text: `Refresh Mission Control data`
- UI type: button or route refresh
- Safe implementation:
  - Browser/API performs HTTP GET against fixed data URLs:
    - `http://127.0.0.1:8787/data/hermes.json`
    - `http://127.0.0.1:8787/data/roadmap.json`
  - The UI updates only in-memory state from returned JSON.
  - Do not run `/home/jellybot/portfolio-intel/scripts/collect_hermes_mission_control.py`.
  - Do not run `~/.hermes/scripts/refresh_hermes_mission_control.sh`.
- Expected output shape:
  - `ok: true|false`
  - `generated_at: string|null` from `hermes.json` when present
  - `sections: {active_work, backups, cron, gateway, ...}` as already present in `hermes.json`
  - `roadmap_projects: number|null` or equivalent count from `roadmap.json`
  - `warnings: string[]`
- Operator interpretation:
  - `generated_at` tells when the displayed data was produced, not when the button was clicked.
  - Stale data means the generation pipeline may need manual review; this action must not run the collector as remediation.
  - Missing or invalid JSON is a display/data-publish problem, not approval to restart services.

### 2. Check Hermes backup status

- Action id: `backup-status-check`
- Label text: `Check Hermes backup status`
- UI type: button
- Safe implementation:
  - Fixed argv only: `["/usr/bin/env", "bash", "/home/jellybot/.hermes/scripts/check_backup_status.sh"]`
  - Cwd: `/home/jellybot`
  - No user-supplied args.
  - 10 second hard timeout; kill the process group on timeout.
- Expected output shape:
  - `ok: true|false`
  - `job_id: "e5448d934cf9"`
  - `ran_at: string|null`
  - `summary: string`
  - `raw_stdout_tail: string` capped to 4 KiB
  - `stderr_tail: string` capped to 4 KiB
  - `exit_code: number|null`
- Operator interpretation:
  - A successful status means the status script found and summarized the latest saved backup output.
  - A failure means backup status is unavailable or stale; do not trigger `backup_hermes_to_github.sh` from Mission Control.
  - Treat restore-test failures as follow-up work for the backup runbook, not as approval for a restore or repair.

### 3. Show latest cron output

- Action id: `latest-cron-output`
- Label text: `Latest cron output`
- UI type: button or panel refresh
- Safe implementation:
  - Read root: `/home/jellybot/.hermes/cron/output/`
  - Allowlisted file pattern: `<job_id>/*.md`, where `<job_id>` exists in `/home/jellybot/.hermes/cron/jobs.json`.
  - Default target: newest `*.md` across all job directories.
  - Optional safe filters: exact job id from jobs registry, such as `e5448d934cf9` or `2377afc113bf`.
  - 5 second budget for directory scan and file read.
- Expected output shape:
  - `ok: true|false`
  - `job_id: string|null`
  - `job_name: string|null`
  - `path: string|null`
  - `mtime: ISO-8601 string|null`
  - `bytes: number|null`
  - `content_markdown: string` capped to 16 KiB
  - `truncated: true|false`
- Operator interpretation:
  - Output is historical saved job output, not a live job run.
  - Stale output indicates the scheduled job may not have run or delivery/output retention may need review.
  - Do not use this action to run, pause, resume, edit, or delete cron jobs.

### 4. Run Hermes health check

- Action id: `hermes-health-check`
- Label text: `Run Hermes health check`
- UI type: button
- Safe implementation:
  - Primary fast probe: HTTP GET `http://127.0.0.1:9119/api/status`.
  - Optional CLI probe: fixed argv `["/home/jellybot/.local/bin/hermes", "status", "--all"]`.
  - Optional doctor probe: fixed argv `["/home/jellybot/.local/bin/hermes", "doctor"]`.
  - Never pass `--fix`, `--ack`, or any user-supplied args.
- Expected output shape:
  - `ok: true|false`
  - `dashboard_status: {version, release_date, gateway_running, gateway_pid, gateway_state, gateway_platforms, active_sessions, auth_required}` from `/api/status`
  - `status_text_tail: string|null` capped to 12 KiB if `hermes status --all` is run
  - `doctor_text_tail: string|null` capped to 12 KiB if `hermes doctor` is run
  - `warnings: string[]`
- Operator interpretation:
  - Green status means probes responded, not that all future actions are safe.
  - Doctor warnings are diagnostic only; Mission Control must not auto-fix them.
  - Gateway/dashboard down results should link to the manual runbook or a guarded future restart request.

### 5. Link to Grafana, Prometheus, Homepage, and Hindsight UI

- Action id: `external-ui-links`
- Label text: `Open observability links`
- UI type: link group
- Safe implementation:
  - Render fixed links from `/home/jellybot/home-network/inventory/services.yml` or checked-in constants.
  - Optional reachability badges may use HEAD/GET only, with 3 seconds per URL.
  - Links render even when optional health badges fail.
- Expected output shape:
  - Static list: `[{label, href, source_key, category}]`
  - Optional badge: `{status_code, reachable, latency_ms}`
- Operator interpretation:
  - Link presence means Mission Control knows the target URL, not that the remote system is healthy.
  - Badge failure means unreachable from the dashboard host or network path; it is not approval to change firewall, DNS, routing, reverse proxies, or service state.

### 6. Check dashboard route health

- Action id: `dashboard-route-health`
- Label text: `Check dashboard route health`
- UI type: button
- Safe implementation:
  - HTTP GET only, against fixed public dashboard routes:
    - `http://127.0.0.1:9119/api/status`
    - `http://127.0.0.1:9119/api/config/defaults`
    - `http://127.0.0.1:9119/api/config/schema`
    - `http://127.0.0.1:9119/api/model/info`
    - `http://127.0.0.1:9119/api/dashboard/themes`
    - `http://127.0.0.1:9119/api/dashboard/plugins`
  - 3 seconds per route, 15 seconds total budget.
- Expected output shape:
  - `ok: true|false`
  - `routes: [{path, status_code, latency_ms, content_type, ok, error}]`
  - Overall `ok` is true only when all required routes return 200 and JSON-compatible content where expected.
- Operator interpretation:
  - 401/403 means auth/config mismatch.
  - 404 means missing route or deployment mismatch.
  - 5xx means dashboard runtime failure.
  - Do not restart the dashboard or edit auth/config from this action.

### 7. Check dashboard plugin route health

- Action id: `dashboard-plugin-route-health`
- Label text: `Check dashboard plugin routes`
- UI type: button
- Safe implementation:
  - GET `http://127.0.0.1:9119/api/dashboard/plugins`.
  - For each returned plugin manifest with `entry`, GET `http://127.0.0.1:9119/dashboard-plugins/{name}/{entry}`.
  - For each returned plugin manifest with `css`, GET `http://127.0.0.1:9119/dashboard-plugins/{name}/{css}`.
  - 3 seconds for manifest, 3 seconds per asset, 20 seconds total budget.
- Current observed plugin assets:
  - `hermes-achievements/dist/index.js`
  - `hermes-achievements/dist/style.css`
  - `kanban/dist/index.js`
  - `kanban/dist/style.css`
- Expected output shape:
  - `ok: true|false`
  - `plugins: [{name, label, version, source, entry, css, has_api}]`
  - `assets: [{plugin, kind: "entry"|"css", url, status_code, content_type, content_length, ok, error}]`
- Operator interpretation:
  - A plugin asset failure explains why a plugin card or panel may not load.
  - Do not rebuild plugins, hide plugins, edit `dashboard.hidden_plugins`, reinstall plugins, or restart dashboard from this action.

## Explicitly excluded write actions

These operations are not read-only controls and must not be exposed as simple Mission Control buttons:

- restarting Hermes gateway, dashboard, Docker services, systemd units, or containers;
- triggering backups, backup repairs, restore drills, repository checks with mutation risk, backup prune/compact/repair/unlock/init, or production restore overwrites;
- running `backup_hermes_to_github.sh` or collector scripts that write `hermes.json`, `roadmap.json`, caches, databases, or repo artifacts;
- running `hermes doctor --fix`, `hermes update`, `hermes config set`, `hermes tools enable/disable`, `hermes plugins install/remove/update`, or `hermes cron create/update/pause/resume/run/remove`;
- firewall, routing, DNS, Tailscale, SSH, sudo, deploy, chmod/chown, system package, or host config changes;
- deleting sessions, cron output, logs, plugin files, generated JSON, repos, Docker volumes, or state databases;
- revealing, rotating, writing, or copying secrets/API keys/OAuth tokens/private keys/passphrases;
- arbitrary shell command execution, arbitrary Python/script execution, arbitrary URL fetches, git commit/push/merge, or deployment commands.

## Future write-action request and approval model

Future write actions may be requested only as guarded proposals, not as direct buttons. Examples include restarts, firewall changes, deploys, secret/data operations, backup checks with mutation risk, restore drills, and Docker service recreation.

A compliant future request must include all of the following before any implementation may execute it:

1. Allowlisted action id and template version.
2. Exact command preview or lossless operation descriptor.
3. Target host, runtime account, service/subsystem, path/backup/collector scope, and risk level.
4. Expected side effects, preflight checks, timeout, post-checks, and rollback/recovery plan.
5. Secret-redaction proof for previews, logs, notifications, Hindsight summaries, and repo records.
6. Short-lived, single-use explicit approval bound to the exact proposal hash and approver identity.
7. Backend revalidation immediately before execution.
8. Refusal on stale, replayed, modified, expired, unknown, unredacted, or unauditable requests.
9. Durable audit events for proposed, approved/denied/expired, refused, started, completed, failed, and any sink failures.

Operators should request future write actions by opening a Kanban task or adding a reviewed design/runbook entry that names the action, target, risk, command shape, rollback plan, and audit requirements. Until the guarded executor and audit store are separately implemented and reviewed, the correct operator response is manual execution outside Mission Control after explicit human approval.

## Implementation notes for future UI/API workers

- Prefer a closed registry keyed by action id; unknown ids return 404.
- Use fixed argv arrays for command-backed checks; never concatenate user input into shell commands.
- Use allowlisted roots for file reads and reject symlinks/path traversal before opening files.
- Cap stdout/stderr/content returned to the UI.
- Record `started_at`, `completed_at`, `duration_ms`, `exit_code`, and `timeout` for every action result.
- Treat read-only actions as status probes, not remediation workflows. If a probe detects a problem, show the problem and link to the relevant runbook/task flow instead of fixing it automatically.
- Keep route-health and plugin-health checks GET-only. If the next step would mutate state, stop and create a guarded write proposal instead.
