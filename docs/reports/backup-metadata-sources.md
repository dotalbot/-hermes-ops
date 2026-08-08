# Backup metadata sources

Purpose: inventory the current machine-readable or command-readable sources available for backup confidence checks across the Hermes profile backup and home-network Borg/Borgmatic backups.

Inspection date: 2026-05-30.
Host inspected: `jellyberry`.

## Summary of reliable sources

| Scope | Source | Freshness field | Status field | Automation-ready? |
|---|---|---:|---|---|
| Hermes `~/.hermes` GitHub backup | `/home/jellybot/.hermes/cron/jobs.json`, job `e5448d934cf9` | `last_run_at` | `last_status` / `last_error` | Yes; JSON file is directly parseable. |
| Hermes backup run output and restore check | `/home/jellybot/.hermes/cron/output/e5448d934cf9/*.md` | output filename and `**Run Time:**` header | final line includes `restore test: ok` on successful changed backup runs | Mostly; parseable, but Markdown/log text needs a small parser. |
| Hermes backup status helper | `/home/jellybot/.hermes/scripts/check_backup_status.sh` | prints `Backup status: ran at ...` | prints final backup summary line | Yes for command-readable checks; output is stable two-line text but not structured JSON. |
| Borg/Borgmatic local host status | `/var/lib/home-network/backup-status/<host>.json` | `updated_at` | `status`, `exit_code`, `repository_reachable` | Yes; JSON, non-secret, world-readable on inspected host. |
| Borg/Borgmatic Prometheus textfile | `/var/lib/node_exporter/textfile_collector/borgmatic_<host>.prom` | `borgmatic_last_run_timestamp_seconds` | `borgmatic_last_run_success`, `borgmatic_repository_reachable` | Yes; Prometheus exposition format is designed for automation. |
| Borg/Borgmatic central Prometheus | `http://jellybase:9090/api/v1/query` | metric `borgmatic_last_run_timestamp_seconds` | metrics `borgmatic_last_run_success`, `borgmatic_repository_reachable` | Yes; JSON API gives cross-host status for `jellyhome`, `jellybase`, and `jellyberry`. |
| Borg/Borgmatic systemd timer | `systemctl list-timers '*borg*' --all --no-pager` | `LAST`, `NEXT` | timer/service active state | Command-readable; useful for schedule health, less ideal than JSON/Prometheus for freshness. |
| Borg/Borgmatic logs | `/var/log/home-network-borgmatic/*.log` | filename and Borg `Time (start)` / `Time (end)` lines | command exit is implied by wrapper status; log contains archive summary | Human-readable fallback; not primary automation source. |

## Hermes daily backup to GitHub

### Schedule and job state

Primary machine-readable source:

```bash
python3 - <<'PY'
import json
from pathlib import Path
jobs = json.loads(Path('/home/jellybot/.hermes/cron/jobs.json').read_text())['jobs']
job = next(j for j in jobs if j['id'] == 'e5448d934cf9')
print(job['name'])
print(job['schedule_display'])
print(job['enabled'], job['state'])
print(job['last_run_at'], job['last_status'], job['last_error'])
print(job['next_run_at'])
PY
```

Expected current sample:

```text
daily-hermes-backup-to-github
0 3 * * *
True scheduled
2026-05-30T03:01:04.494548+01:00 ok None
2026-05-31T03:00:00+01:00
```

Relevant `jobs.json` fields:

- `id`: `e5448d934cf9`
- `name`: `daily-hermes-backup-to-github`
- `script`: `backup_hermes_to_github.sh`
- `no_agent`: `true`
- `schedule_display`: `0 3 * * *`
- `enabled`: `true`
- `last_run_at`: latest scheduler completion timestamp
- `last_status`: `ok` or failed status
- `last_error`: error text if scheduler captured a failure

Permissions observed:

