#!/usr/bin/env python3
"""Dashboard health check notifier — wired for no-agent cron delivery.

Wraps scripts/dashboard_health_check.py and formats a concise Discord-ready
notification.  Green runs stay silent (empty stdout -> scheduler suppresses
delivery).  Red runs produce a clear notification with affected entry and
reason.  Also supports direct Discord webhook POST and Mission Control JSON
output for operator dashboards.

Stdout contract (matching no-agent cron):
  - Empty stdout / exit 0 -> silent tick, no delivery.
  - Non-empty stdout -> delivered verbatim to the cron deliver target.
  - Non-zero exit -> error alert from the scheduler.

CLI usage:
  python3 scripts/dashboard_notifier.py
  python3 scripts/dashboard_notifier.py --dry-run     # preview without sending
  python3 scripts/dashboard_notifier.py --console     # always print to stdout
  python3 scripts/dashboard_notifier.py --to-webhook  # POST to DASHBOARD_WEBHOOK_URL
  python3 scripts/dashboard_notifier.py --to-mission-control  # write health file

Env vars (secrets go in ~/.hermes/.env, never hard-coded):
  DASHBOARD_WEBHOOK_URL        Discord webhook URL for --to-webhook
  DASHBOARD_MISSION_CONTROL    Path to write Mission Control JSON (default:
                               /home/jellybot/portfolio-intel/mission-control-v2/data/dashboard-health.json)
  DASHBOARD_HEARTBEAT_HOURS    Optional: send a heartbeat every N hours even
                               when all green (0 = disabled, default)
  DASHBOARD_DRY_RUN            Set to "1" to enable dry-run from env
  DASHBOARD_CONSOLE            Set to "1" to always print to stdout from env
  DASHBOARD_INVENTORY          Override path to dashboard-inventory.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO = HERE.parent  # hermes-ops
DEFAULT_INVENTORY = Path(
    os.environ.get(
        "DASHBOARD_INVENTORY",
        str(REPO / "config" / "dashboard-inventory.json"),
    )
)
DEFAULT_MISSION_CONTROL_OUTPUT = Path(
    os.environ.get(
        "DASHBOARD_MISSION_CONTROL",
        "/home/jellybot/portfolio-intel/mission-control-v2/data/dashboard-health.json",
    )
)
HEARTBEAT_STATE = REPO / "config" / ".dashboard-heartbeat-state.json"

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_red_digest(outcomes: dict[str, Any]) -> str:
    """Build a concise Discord-friendly message listing only RED outcomes.

    Returns markdown suitable for Discord delivery.  Empty list of reds ->
    returns empty string (no output needed for green-only runs).
    """
    checks: list[dict[str, Any]] = outcomes.get("checks", [])
    reds = [c for c in checks if c.get("status") == "RED"]
    if not reds:
        return ""

    ts = outcomes.get(
        "checked_at",
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    total = outcomes.get("total", len(checks))
    green = outcomes.get("green", sum(1 for c in checks if c.get("status") == "GREEN"))

    lines: list[str] = []
    lines.append(f"\u26a0\ufe0f  **Dashboard Health: {len(reds)} failure(s)** \u2014 {ts}")
    lines.append("")

    for r in reds:
        name = r.get("display_name") or r.get("entry_id", "?")
        detail = r.get("detail", "no detail")
        lines.append(f"\u2022 **{name}**")
        lines.append(f"  {detail}")

    lines.append("")
    lines.append(f"--- Summary: {total} checks, {green} ok, {len(reds)} failed ---")
    return "\n".join(lines)


def format_green_digest(outcomes: dict[str, Any]) -> str:
    """Build a concise all-clear message (for console or heartbeat)."""
    checks: list[dict[str, Any]] = outcomes.get("checks", [])
    ts = outcomes.get(
        "checked_at",
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    total = outcomes.get("total", len(checks))
    green = outcomes.get("green", sum(1 for c in checks if c.get("status") == "GREEN"))
    skipped = outcomes.get("skipped", sum(1 for c in checks if c.get("status") == "SKIP"))
    return (
        f"\U0001f7e2  **Dashboard Health: all clear** \u2014 {ts}\n"
        f"   {total} checks, {green} ok, {skipped} skipped"
    )


def format_green_heartbeat(outcomes: dict[str, Any], hours: int) -> str:
    """Build a low-frequency all-green heartbeat message."""
    base = format_green_digest(outcomes)
    return base + f", heartbeat interval {hours}h"


# ---------------------------------------------------------------------------
# Heartbeat tracking
# ---------------------------------------------------------------------------

def _read_heartbeat_state() -> dict[str, Any]:
    try:
        with HEARTBEAT_STATE.open("r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_heartbeat_ts": 0}


def _write_heartbeat_state(state: dict[str, Any]) -> None:
    HEARTBEAT_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT_STATE.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(HEARTBEAT_STATE)


def heartbeat_due(hours: float) -> bool:
    """True if the heartbeat interval has elapsed since last heartbeat."""
    if hours <= 0:
        return False
    state = _read_heartbeat_state()
    last = state.get("last_heartbeat_ts", 0)
    elapsed_h = (time.time() - last) / 3600
    return elapsed_h >= hours


def mark_heartbeat_sent() -> None:
    _write_heartbeat_state({"last_heartbeat_ts": time.time()})


# ---------------------------------------------------------------------------
# Deliverers
# ---------------------------------------------------------------------------

def deliver_webhook(url: str, message: str) -> str | None:
    """POST *message* to a Discord webhook.  Returns error string or None."""
    import urllib.error
    import urllib.request

    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 204):
                return f"webhook returned HTTP {resp.status}"
        return None
    except urllib.error.HTTPError as exc:
        return f"webhook HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        return f"webhook error: {type(exc).__name__}: {exc}"


def deliver_mission_control(
    checks: list[dict[str, Any]],
    output_path: Path,
) -> str | None:
    """Write a dashboard-health.json payload for Mission Control.

    Returns error string or None.
    """
    reds = [c for c in checks if c.get("status") == "RED"]
    greens = [c for c in checks if c.get("status") == "GREEN"]
    skips = [c for c in checks if c.get("status") == "SKIP"]

    health_status = "ok" if not reds else "degraded"

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": health_status,
        "total": len(checks),
        "green": len(greens),
        "red": len(reds),
        "skipped": len(skips),
        "failures": [
            {
                "entry_id": c.get("entry_id", "?"),
                "display_name": c.get("display_name", "?"),
                "detail": c.get("detail", ""),
                "check_type": c.get("type", "unknown"),
            }
            for c in reds
        ],
        "summary": (
            f"{len(reds)} failure(s), {len(greens)} ok, {len(skips)} skipped"
        ),
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = output_path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(output_path)
        return None
    except OSError as exc:
        return f"mission-control write error: {exc}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dashboard health check notifier",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("DASHBOARD_DRY_RUN", "") == "1",
        help="Preview the notification without sending",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        default=os.environ.get("DASHBOARD_CONSOLE", "") == "1",
        help="Always print to stdout, even when all green",
    )
    parser.add_argument(
        "--to-webhook",
        action="store_true",
        help="POST notification to DASHBOARD_WEBHOOK_URL",
    )
    parser.add_argument(
        "--to-mission-control",
        action="store_true",
        help="Write dashboard-health.json for Mission Control",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get("DASHBOARD_WEBHOOK_URL", ""),
        help="Discord webhook URL (or set DASHBOARD_WEBHOOK_URL env var)",
    )
    parser.add_argument(
        "--mission-control-output",
        type=Path,
        default=DEFAULT_MISSION_CONTROL_OUTPUT,
        help=f"Mission Control output path",
    )
    parser.add_argument(
        "--heartbeat-hours",
        type=float,
        default=float(os.environ.get("DASHBOARD_HEARTBEAT_HOURS", "0")),
        help="Send a heartbeat every N hours even when all green (0=disabled)",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help=f"Path to dashboard-inventory.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # ---------------------------------------------------------------
    # 1. Run the checker
    # ---------------------------------------------------------------
    checker = HERE / "dashboard_health_check.py"
    cmd = [sys.executable, str(checker), "--json", "--inventory", str(args.inventory)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        msg = "\u274c  **Dashboard Health: checker timed out**"
        print(msg)
        return 1
    except FileNotFoundError:
        msg = f"\u274c  **Dashboard Health: checker not found at {checker}**"
        print(msg, file=sys.stderr)
        return 1

    if proc.returncode not in (0, 1):
        # Real error (2+), not just failed checks
        err = proc.stderr.strip() or f"exit code {proc.returncode}"
        msg = f"\u274c  **Dashboard Health: checker error**\n  {err}"
        print(msg, file=sys.stderr)
        return proc.returncode

    # Parse checker JSON output
    try:
        outcomes: dict[str, Any] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        msg = f"\u274c  **Dashboard Health: invalid JSON from checker**\n  {proc.stdout[:500]}"
        print(msg, file=sys.stderr)
        return 1

    checks: list[dict[str, Any]] = outcomes.get("checks", [])
    red_count = outcomes.get("red", sum(1 for c in checks if c.get("status") == "RED"))
    total = outcomes.get("total", len(checks))

    # ---------------------------------------------------------------
    # 2. Determine what to send
    # ---------------------------------------------------------------
    send_message: str | None = None
    is_heartbeat = False

    if red_count > 0:
        # Failures -> build failure digest
        send_message = format_red_digest(outcomes)
    elif args.heartbeat_hours > 0 and heartbeat_due(args.heartbeat_hours):
        # All green + heartbeat due -> build heartbeat
        send_message = format_green_heartbeat(outcomes, int(args.heartbeat_hours))
        is_heartbeat = True

    # ---------------------------------------------------------------
    # 3. Deliver
    # ---------------------------------------------------------------
    errors: list[str] = []

    # --- Console output (stdout contract for no-agent cron) ---
    if args.console and not send_message:
        # Console mode: always report, even when all green
        send_message = format_green_digest(outcomes)

    if send_message and (
        args.dry_run or args.console or not (args.to_webhook or args.to_mission_control)
    ):
        print(send_message)

    # --- Discord webhook ---
    if args.to_webhook:
        url = args.webhook_url
        if not url:
            errors.append("DASHBOARD_WEBHOOK_URL not set, cannot send to webhook")
        elif args.dry_run:
            print(f"[dry-run] would POST to webhook ({len(send_message or '')} chars)")
        elif send_message:
            err = deliver_webhook(url, send_message)
            if err:
                errors.append(err)

    # --- Mission Control JSON ---
    if args.to_mission_control:
        output_path = args.mission_control_output
        if args.dry_run:
            print(f"[dry-run] would write to {output_path}")
        else:
            err = deliver_mission_control(checks, output_path)
            if err:
                errors.append(err)

    # ---------------------------------------------------------------
    # 4. Heartbeat state
    # ---------------------------------------------------------------
    if send_message and is_heartbeat:
        mark_heartbeat_sent()
    elif red_count > 0:
        # Reset heartbeat timer on failure so the first all-clear after a fix
        # sends an all-green recovery message, not a heartbeat gate delay
        _write_heartbeat_state({"last_heartbeat_ts": 0})

    # ---------------------------------------------------------------
    # 5. Exit
    # ---------------------------------------------------------------
    if errors:
        for e in errors:
            print(f"[notify-error] {e}", file=sys.stderr)
        if red_count > 0:
            return 1  # Failures that also had delivery errors
        # Delivery errors on green run: still exit 0 so the scheduler
        # doesn't treat it as a broken watchdog
        return 0

    return 1 if red_count > 0 else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FATAL] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
