# No-agent cron implementation pattern

This guide documents the current Hermes no-agent cron pattern as seen in the live default profile on jellyberry and the upstream Hermes scheduler. It is intended for workers implementing similar deterministic cron/watchdog jobs.

## Pattern in one line

Use a script under `/home/jellybot/.hermes/scripts/`, schedule it with a Hermes cron job using `no_agent=true`, and make stdout the contract:

- stdout with content: deliver that content verbatim to the configured target.
- empty stdout: quiet successful tick; no Discord/Telegram/etc. message.
- non-zero exit or timeout: deliver an error alert so broken watchdogs are not silent.

For explicit daily digest jobs, do not stay quiet on success. A digest is supposed to post every scheduled run, so the script should always print the complete Discord-ready digest unless it truly fails.

## Live files and paths found

Runtime profile paths:

- Cron registry: `/home/jellybot/.hermes/cron/jobs.json`.
- Cron output root: `/home/jellybot/.hermes/cron/output/`.
- Script directory: `/home/jellybot/.hermes/scripts/`.
- Weather briefing script: `/home/jellybot/.hermes/scripts/west_mersea_daily_briefing.py`.
- Weather location helper: `/home/jellybot/.hermes/scripts/weather_location_command.py`.
- Weather location state: `/home/jellybot/.hermes/scripts/weather_locations.json`.
- Event-watchdog example: `/home/jellybot/.hermes/scripts/portfolio_event_refresh.py`.
- Alert-watchdog example: `/home/jellybot/.hermes/scripts/portfolio_refresh_alert.py`.
- Backup no-agent example: `/home/jellybot/.hermes/scripts/backup_hermes_to_github.sh`.
- Backup status helper: `/home/jellybot/.hermes/scripts/check_backup_status.sh`.

Hermes implementation/docs paths inspected:

- Scheduler no-agent behavior: `/home/jellybot/.hermes/hermes-agent/cron/scheduler.py`, especially `_run_job_script()` around lines 851-970 and the `no_agent` short-circuit around lines 1220-1322.
- User-facing no-agent docs: `/home/jellybot/.hermes/hermes-agent/website/docs/guides/cron-script-only.md`.
- CLI flag wiring: `/home/jellybot/.hermes/hermes-agent/hermes_cli/main.py` has `--no-agent`; `/home/jellybot/.hermes/hermes-agent/hermes_cli/cron.py` displays no-agent mode.

## Existing live jobs

Current `cronjob(action="list")` showed these relevant no-agent jobs:

- `e8b705a14aa6` / `Daily West Mersea Weather + Tides + Joke + Quote`
  - Schedule: `30 8 * * *`.
  - Script: `west_mersea_daily_briefing.py`.
  - Delivery: Discord channel/thread target `discord:1500902520988631363:1506327936758710323`.
  - `enabled_toolsets`: `["web"]`, although no-agent mode runs the script directly and does not start an agent/tool loop.
  - Behavior: explicit digest mode; prints a full briefing every morning.

- `4e4598693e30` / `portfolio-event-refresh`
  - Schedule: `every 5m`.
  - Script: `portfolio_event_refresh.py`.
  - Delivery: `local`.
  - Behavior: watchdog mode; stays quiet unless a release/tag/successful-PR fingerprint changes or a forced run is requested.

- `ca8bdd42917a` / `portfolio-refresh-alert`
  - Schedule: `every 30m`.
  - Script: `portfolio_refresh_alert.py`.
  - Delivery: Discord.
  - Behavior: watchdog mode; prints only degradation/recovery alerts, otherwise empty stdout.

- `e5448d934cf9` / `daily-hermes-backup-to-github`
  - Schedule: `0 3 * * *`.
  - Script: `backup_hermes_to_github.sh`.
  - Delivery: `local`.
  - Behavior: backup mode; empty stdout when no Git diff, output only when a backup commit/push/restore verification happened or when a failure occurs.

- `2377afc113bf` / `weekly-hermes-backup-healthcheck`
  - Schedule: `20 3 * * 1`.
  - Script: `check_backup_status.sh`.
  - Delivery: Discord.
  - Behavior: status digest; reads the latest backup output file and prints a short summary.

## Script structure conventions

Python no-agent scripts should follow this shape:

```python
#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

STATE = Path("/absolute/or/env-overridable/state.json")

def main():
    changed = detect_change()
    if not changed:
        return  # empty stdout = silent tick
    print(render_message())

if __name__ == "__main__":
    main()
```

Bash no-agent scripts should follow this shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Do checks/work.
# If nothing happened and no alert is needed, exit with no stdout.
if no_change; then
  exit 0