- `/home/jellybot/.hermes/cron/jobs.json` is readable by the `jellybot` account running Hermes.
- The active Kanban worker profile's `cronjob(action='list')` returned no jobs because it reads the `homenetworkworker` profile; this backup job lives in the default Hermes home at `/home/jellybot/.hermes/cron/jobs.json`. Automation must read the default home explicitly or run under the default profile.

Failure cases to handle:

- Missing job id: job was removed or moved to another profile.
- `enabled: false` or `state: paused`: backup is not scheduled.
- `last_status` not `ok` or `last_error` non-null: scheduler or script failure.
- `last_run_at` older than the freshness threshold, for example more than 26 hours for a daily 03:00 job.

### Backup script

Runtime script:

```text
/home/jellybot/.hermes/scripts/backup_hermes_to_github.sh
```

Core behavior:

- Clones/pulls `git@github.com:dotalbot/agents_config_knowledge.git` into `/home/jellybot/.hermes-backup-worktree`.
- Syncs `/home/jellybot/.hermes/` into `snapshot/.hermes/` with exclusions for secrets and churn: `.env`, `auth.json`, logs, sessions, caches, venvs, `cron/output/`, state DBs, Kanban DBs, etc.
- Aborts if a file over 95 MiB would be committed.
- Commits only when the snapshot changed.
- Pushes to GitHub.
- Runs restore verification by extracting `git archive HEAD snapshot/.hermes` to a temp directory and checking for `snapshot/.hermes/config.yaml`.

Exact status command:

```bash
/home/jellybot/.hermes/scripts/check_backup_status.sh
```

Observed output:

```text
Backup status: ran at 2026-05-30 03:01:04
Backed up ~/.hermes to git@github.com:dotalbot/agents_config_knowledge.git at 2026-05-30T02:00:58Z (restore test: ok, files=6417)
```

Automation notes:

- This helper reads `/home/jellybot/.hermes/cron/output/e5448d934cf9/*.md`, chooses the newest Markdown output file, parses the `**Run Time:**` header, and prints the final line.
- It is suitable as a quick command-readable check, but the underlying `jobs.json` is better for strict freshness because it is JSON.
- If a no-change backup run exits quietly, the scheduler may still create a run output file with no final backup summary. In that case use `jobs.json:last_status` for run success and the latest output containing `restore test: ok` for the last changed snapshot restore check.

Output and restore-verification source:

```text
/home/jellybot/.hermes/cron/output/e5448d934cf9/2026-05-30_03-01-04.md
```

Observed final line:

```text
Backed up ~/.hermes to git@github.com:dotalbot/agents_config_knowledge.git at 2026-05-30T02:00:58Z (restore test: ok, files=6417)
```

Failure cases to handle:

- `Host key verification failed`: GitHub host key missing for the backup SSH key context.
- `Permission denied (publickey)`: `/home/jellybot/.ssh/hermes_backup_github` lacks access to the private repo.
- `Backup aborted: large file would exceed GitHub limit`: excluded paths need updating or large generated state needs moving out of the snapshot.
- Restore test failure text: `Backup push succeeded, but restore test failed: ...`; treat as failed even if push succeeded.
- No `.md` output files: backup job has never produced captured output or output path is wrong.

## Borg/Borgmatic backups

### Local sanitized status JSON

Primary local machine-readable source on each Borgmatic host:

```text
/var/lib/home-network/backup-status/<host>.json
```

Observed on `jellyberry`:

```bash
python3 -m json.tool /var/lib/home-network/backup-status/jellyberry.json
```

Observed output:

```json
{
    "archive_name": "jellyberry-2026-05-30T03:25:56",
    "duration_seconds": 17,
    "exit_code": 0,
    "host": "jellyberry",
    "message": "scheduled backup completed; log=/var/log/home-network-borgmatic/jellyberry-scheduled-20260530-032555.log",
    "repository": "ssh://jellybackup@192.168.1.75/home/jellybackup/externaldisk/borg_jellyberry",
    "repository_reachable": true,
    "status": "success",
    "updated_at": "2026-05-30T02:26:18.916960+00:00"
}
```

