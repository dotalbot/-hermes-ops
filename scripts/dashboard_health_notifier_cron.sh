#!/usr/bin/env bash
# Runtime wrapper for Hermes no-agent cron (homenetworkworker profile).
# Source of truth: /home/jellybot/dev_projects/hermes-ops/scripts/dashboard_health_notifier_cron.sh
# Runtime install: /home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh
# To refresh after editing the source of truth:
#   install -m 0755 /home/jellybot/dev_projects/hermes-ops/scripts/dashboard_health_notifier_cron.sh \
#     /home/jellybot/.hermes/profiles/homenetworkworker/scripts/dashboard_health_notifier_cron.sh
set -euo pipefail

REPO="${DASHBOARD_HEALTH_REPO:-/home/jellybot/dev_projects/hermes-ops}"
INVENTORY="${DASHBOARD_INVENTORY:-$REPO/config/dashboard-inventory.json}"

cd "$REPO"
exec python3 "$REPO/scripts/dashboard_notifier.py" --inventory "$INVENTORY" "$@"
