# Dashboard link no-agent watchdog

Purpose: deterministic watchdog for stale/broken dashboard and observability links. It is designed for Hermes `no_agent=true` cron use, so a normal passing run prints nothing and produces no chat notification.

## Runtime files

Source of truth in this repo:

- Script: `scripts/dashboard_link_check.py`
- Config: `config/dashboard-links.json`
- Runbook: `docs/runbooks/dashboard-link-no-agent-watchdog.md`

Runtime copy for Hermes cron:

- Script: `/home/jellybot/.hermes/scripts/dashboard_link_check.py`
- Default config path: `/home/jellybot/hermes-ops/config/dashboard-links.json`
- State: `/home/jellybot/.hermes/state/dashboard_link_check_state.json`
- Lock: `/home/jellybot/.hermes/state/dashboard_link_check.lock`
- Log: `/home/jellybot/.hermes/logs/dashboard_link_check.log`

## Cron schedule

Installed job:

- Job id: `adf27938fea4`
- Name: `dashboard-link-watchdog`
- Schedule: `every 30m`
- Mode: `no_agent=true`
- Script: `dashboard_link_check.py`
- Delivery: `local`

`local` delivery keeps this first rollout conservative. Change delivery to Discord/Telegram after confirming the link list matches the operator's preferred alert surface.

Ready-to-install CLI equivalent:

```bash
hermes cron create "every 30m" \
  --name dashboard-link-watchdog \
  --script dashboard_link_check.py \
  --no-agent \
  --deliver local
```

With the tool API, use:

```python
cronjob(
    action="create",
    name="dashboard-link-watchdog",
    schedule="every 30m",
    script="dashboard_link_check.py",
    no_agent=True,
    deliver="local",
    prompt="Deterministic no-agent dashboard link watchdog. Empty stdout means no alert; non-empty stdout is the fixed alert/digest body.",
)
```

## Manual runs

Normal quiet watchdog mode:

```bash
python3 /home/jellybot/.hermes/scripts/dashboard_link_check.py
```

Expected passing behavior: no stdout.

Digest/report mode:

```bash
python3 /home/jellybot/.hermes/scripts/dashboard_link_check.py --digest
```

Forced failure test without touching the real config:

```bash
tmp=$(mktemp)
printf '%s\n' '{"links":[{"label":"forced bad","url":"http://127.0.0.1:1/","expected":{"status":200},"timeout_seconds":0.2,"retries":0}]}' > "$tmp"
python3 /home/jellybot/.hermes/scripts/dashboard_link_check.py --config "$tmp" --state /tmp/dashboard-link-check-test-state.json --no-state
rm -f "$tmp" /tmp/dashboard-link-check-test-state.json
```

Expected output starts with:

```text
Dashboard link check failed:
- forced bad: expected status 200, got no response; ...
```

## Quiet/noise behavior

- All links pass and there was no previous failure: stdout is empty.
- A new failure fingerprint appears: stdout is a concise fixed alert.
- The same failure fingerprint repeats: stdout is empty to suppress duplicate alerts.
- A prior failure recovers: stdout reports recovery once.
- `--digest` or `DASHBOARD_LINK_CHECK_DIGEST=1`: stdout always contains a full report and does not update alert-suppression state.
- Overlapping cron runs exit successfully with no stdout.

## Config format

`config/dashboard-links.json` contains:

- `defaults.method`: `GET` or `HEAD` only.
- `defaults.timeout_seconds`, `defaults.retries`, `defaults.retry_delay_seconds`.
- `links[].label`: human label for alerts.
- `links[].url`: fixed `http://` or `https://` target only.
- `links[].expected.status`: exact status code, or `status_class`, or `status_min`/`status_max`.
- `links[].expected.text_contains`: optional bounded body text check.

Keep this list fixed and operator-owned. Do not let browser input, LLM output, or a dashboard request provide arbitrary URLs.

## Logging and errors

The script writes one compact status line per completed run to `/home/jellybot/.hermes/logs/dashboard_link_check.log`. Logging failures are ignored so log filesystem issues do not create noisy false alerts.

Bad config or unexpected fatal exceptions exit non-zero; Hermes no-agent cron will emit its normal error alert for those runs. Per-link HTTP failures are reported as link-check failures, not Python stack traces.

## Verification performed

- `python3 -m py_compile scripts/dashboard_link_check.py`
- Runtime copy created at `/home/jellybot/.hermes/scripts/dashboard_link_check.py`
- `python3 /home/jellybot/.hermes/scripts/dashboard_link_check.py --digest`
- Quiet mode run after a passing digest produced empty stdout
- Forced bad config emitted a fixed `Dashboard link check failed:` alert
- `git diff --check`