Automation-ready fields:

- `updated_at`: latest status timestamp.
- `status`: expect `success`.
- `exit_code`: expect `0`.
- `repository_reachable`: expect `true`.
- `archive_name`: latest archive identifier.
- `message`: includes log path, but should not be the primary status source.

Permissions observed:

```text
-rw-r--r-- root:root /var/lib/home-network/backup-status/jellyberry.json
```

This is readable by non-root automation on `jellyberry`. Writing/updating it is performed by the root-run Borgmatic wrapper.

Failure cases to handle:

- Missing JSON file: host has not run the managed status stage/wrapper, or path bootstrap did not happen.
- Stale `updated_at`: scheduled backup did not run or status update failed.
- `status` not `success`, `exit_code` not `0`, or `repository_reachable` false: backup or repository health failure.
- Invalid JSON or partial file: wrapper bug or interrupted write; treat as failure.

### Prometheus textfile metrics

Primary local metrics source:

```text
/var/lib/node_exporter/textfile_collector/borgmatic_<host>.prom
```

Observed on `jellyberry`:

```bash
sed -n '1,80p' /var/lib/node_exporter/textfile_collector/borgmatic_jellyberry.prom
```

Observed metric lines:

```text
borgmatic_last_run_timestamp_seconds{host="jellyberry"} 1780107978
borgmatic_last_run_success{host="jellyberry"} 1
borgmatic_last_run_exit_code{host="jellyberry"} 0
borgmatic_last_run_duration_seconds{host="jellyberry"} 17
borgmatic_repository_reachable{host="jellyberry"} 1
borgmatic_last_archive_info{host="jellyberry",archive_name="jellyberry-2026-05-30T03:25:56"} 1
```

Timestamp conversion example:

```bash
date -d @1780107978 -Is
```

Observed output:

```text
2026-05-30T03:26:18+01:00
```

Permissions observed:

```text
-rw-r--r-- root:root /var/lib/node_exporter/textfile_collector/borgmatic_jellyberry.prom
```

Automation notes:

- This is suitable for local no-agent checks and node_exporter ingestion.
- Metric format is command-readable, but the JSON status file is easier for shell/Python status scripts.

Failure cases to handle:

- File missing: textfile collector directory not created, wrapper not run, or host not enabled.
- Timestamp stale: backup did not run or wrapper failed before metric write.
- `borgmatic_last_run_success` != `1`, `borgmatic_last_run_exit_code` != `0`, or `borgmatic_repository_reachable` != `1`: failure.
- Prometheus scrape may still fail even when this file exists; check `node_textfile_scrape_error` and central Prometheus target status.

### Central Prometheus API

Cross-host machine-readable source:

```bash
curl -fsG --data-urlencode 'query=borgmatic_last_run_success' \
  http://jellybase:9090/api/v1/query
```

Observed result included all three primary hosts:

```text
host=jellybase value=1
host=jellyberry value=1
host=jellyhome value=1
```

Useful exact queries:

```bash
curl -fsG --data-urlencode 'query=borgmatic_last_run_timestamp_seconds' \
  http://jellybase:9090/api/v1/query
curl -fsG --data-urlencode 'query=borgmatic_last_run_success' \
  http://jellybase:9090/api/v1/query
curl -fsG --data-urlencode 'query=borgmatic_repository_reachable' \
  http://jellybase:9090/api/v1/query
curl -fsG --data-urlencode 'query=borgmatic_last_archive_info' \
  http://jellybase:9090/api/v1/query
```

Observed snapshot at inspection time:

