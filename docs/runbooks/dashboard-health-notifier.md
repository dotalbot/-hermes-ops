# Dashboard health notifier

Purpose: wraps `dashboard_health_check.py` to produce concise Discord-ready
notifications.  Uses the no-agent cron pattern: silent when all checks are
green, delivers only on red failures.

The notifier is **not** a separate watchdog — it is a delivery wrapper around
the deterministic checker.  Schedule either the checker directly (for local
recording) or the notifier (for Discord/Mission Control delivery).

## Source files

| Path | Purpose |
|---|---|
| `scripts/dashboard_notifier.py` | Notifier script (source of truth) |
| `scripts/dashboard_health_check.py` | Deterministic checker (runs as subprocess) |
| `config/dashboard-inventory.json` | Inventory contract for dashboard entries |
| `config/.dashboard-heartbeat-state.json` | Heartbeat interval tracking (auto-created) |

## Usage

```bash
# Default mode (stdout contract for no-agent cron):
#   - Red findings → printed to stdout → delivered by cron scheduler
#   - All green    → empty stdout → cron suppresses delivery
python3 scripts/dashboard_notifier.py

# Dry-run: preview what would be sent, don't actually send
python3 scripts/dashboard_notifier.py --dry-run

# Console mode: always print to stdout regardless of status
python3 scripts/dashboard_notifier.py --console

# Discord webhook: POST formatted message to webhook URL
DASHBOARD_WEBHOOK_URL=https://discord.com/api/webhooks/... \
  python3 scripts/dashboard_notifier.py --to-webhook

# Mission Control: write dashboard-health.json for the MC dashboard
python3 scripts/dashboard_notifier.py --to-mission-control

# Heartbeat: send an all-clear message every N hours
DASHBOARD_HEARTBEAT_HOURS=24 \
  python3 scripts/dashboard_notifier.py --console

# Combine flags: webhook + Mission Control with dry-run
python3 scripts/dashboard_notifier.py \
  --dry-run --to-webhook --to-mission-control

# Combined delivery: webhook + Mission Control at once
DASHBOARD_WEBHOOK_URL=https://discord.com/... \
  python3 scripts/dashboard_notifier.py \
    --to-webhook --to-mission-control
```

## Environment variables (secrets go in `~/.hermes/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DASHBOARD_WEBHOOK_URL` | Discord webhook URL | (empty) |
| `DASHBOARD_MISSION_CONTROL` | Path for Mission Control JSON | `/home/jellybot/portfolio-intel/mission-control-v2/data/dashboard-health.json` |
| `DASHBOARD_HEARTBEAT_HOURS` | Send all-clear heartbeat every N hours (0=disabled) | `0` |
| `DASHBOARD_DRY_RUN` | Set to `1` to enable dry-run by default | (unset) |
| `DASHBOARD_CONSOLE` | Set to `1` to always print to stdout by default | (unset) |
| `DASHBOARD_INVENTORY` | Override path to dashboard-inventory.json | `config/dashboard-inventory.json` |

## Behaviour

### All green (default)
- Prints nothing → no-agent cron scheduler suppresses delivery.
- Silent tick: no Discord message, no chat noise.

### All green (with heartbeat)
- If `DASHBOARD_HEARTBEAT_HOURS` is set and the interval has elapsed since
  the last heartbeat, an all-clear summary is sent.
- Heartbeat state is tracked in `config/.dashboard-heartbeat-state.json`.
- On the first failure after a green period, the heartbeat timer is reset so
  the recovery message is not delayed by the heartbeat gate.

### Red findings
- Produces a clean failure digest with affected entry name and reason.
- Example format:
  ```
  ⚠️  **Dashboard Health: 2 failure(s)** — 2026-05-30T13:57:47Z
  
  • **Loki**
    expected status 2xx, got status 404
  • **MQTT Exporter**
    URLError: <urlopen error timed out>
  
  --- Summary: 69 checks, 56 ok, 2 failed ---
  ```

### Webhook delivery errors
- Webhook errors are logged to stderr but do not crash the script.
- Red findings still produce exit code 1 even if webhook delivery fails.
- Green-run webhook errors produce exit code 0 (not a broken watchdog).

## Scheduling (no-agent cron)

Use the Hermes cron tool:

```python
cronjob(
    action="create",
    name="dashboard-health-notifier",
    schedule="every 30m",
    script="dashboard_notifier.py",
    no_agent=True,
    deliver="discord:<channel_id>:<thread_id>",  # or "local"
)
```

Or CLI equivalent:

```bash
hermes cron create "every 30m" \
  --name dashboard-health-notifier \
  --script dashboard_notifier.py \
  --no-agent \
  --deliver discord:<channel_id>:<thread_id>
```

## Testing

```bash
# 1. Syntax check
python3 -m py_compile scripts/dashboard_notifier.py

# 2. Dry-run (safe, doesn't send anywhere)
python3 scripts/dashboard_notifier.py --dry-run

# 3. Console mode (shows output even when all green)
python3 scripts/dashboard_notifier.py --console

# 4. Verify exit code (non-zero = red findings)
python3 scripts/dashboard_notifier.py --dry-run; echo "exit=$?"

# 5. Mission Control output (dry-run)
python3 scripts/dashboard_notifier.py --dry-run --to-mission-control

# 6. Heartbeat test
DASHBOARD_HEARTBEAT_HOURS=0.0001 \
  python3 scripts/dashboard_notifier.py --console --dry-run
```