fi

echo "human-facing message"
```

Important scheduler conventions:

- Scripts must reside under `/home/jellybot/.hermes/scripts/`. With the `cronjob` tool, pass a relative filename such as `west_mersea_daily_briefing.py`, not an arbitrary source path.
- `.sh` and `.bash` scripts run with bash. Other extensions run with Hermes' current Python interpreter (`sys.executable`). The scheduler deliberately does not trust shebangs for interpreter selection.
- The scheduler captures stdout/stderr, strips surrounding whitespace, redacts secrets, and uses stdout as the message body for successful no-agent jobs.
- Runtime `HOME`/`HERMES_HOME` are set for the active profile. Prefer explicit env overrides for project roots and state paths where practical.
- If a job has `workdir`, no-agent runs temporarily from that directory, but scripts are still resolved under `~/.hermes/scripts/`.

## Weather/tide briefing pattern

The live West Mersea briefing is an explicit digest, not a quiet watchdog.

`/home/jellybot/.hermes/scripts/west_mersea_daily_briefing.py` does the following:

- Reads location state from `/home/jellybot/.hermes/scripts/weather_locations.json`.
- Defaults to `West Mersea, UK`.
- Special-cases West Mersea coordinates: lat `51.777`, lon `0.918`, timezone `Europe/London`.
- Uses Open-Meteo forecast APIs for current conditions, daily forecast, sunrise/sunset, rain chance, UV, wind, humidity, pressure, visibility, and cloud cover.
- Uses BBC Weather coast-and-sea tide page `https://www.bbc.co.uk/weather/coast-and-sea/tide-tables/1/124` and parses the embedded `data-data-id="tides"` JSON, sourced from BBC Weather / UK Hydrographic Office.
- Uses `https://icanhazdadjoke.com/` for the dad joke with JSON accept headers.
- Uses `https://zenquotes.io/api/today` for the quote.
- Renders one Discord-friendly markdown message with emoji section headers and bullets; no markdown tables.
- Catches per-section failures and prints fallback values such as `Unavailable`, so one bad upstream does not kill the whole digest.
- Includes tides only when the requested location contains `west mersea`.

`/home/jellybot/.hermes/scripts/weather_location_command.py` is a manual helper for location management:

- `list`: prints known locations.
- `add <location>`: appends a normalized location to `weather_locations.json`.
- `set <location> [--add-if-missing]`: updates `current`, saves the file, then immediately runs the briefing once for feedback.

Current location state:

```json
{
  "current": "West Mersea, UK",
  "known": [
    "West Mersea, UK",
    "Sofia, Bulgaria",
    "Sandton, Johannesburg, South Africa"
  ]
}
```

## Quiet watchdog pattern

Use this when the schedule is frequent and the user only wants a message if something changed or crossed a threshold.

Examples:

- `portfolio_event_refresh.py`:
  - Polls GitHub repo release/tag/successful-merged-PR signals.
  - Stores state in `/home/jellybot/portfolio-intel/data/portfolio_event_refresh_state.json`.
  - Uses a lock file `/home/jellybot/portfolio-intel/data/portfolio_event_refresh.lock` with stale-lock handling.
  - If another run holds the lock, returns with no output.
  - If the fingerprint did not change, writes state and returns with no output.
  - If changed, runs the collector and prints a concise refresh summary plus warnings.
  - Supports explicit test/digest mode with `PORTFOLIO_EVENT_REFRESH_FORCE=1` or `--force`, which should print a refresh message even if the normal state gate would stay quiet.

- `portfolio_refresh_alert.py`:
  - Prints only when portfolio collector failures cross the alert threshold or recover.
  - Comment explicitly states: `Quiet mode: no output means no notification for no_agent cron jobs.`

- `backup_hermes_to_github.sh`:
  - Runs a deterministic rsync/Git backup.
  - Exits with no stdout if `git diff --cached --quiet` finds no change.
  - Prints a backup/restore verification summary only after a backup commit/push happens.

## Output and logging behavior

Hermes writes a markdown output record under `/home/jellybot/.hermes/cron/output/<job_id>/` for each no-agent run.

Observed examples:

- Weather digest output: `/home/jellybot/.hermes/cron/output/e8b705a14aa6/2026-05-29_08-30-43.md`
  - Contains the full Discord-ready briefing after the standard cron header.

- Quiet event-watchdog output: `/home/jellybot/.hermes/cron/output/4e4598693e30/2026-05-29_22-50-22.md`
  - Contains only scheduler metadata and `**Status:** silent (empty output)`.
  - The message was not delivered.