```text
borgmatic_last_run_timestamp_seconds:
  jellybase  1780110996 -> 2026-05-30T04:16:36+01:00
  jellyberry 1780107978 -> 2026-05-30T03:26:18+01:00
  jellyhome  1780107058 -> 2026-05-30T03:10:58+01:00
borgmatic_last_run_success:
  jellybase  1
  jellyberry 1
  jellyhome  1
borgmatic_repository_reachable:
  jellybase  1
  jellyberry 1
  jellyhome  1
borgmatic_last_archive_info:
  jellybase  jellybase-2026-05-30T03:15:54
  jellyberry jellyberry-2026-05-30T03:25:56
  jellyhome  jellyhome-2026-05-30T03:08:33
```

Automation notes:

- This is the best single source for cross-host freshness/status checks.
- Prometheus returns JSON, so no manual interpretation is needed.
- Query from a host that can reach `jellybase:9090`.

Failure cases to handle:

- HTTP connection failure: Prometheus down, DNS failure, network issue, or not on LAN/Tailnet.
- Empty result vector: target not scraped or metric name changed.
- Host missing from result: node_exporter/textfile metrics missing for that host or scrape target down.
- Metric timestamp stale but success still `1`: last successful backup is old; freshness check must use timestamp age, not success alone.

### Systemd timer and service

Schedule source on inspected host:

```bash
systemctl list-timers '*borg*' --all --no-pager
systemctl list-units 'home-network-borgmatic-*' 'borgmatic*' --all --no-pager
systemctl cat home-network-borgmatic-jellyberry.service home-network-borgmatic-jellyberry.timer --no-pager
```

Observed sample:

```text
NEXT                        LEFT LAST                         PASSED UNIT                                    ACTIVATES
Sun 2026-05-31 03:01:19 BST  12h Sat 2026-05-30 03:25:55 BST 11h ago home-network-borgmatic-jellyberry.timer home-network-borgmatic-jellyberry.service

home-network-borgmatic-jellyberry.service loaded inactive dead
home-network-borgmatic-jellyberry.timer   loaded active   waiting
```

