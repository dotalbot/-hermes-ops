# Dashboard health scheduled execution plan

## Goal

Make the deterministic dashboard health checker easy for an operator to run manually and safe to run on a recurring schedule.

## Scope

- Add a scheduler-friendly runtime wrapper for Hermes no-agent cron.
- Document installation/update commands for the runtime script copy and scheduled job.
- Expand the operator runbook with inventory location, manual checks, green/red interpretation, dashboard inventory updates, common failure troubleshooting, and validation that intentionally stale/unreachable entries are caught.

## Non-goals

- Do not hard-code Discord webhook secrets.
- Do not mutate the production dashboard inventory during validation.
- Do not make green runs noisy by default.

## Files expected to change

- `.gitignore`
- `scripts/dashboard_health_notifier_cron.sh`
- `docs/runbooks/dashboard-health-notifier.md`
- `docs/plans/dashboard-health-scheduled-execution.md`
- `docs/README.md`

## Verification strategy

- Shell syntax check the cron wrapper.
- Python syntax check the checker and notifier.
- Run notifier in dry-run/console mode against the real inventory.
- Run the cron wrapper directly.
- Create a temporary modified inventory with one intentionally unreachable port and prove the wrapper/checker returns red without changing production inventory.
- Run `git diff --check`.

## Rollback

- Remove or pause the Hermes cron job if installed.
- Remove `/home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh` runtime copy.
- Revert the documentation and wrapper commit from the feature branch.