- Event-watchdog changed output: `/home/jellybot/.hermes/cron/output/4e4598693e30/2026-05-28_14-23-41.md`
  - Contains collector output, `Portfolio diagrams refreshed: ...`, and warning lines.

- Backup output: `/home/jellybot/.hermes/cron/output/e5448d934cf9/2026-05-29_03-00-42.md`
  - Contains Git commit output and `Backed up ~/.hermes ... (restore test: ok, files=6330)`.

The scheduler's saved markdown document is not the same as delivered content. For non-empty no-agent stdout, the saved file includes metadata and the script output; delivery receives just stdout. For empty stdout, the saved file records `silent (empty output)` but delivery is suppressed.

## Configuration expectations

- Put scripts in `/home/jellybot/.hermes/scripts/` and schedule with `script: "filename.py"` or `script: "filename.sh"`.
- Jobs live in `/home/jellybot/.hermes/cron/jobs.json`; prefer managing them with the `cronjob` tool or `hermes cron`, not manual JSON edits.
- Use `deliver="local"` for internal collectors/status artifacts and explicit platform targets for user-facing posts.
- Keep secrets in environment variables or `/home/jellybot/.hermes/.env`, not in scripts or docs.
- If a script reads tokens directly from `.env`, load only the named value and never print it. `portfolio_event_refresh.py` reads `GITHUB_TOKEN_RO` or `GITHUB_TOKEN` but prints only sanitized errors.
- For project-specific roots, use env-overridable paths, e.g. `PORTFOLIO_INTEL_ROOT`, `PORTFOLIO_COLLECTOR_SCRIPT`, `HERMES_ENV_FILE`.
- Keep runtime state outside Git unless it is intentionally a tracked artifact. Use atomic writes for JSON state: write a temp file then `os.replace()`.
- Add locks for frequent pollers so overlapping runs do not stampede external APIs or corrupt state.

## Scheduling examples

Using the `cronjob` tool:

```python
cronjob(
    action="create",
    name="Daily West Mersea Weather + Tides + Joke + Quote",
    schedule="30 8 * * *",
    script="west_mersea_daily_briefing.py",
    no_agent=True,
    deliver="discord:<channel_id>:<thread_id>",
    prompt="Optional human-readable description only; no-agent will not call the LLM.",
)
```

Watchdog example:

```python
cronjob(
    action="create",
    name="portfolio-event-refresh",
    schedule="every 5m",
    script="portfolio_event_refresh.py",
    no_agent=True,
    deliver="local",
)
```

CLI equivalent:

```bash
hermes cron create "30 8 * * *" \
  --no-agent \
  --script west_mersea_daily_briefing.py \
  --deliver discord:<channel_id>:<thread_id> \
  --name "Daily West Mersea Weather + Tides + Joke + Quote"
```

## Testing approach

Before scheduling or changing a no-agent script:

1. Syntax-check it:
   - Python: `python3 -m py_compile /home/jellybot/.hermes/scripts/<script>.py`.
   - Bash: `bash -n /home/jellybot/.hermes/scripts/<script>.sh`.
2. Run the script directly and inspect stdout:
   - Digest scripts should print the complete expected message.
   - Quiet watchdogs should print nothing in the no-change case.
   - Forced/test mode should print a clear message, e.g. `--force` or a dedicated environment variable.
3. Trigger through Hermes cron once with `cronjob(action="run", job_id="...")` or `hermes cron run <job_id>`.
4. Inspect `/home/jellybot/.hermes/cron/output/<job_id>/`:
   - Empty stdout should produce a metadata-only file with `**Status:** silent (empty output)`.
   - Non-empty stdout should appear after the `---` separator.
5. If delivery is Discord/Telegram/etc., verify the channel received exactly the script stdout and not a second hand-authored message.
6. For docs-only changes in this repo, run `git diff --check` before commit.

## Worker checklist for new no-agent cron jobs

- [ ] Decide whether this is a digest or a watchdog.
- [ ] Put the source script under `/home/jellybot/.hermes/scripts/` or explicitly sync a repo-maintained source copy there.
- [ ] Make stdout the complete delivery contract.
- [ ] Keep no-change watchdog ticks completely silent: no progress banners, debug prints, warnings, or stack traces on success.
- [ ] Send errors by failing non-zero with useful stderr/stdout; do not catch and suppress real failures.
- [ ] Keep secrets out of stdout, output files, docs, and Git.
- [ ] Use state files and locks for pollers.
- [ ] Add a manual forced/digest mode for verification when normal operation is quiet.
- [ ] Schedule with `no_agent=true` and a relative script filename.
- [ ] Verify direct execution, cron output file, and delivery behavior.