Timer definition observed:

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
RandomizedDelaySec=30m
Persistent=true
```

Permissions observed:

- Reading timer/service status does not require sudo.
- `/usr/local/sbin/home-network-borgmatic-run-jellyberry` is `-rwxr-x--- root:root`, so the `jellybot` user cannot inspect or run the wrapper directly without sudo.
- Non-interactive sudo was not available during inspection (`sudo -n true` exited `1`).

Automation notes:

- Use systemd timer state to detect schedule drift or a disabled timer.
- Do not use systemd alone for backup success; pair it with status JSON or Prometheus metrics.

Failure cases to handle:

- Timer missing or inactive: scheduled backups will not run.
- Service failed: inspect `systemctl status` and root-readable wrapper/logs if permitted.
- `LAST` old or absent while status JSON is old: timer has not fired.

### Borg/Borgmatic logs

Observed latest local log:

```text
/var/log/home-network-borgmatic/jellyberry-scheduled-20260530-032555.log
```

Sample content:

```text
Repository: ssh://jellybackup@192.168.1.75/home/jellybackup/externaldisk/borg_jellyberry
Archive name: jellyberry-2026-05-30T03:25:56
Time (start): Sat, 2026-05-30 03:25:59
Time (end):   Sat, 2026-05-30 03:25:59
Duration: 0.04 seconds
Number of files: 38
```

Permissions observed:

```text
-rw-r--r-- root:root /var/log/home-network-borgmatic/jellyberry-scheduled-20260530-032555.log
```

Automation notes:

- Logs are useful as a diagnostic fallback and to link from `backup-status/<host>.json:message`.
- They are less reliable than JSON/Prometheus because not every failure necessarily produces a clean parseable log line.

Failure cases to handle:

- Missing log path referenced by status JSON: log rotation/cleanup or wrapper failure.
- Log exists but status JSON reports failure: trust status JSON and inspect log for cause.
- Logs may include repository URLs and archive metadata; do not send raw logs to public channels.

## Restore verification outputs

### Hermes GitHub backup restore verification

Current existing restore verification is embedded in the Hermes backup script output. A successful changed backup prints:

```text
restore test: ok, files=<count>
```

Observed source:

```text
/home/jellybot/.hermes/cron/output/e5448d934cf9/2026-05-30_03-01-04.md
```

Observed final line:

```text
Backed up ~/.hermes to git@github.com:dotalbot/agents_config_knowledge.git at 2026-05-30T02:00:58Z (restore test: ok, files=6417)
```

This is command-readable but not a separate durable JSON artifact. Automation can grep the newest output file that contains `restore test: ok`, but strict daily confidence should combine:

1. `jobs.json:last_run_at` and `last_status == ok` for scheduler freshness.
2. Latest output final line containing `restore test: ok` for the latest changed backup snapshot verification.

### Borg/Borgmatic restore test outputs

The rollout generator defines `stage-07-check-and-restore-test.sh`; it runs:

```bash
borgmatic check
borgmatic extract --archive latest --path "$archive_path" --destination "$restore_dir"
diff -q "$restore_source" "${restore_dir}/${archive_path}"
echo "RESTORE_TEST_OK ${restore_dir}"
```

The stage writes success into the same sanitized status JSON via a message like:

```text
check and restore test passed: <source> -> /tmp/borgmatic-restore-test-<host>-<timestamp>
```

However, during this inspection no durable local `borgmatic-restore-test-*` directory or separate restore-test log was found on `jellyberry`:

```bash
find /tmp -maxdepth 1 -name 'borgmatic-restore-test-*' -print
find /var/log/home-network-borgmatic -maxdepth 1 -name '*restore*' -print
```

Both returned no files. The durable source of scheduled backup confidence is therefore the sanitized status JSON and Prometheus metrics; restore drill evidence currently lives in documented runbooks/plans or transient `/tmp` outputs unless a future task adds durable restore-test result files.

Existing documented restore drills in `/home/jellybot/home-network` include service-specific runbooks such as:

- `docs/runbooks/homeassistant-restore.md`
- `docs/runbooks/mosquitto-restore.md`
- `docs/plans/011-restore-drills-and-runtime-caveats.md`

Automation note: do not treat those narrative runbook entries as current backup freshness. They prove drills happened, not that the latest scheduled backup is restorable.

## Recommended automation contract

For a lightweight backup confidence check, use this order:

1. Read `/home/jellybot/.hermes/cron/jobs.json` and assert job `e5448d934cf9` is enabled, scheduled, `last_status == "ok"`, and `last_run_at` is fresh.
2. Run `/home/jellybot/.hermes/scripts/check_backup_status.sh` or parse the newest `/home/jellybot/.hermes/cron/output/e5448d934cf9/*.md` to find the latest `restore test: ok` line.
3. Query `http://jellybase:9090/api/v1/query` for `borgmatic_last_run_timestamp_seconds`, `borgmatic_last_run_success`, and `borgmatic_repository_reachable` across all expected hosts.
4. On each local host, fall back to `/var/lib/home-network/backup-status/<host>.json` if Prometheus is unreachable.
5. Use systemd timer status only to explain schedule failures, not as the primary success source.

Minimum machine-readable freshness rule:

```text
Hermes backup fresh if:
  jobs[e5448d934cf9].enabled == true
  jobs[e5448d934cf9].last_status == "ok"
  now - parse_timestamp(jobs[e5448d934cf9].last_run_at) <= 26 hours

Borgmatic host fresh if:
  borgmatic_last_run_success{host=...} == 1
  borgmatic_repository_reachable{host=...} == 1
  now - borgmatic_last_run_timestamp_seconds{host=...} <= 26 hours
```

This avoids manual interpretation. Success without freshness is not enough; the timestamp age is the actual confidence check. Backups are like milk: the label matters, but the date matters more.
