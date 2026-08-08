# Backup freshness check

Purpose: deterministic manual check for latest Hermes GitHub backup and home-network Borg/Borgmatic backup freshness. The check reads real metadata/output and does not assume success from a schedule.

## Script

Repository copy:

```bash
/home/jellybot/dev_projects/hermes-ops/scripts/backup_freshness_check.py
```

Manual text run:

```bash
cd /home/jellybot/dev_projects/hermes-ops
python3 scripts/backup_freshness_check.py
```

Manual JSON run:

```bash
cd /home/jellybot/dev_projects/hermes-ops
python3 scripts/backup_freshness_check.py --json
```

Exit codes:

- `0`: every component is green.
- `1`: one or more components is yellow or red.
- `2`: bad CLI/configuration input.

## Sources read

Hermes backup:

- `/home/jellybot/.hermes/cron/jobs.json`, job `e5448d934cf9`
- `/home/jellybot/.hermes/cron/output/e5448d934cf9/*.md` for latest `restore test: ok` evidence

Borg/Borgmatic backups:

- Central Prometheus API: `http://jellybase:9090/api/v1/query`
- Queries:
  - `borgmatic_last_run_timestamp_seconds`
  - `borgmatic_last_run_success`
  - `borgmatic_repository_reachable`
  - `borgmatic_last_archive_info`
- Expected hosts by default: `jellyhome`, `jellybase`, `jellyberry`

Fallback if Prometheus is unreachable:

- The script emits a red `Borgmatic backups (Prometheus)` result because cross-host metadata is missing.
- It also reads local status JSON for the current host: `/var/lib/home-network/backup-status/<hostname>.json`.
- The local fallback can prove only the current host; it never turns a Prometheus outage into an overall green status.

## Output contract

Each result includes:

- `component`
- `last_successful_backup_time`
- `age_seconds`
- `age_human`
- `status`: `green`, `yellow`, or `red`
- `evidence`
- `source`
- `next_action`

## Status rules

Default freshness thresholds:

- Green: latest successful metadata timestamp is younger than 26 hours and success fields are good.
- Yellow: timestamp is at least 26 hours old but younger than 48 hours, or restore-test evidence is missing while the scheduler reports success.
- Red: timestamp is at least 48 hours old, required metadata is missing, or failure fields indicate an unsuccessful backup/repository state.

Hermes is green only when:

- the configured cron job exists,
- `enabled == true`,
- `state` is scheduled/running,
- `last_status == "ok"`,
- `last_error` is empty,
- `last_run_at` is fresh,
- a captured output file contains `restore test: ok`.

Borgmatic host status is green only when Prometheus reports:

- `borgmatic_last_run_success{host=...} == 1`,
- `borgmatic_repository_reachable{host=...} == 1`,
- `borgmatic_last_run_timestamp_seconds{host=...}` is fresh.

## Useful options

```bash
python3 scripts/backup_freshness_check.py --warn-hours 26 --red-hours 48
python3 scripts/backup_freshness_check.py --borg-hosts jellyhome jellybase jellyberry
python3 scripts/backup_freshness_check.py --prometheus-url http://jellybase:9090/api/v1/query
python3 scripts/backup_freshness_check.py --no-local-fallback
```

## Failure handling

- Missing Hermes job: find the current daily Hermes backup cron job id or recreate the job.
- Failed Hermes job: inspect the latest cron output under `/home/jellybot/.hermes/cron/output/e5448d934cf9/` and fix the backup script failure.
- Missing Hermes restore evidence: run `/home/jellybot/.hermes/scripts/check_backup_status.sh` and inspect captured output for restore-test lines.
- Prometheus unreachable: restore access to `jellybase:9090`, or run on a host that can reach it; local fallback only covers the current host.
- Missing Borgmatic host metric: check node_exporter/textfile collector and Borgmatic wrapper on that host.
- Borgmatic failure/repository unreachable: inspect `/var/lib/home-network/backup-status/<host>.json` and the latest `/var/log/home-network-borgmatic/` log on that host.
- Stale Borgmatic timestamp: check the host's Borgmatic timer/service and wrapper output.

## Verification performed

Live verification on 2026-05-30:

```bash
python3 -m unittest tests/test_backup_freshness_check.py
python3 scripts/backup_freshness_check.py --json
```

Observed result: 8 unit tests passed and live metadata returned `summary_status: green` for Hermes GitHub backup plus Borgmatic hosts `jellyhome`, `jellybase`, and `jellyberry`.
