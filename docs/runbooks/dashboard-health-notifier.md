# Dashboard health notifier

Purpose: wraps `dashboard_health_check.py` to produce concise Discord-ready notifications. Uses the Hermes no-agent cron pattern: red findings produce a digest, while all-green runs are silent by default and do not spam chat.

The notifier is not a separate watchdog. It is a delivery wrapper around the deterministic checker. Schedule the cron wrapper for recurring runs, and use the checker/notifier directly for manual diagnosis.

## Source files

| Path | Purpose |
|---|---|
| `config/dashboard-inventory.json` | Source-of-truth dashboard/Homepage inventory and check contract |
| `scripts/dashboard_health_check.py` | Deterministic checker; emits JSON/text and exits non-zero on required red checks |
| `scripts/dashboard_notifier.py` | Formats checker results for no-agent cron, webhook, or Mission Control output |
| `scripts/dashboard_health_notifier_cron.sh` | Hermes cron runtime wrapper; pins repo and inventory paths |
| `docs/specs/dashboard-health-check-inventory-contract.md` | Inventory field semantics and failure policy |
| `docs/runbooks/dashboard-health-notifier.md` | This operator runbook |

Runtime copy for the installed default-profile Hermes cron job:

| Runtime path | Purpose |
|---|---|
| `/home/jellybot/.hermes/scripts/dashboard_health_notifier_cron.sh` | Script scheduled by Hermes cron (default profile) |
| `/home/jellybot/dev_projects/hermes-ops/config/dashboard-inventory.json` | Inventory read by the runtime wrapper |
| `/home/jellybot/dev_projects/hermes-ops/config/.dashboard-heartbeat-state.json` | Optional heartbeat state, ignored by git |
| `/home/jellybot/.hermes/cron/output/<job_id>/` | Scheduler run records |

To switch to a different profile, copy the wrapper to that profile's `scripts/` dir and recreate the job with `--profile <name>`.

## Manual runs

Run from the repo root:

```bash
cd /home/jellybot/dev_projects/hermes-ops

# Human-readable checker output; non-zero means at least one required red check.
python3 scripts/dashboard_health_check.py

# Machine-readable checker output for scripts.
python3 scripts/dashboard_health_check.py --json

# No-agent stdout contract:
#   all green -> empty stdout, exit 0
#   red       -> digest on stdout, exit 1
python3 scripts/dashboard_notifier.py

# Operator console view; always prints a summary.
python3 scripts/dashboard_notifier.py --console

# Dry-run Mission Control without writing. Add --to-webhook only when DASHBOARD_WEBHOOK_URL is set.
python3 scripts/dashboard_notifier.py --dry-run --to-mission-control

# Runtime wrapper exactly as Hermes cron executes it.
/home/jellybot/dev_projects/hermes-ops/scripts/dashboard_health_notifier_cron.sh
```

Expected exit codes:

| Exit | Meaning | Operator action |
|---:|---|---|
| 0 | All required checks green, or only acceptable skips | No action |
| 1 | One or more required checks red | Read the digest and fix/update the affected entry |
| 2+ | Bad inventory, missing file, malformed JSON, or unexpected checker error | Fix checker/runtime configuration before trusting results |

## Interpreting green/red output

Green means the configured check matched expectations from `config/dashboard-inventory.json`: HTTP status/text, TCP port, asset, or Homepage coverage checks passed for required entries.

Red means the entry is actionable unless `required` is false or the inventory explicitly marks the check as skipped. The digest lists only failed entries, for example:

```text
⚠️  **Dashboard Health: 2 failure(s)** — 2026-05-30T13:57:47Z

• **Loki**
  expected status 2xx, got status 404
• **MQTT Exporter**
  URLError: <urlopen error timed out>

--- Summary: 69 checks, 56 ok, 2 failed ---
```

All-green default notifier runs print nothing. This is intentional: Hermes no-agent cron treats empty stdout as a silent successful tick.

