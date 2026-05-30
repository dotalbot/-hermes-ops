#!/usr/bin/env bash
# Runtime wrapper for Hermes no-agent cron.
# Source of truth: /home/jellybot/hermes-ops/scripts/dashboard_health_notifier_cron.sh
# Active profile install path:
#   /home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh
# Default profile install path, if recreated there:
#   /home/jellybot/.hermes/scripts/dashboard_health_notifier_cron.sh
set -euo pipefail

REPO="${DASHBOARD_HEALTH_REPO:-/home/jellybot/hermes-ops}"
INVENTORY="${DASHBOARD_INVENTORY:-$REPO/config/dashboard-inventory.json}"

cd "$REPO"
exec python3 "$REPO/scripts/dashboard_notifier.py" --inventory "$INVENTORY" "$@"
