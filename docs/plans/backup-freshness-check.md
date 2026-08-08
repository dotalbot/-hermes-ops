# Backup freshness check plan

## Goal

Add a deterministic manual check that reads real Hermes backup and Borg/Borgmatic metadata and reports whether the latest successful backup is fresh.

## Scope

- Add a Python script under `scripts/` that can be run manually.
- Read Hermes backup job metadata from `/home/jellybot/.hermes/cron/jobs.json` for job `e5448d934cf9`.
- Read Hermes restore verification evidence from `/home/jellybot/.hermes/cron/output/e5448d934cf9/*.md`.
- Read Borg/Borgmatic status from central Prometheus at `http://jellybase:9090/api/v1/query` for `jellyhome`, `jellybase`, and `jellyberry`.
- Fall back to local sanitized Borgmatic status JSON when Prometheus is unreachable.
- Emit structured status with component, last successful backup time, age, status, evidence/source, and next action.

## Non-goals

- Do not trigger a backup.
- Do not run a restore drill.
- Do not mutate cron, Borgmatic, Prometheus, or systemd configuration.
- Do not require sudo.

## Acceptance criteria

- The check can be run manually.
- A fresh successful backup returns `green`.
- Missing metadata, stale timestamps, or failure fields return `yellow`/`red` with a concrete next action.
- Status is based on actual backup metadata/output, not schedule assumptions.
- Verification includes live execution against the current metadata sources plus offline parser/unit tests.

## Files expected to change

- `scripts/backup_freshness_check.py`
- `tests/test_backup_freshness_check.py`
- `docs/runbooks/backup-freshness-check.md`
- `docs/README.md`