## Scheduled execution

Hermes cron jobs can only execute scripts under the active profile's `scripts/` directory. The cron wrapper is installed at both locations for flexibility:

```bash
# Default profile (scripts dir used by the active gateway/cron daemon)
ls /home/jellybot/.hermes/scripts/dashboard_health_notifier_cron.sh

# Profile-specific copy (for homenetworkworker profile if its scheduler is active)
ls /home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh
```

Installed job (default profile, active gateway scheduler):

| Field | Value |
|---|---|
| Job id | `cfb338cf70ff` |
| Name | `dashboard-health-notifier` |
| Schedule | `every 30m` |
| Mode | `no_agent=true` |
| Script | `dashboard_health_notifier_cron.sh` |
| Delivery | `local` |
| Next run | Auto: see `hermes cron list` |

Equivalent install command:

```bash
hermes cron create "every 30m" \
  --name dashboard-health-notifier \
  --script dashboard_health_notifier_cron.sh \
  --no-agent \
  --deliver local
```

Tool API equivalent:

```python
cronjob(
    action="create",
    name="dashboard-health-notifier",
    schedule="every 30m",
    script="dashboard_health_notifier_cron.sh",
    no_agent=True,
    deliver="local",
    prompt="Deterministic no-agent dashboard health notifier. Empty stdout means all green; non-empty stdout is the fixed failure digest.",
)
```

> Old homenetworkworker profile job `61c428e54b12` was removed (default profile scheduler runs it now).

To recreate under a different profile, first delete the default job, then create with `--profile <name>`.

`local` delivery is a staging/safety setting, not a human alert route. It avoids accidental Discord noise during first rollout while the real inventory still has known red findings. Before relying on this job for production alerting, update the job delivery target to the preferred Discord/Telegram channel or enable `--to-webhook` with `DASHBOARD_WEBHOOK_URL`. Green runs still stay silent; only red digests or scheduler errors are delivered.

Useful scheduler operations:

```bash
hermes cron list
hermes cron run <job_id>
hermes cron pause <job_id>
hermes cron resume <job_id>
hermes cron remove <job_id>
```

## Optional delivery modes

```bash
# POST red digests to Discord webhook; keep the webhook URL in ~/.hermes/.env.
DASHBOARD_WEBHOOK_URL=https://discord.com/api/webhooks/... \
  python3 scripts/dashboard_notifier.py --to-webhook

# Write Mission Control JSON when run manually or from a separate dashboard update job.
python3 scripts/dashboard_notifier.py --to-mission-control

# Low-frequency all-clear heartbeat for humans who want periodic proof of life.
DASHBOARD_HEARTBEAT_HOURS=24 python3 scripts/dashboard_notifier.py
```

Do not hard-code webhook URLs or tokens in the repo.

## Updating dashboard entries

1. Edit `config/dashboard-inventory.json`.
2. Preserve stable `id` values so historical failures remain understandable.
3. Set `source_file`, `service.host`, `service.port`, `service.path`, `runtime_host`, and `network_assumptions` whenever known.
4. Use `expected_http.status`, `status_class`, `allowed_status_classes`, or `text_contains` to describe the real success condition.
5. Mark intentionally informational entries as `required: false` or `check_mode: skip`; do not leave noisy required checks for known-offline experiments.
6. Run:

```bash
python3 -m json.tool config/dashboard-inventory.json >/dev/null
python3 scripts/dashboard_health_check.py --json >/tmp/dashboard-health.json
echo "exit=$?"
python3 scripts/dashboard_notifier.py --console
```

7. If the scheduled runtime copy changed, reinstall it with the `install -m 0755 ...` command above.

## Troubleshooting common failures

### DNS or host resolution

Symptoms: `Name or service not known`, `Temporary failure in name resolution`, or repeated timeout on hostname-only targets.

Checks:

```bash
getent hosts <hostname>
python3 scripts/dashboard_health_check.py --json --inventory config/dashboard-inventory.json
```

Fix: use a stable LAN IP or document the required DNS/Tailscale route in `network_assumptions`.

### Wrong host network

Symptoms: `127.0.0.1` checks fail when run away from jellyberry, or LAN-only services fail from a non-LAN host.

Fix: run the checker on the inventory `network_context.primary_checker_host` (`jellyberry`) or change the entry URL to the reachable LAN/Tailnet address and update `network_assumptions`.

### Stale route or moved service

Symptoms: HTTP `404`, `502`, `503`, or timeout after service migration.

Fix: verify the live service endpoint, update `url`, `service.host`, `service.port`, and Homepage entries together, then rerun the notifier. For Docker-managed services, also check the source-of-truth compose/appdata in `/home/jellybot/dev_projects/home-network`.

### Missing dashboard/plugin assets

Symptoms: manifest check passes but asset checks return `404` or dashboard UI says a plugin script could not load.

Fix: rebuild or reinstall the plugin bundle, hide broken demo plugins if intentional, and ensure `assets[].entry` / `assets[].css` matches the served plugin manifest.

### Closed port

Symptoms: `connection refused`, `No route to host`, or TCP timeout.

Checks:

```bash
python3 - <<'PY'
import socket
socket.create_connection(("127.0.0.1", 8787), timeout=3).close()
print("port reachable")
PY
```

Fix: start/restart the service, fix container port publishing, or update the inventory if the service intentionally moved.

### Scheduler/runtime copy drift

Symptoms: manual repo run works but cron fails with missing inventory or stale behavior.

Fix:

```bash
install -m 0755 /home/jellybot/dev_projects/hermes-ops/scripts/dashboard_health_notifier_cron.sh \
  /home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh
hermes cron run <job_id>
```

Then inspect `/home/jellybot/.hermes/cron/output/<job_id>/`.

## Validation: prove stale/unreachable entries are caught

This validation does not modify the production inventory. It copies the inventory, injects one intentionally unreachable required port check, and confirms the notifier returns red:

```bash
cd /home/jellybot/dev_projects/hermes-ops

tmp=$(mktemp)
python3 - "$tmp" <<'PY'
import json, sys
from pathlib import Path
src = Path("config/dashboard-inventory.json")
dst = Path(sys.argv[1])
data = json.loads(src.read_text())
data.setdefault("entries", []).append({
    "id": "validation-unreachable-port",
    "display_name": "Validation unreachable port",
    "source": "runbook-validation",
    "source_file": "temporary inventory copy",
    "category": "Validation",
    "url": "tcp://127.0.0.1:1",
    "service": {"scheme": "tcp", "host": "127.0.0.1", "port": 1, "runtime_host": "jellyberry"},
    "expected_port": {"reachable": True},
    "required": True,
    "check_mode": "port",
    "network_assumptions": ["Port 1 should be closed on normal hosts; this entry must fail."],
})
dst.write_text(json.dumps(data, indent=2) + "\n")
PY

DASHBOARD_INVENTORY="$tmp" scripts/dashboard_health_notifier_cron.sh; rc=$?
rm -f "$tmp"
test "$rc" -eq 1
```

Expected result: output includes `Validation unreachable port` and the command exits `1`. If it exits `0`, the checker is not catching broken required port entries and the scheduled job should be paused until fixed.

## Verification checklist

Run before changing the schedule or declaring the branch ready:

```bash
bash -n scripts/dashboard_health_notifier_cron.sh
python3 -m py_compile scripts/dashboard_health_check.py scripts/dashboard_notifier.py
python3 scripts/dashboard_notifier.py --console
/home/jellybot/dev_projects/hermes-ops/scripts/dashboard_health_notifier_cron.sh; echo "repo_exit=$?"
/home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh; echo "runtime_exit=$?"
hermes cron status
hermes cron list
git diff --check
```

If the real inventory is currently red, the notifier exits `1`; that is a dashboard health finding, not a wrapper failure.
