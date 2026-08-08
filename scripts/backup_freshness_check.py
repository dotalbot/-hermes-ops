#!/usr/bin/env python3
"""Deterministic backup freshness checker.

Reads real backup metadata/output instead of assuming success from schedules:
- Hermes GitHub backup cron job JSON + captured backup output.
- Borg/Borgmatic central Prometheus metrics, with a local status JSON fallback.

Exit codes:
  0: every component is green
  1: at least one component is yellow/red
  2: bad CLI/configuration error
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import socket
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

GREEN = "green"
YELLOW = "yellow"
RED = "red"

DEFAULT_HERMES_JOBS = Path("/home/jellybot/.hermes/cron/jobs.json")
DEFAULT_HERMES_JOB_ID = "e5448d934cf9"
DEFAULT_HERMES_OUTPUT_DIR = Path("/home/jellybot/.hermes/cron/output/e5448d934cf9")
DEFAULT_PROMETHEUS_URL = "http://jellybase:9090/api/v1/query"
DEFAULT_BORG_HOSTS = ("jellyhome", "jellybase", "jellyberry")
DEFAULT_LOCAL_BORG_STATUS = Path("/var/lib/home-network/backup-status")
USER_AGENT = "HermesBackupFreshnessCheck/1.0 (+deterministic-check)"


@dataclass
class BackupStatus:
    component: str
    last_successful_backup_time: str | None
    age_seconds: int | None
    age_human: str | None
    status: str
    evidence: str
    source: str
    next_action: str


def parse_timestamp(value: str | int | float | None) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def age_parts(last_time: dt.datetime | None, now: dt.datetime) -> tuple[int | None, str | None]:
    if last_time is None:
        return None, None
    seconds = int((now - last_time).total_seconds())
    if seconds < 0:
        return seconds, "in the future"
    days, rem = divmod(seconds, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, _ = divmod(rem, 60)
    if days:
        return seconds, f"{days}d {hours}h"
    if hours:
        return seconds, f"{hours}h {minutes}m"
    return seconds, f"{minutes}m"


def classify_age(age_seconds: int | None, warn_hours: float, red_hours: float) -> str:
    if age_seconds is None:
        return RED
    if age_seconds < 0:
        return YELLOW
    hours = age_seconds / 3600
    if hours >= red_hours:
        return RED
    if hours >= warn_hours:
        return YELLOW
    return GREEN


def worst_status(*statuses: str) -> str:
    if RED in statuses:
        return RED
    if YELLOW in statuses:
        return YELLOW
    return GREEN


def load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing file: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"JSON root must be object: {path}"
    return data, None


def latest_restore_evidence(output_dir: Path) -> tuple[str | None, str | None, str | None]:
    """Return (timestamp, evidence_line, source_file) for newest restore-test-ok output."""
    newest: tuple[float, str, str, str] | None = None
    for filename in glob.glob(str(output_dir / "*.md")):
        path = Path(filename)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            mtime = path.stat().st_mtime
        except OSError:
            continue
        for line in reversed([line.strip() for line in text.splitlines() if line.strip()]):
            if "restore test: ok" in line:
                time_match = re.search(r" at (\d{4}-\d{2}-\d{2}T[^\s]+)", line)
                backup_time = time_match.group(1) if time_match else None
                candidate = (mtime, backup_time or "", line, str(path))
                if newest is None or candidate[0] > newest[0]:
                    newest = candidate
                break
    if newest is None:
        return None, None, None
    return newest[1] or None, newest[2], newest[3]


def check_hermes(args: argparse.Namespace, now: dt.datetime) -> BackupStatus:
    data, error = load_json_file(args.hermes_jobs)
    source = str(args.hermes_jobs)
    if error:
        return BackupStatus(
            component="Hermes GitHub backup",
            last_successful_backup_time=None,
            age_seconds=None,
            age_human=None,
            status=RED,
            evidence=error,
            source=source,
            next_action="Restore or regenerate the Hermes cron jobs file; verify the daily backup job still exists.",
        )
    assert data is not None

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        return BackupStatus(
            component="Hermes GitHub backup",
            last_successful_backup_time=None,
            age_seconds=None,
            age_human=None,
            status=RED,
            evidence="jobs.json does not contain a jobs list",
            source=source,
            next_action="Inspect the Hermes cron state file format before relying on backup status.",
        )
    job = next((item for item in jobs if isinstance(item, dict) and item.get("id") == args.hermes_job_id), None)
    if not job:
        return BackupStatus(
            component="Hermes GitHub backup",
            last_successful_backup_time=None,
            age_seconds=None,
            age_human=None,
            status=RED,
            evidence=f"job id {args.hermes_job_id} not found",
            source=source,
            next_action="Find the current daily Hermes backup cron job id or recreate the job.",
        )

    problems: list[str] = []
    if not job.get("enabled", False):
        problems.append("job disabled")
    if str(job.get("state", "")).lower() not in {"scheduled", "running"}:
        problems.append(f"unexpected state={job.get('state')!r}")
    if job.get("last_status") != "ok":
        problems.append(f"last_status={job.get('last_status')!r}")
    if job.get("last_error"):
        problems.append(f"last_error={job.get('last_error')!r}")

    last_run = parse_timestamp(job.get("last_run_at"))
    age_seconds, age_human = age_parts(last_run, now)
    age_status = classify_age(age_seconds, args.warn_hours, args.red_hours)
    restore_time, restore_line, restore_source = latest_restore_evidence(args.hermes_output_dir)
    restore_status = GREEN if restore_line else YELLOW
    base_status = RED if problems else GREEN
    status = worst_status(base_status, age_status, restore_status)

    evidence_parts = [
        f"job={job.get('name', args.hermes_job_id)}",
        f"enabled={job.get('enabled')}",
        f"state={job.get('state')}",
        f"last_status={job.get('last_status')}",
        f"last_run_at={job.get('last_run_at')}",
    ]
    if restore_line:
        evidence_parts.append(f"restore_evidence={restore_line}")
    else:
        evidence_parts.append(f"restore_evidence=missing in {args.hermes_output_dir}")
    if problems:
        evidence_parts.append("problems=" + "; ".join(problems))

    if status == GREEN:
        next_action = "No action; scheduler reports success and latest run is fresh."
    elif problems:
        next_action = "Inspect the latest Hermes backup cron output and fix the reported job/script failure before the next 03:00 run."
    elif age_status != GREEN:
        next_action = "Run the Hermes backup status helper, then inspect/restart the daily cron job if no fresh run appears."
    else:
        next_action = "Run /home/jellybot/.hermes/scripts/check_backup_status.sh and inspect cron output for restore-test evidence."

    return BackupStatus(
        component="Hermes GitHub backup",
        last_successful_backup_time=last_run.isoformat() if last_run and not problems else None,
        age_seconds=age_seconds,
        age_human=age_human,
        status=status,
        evidence="; ".join(evidence_parts),
        source=f"{source}; {restore_source or args.hermes_output_dir}",
        next_action=next_action,
    )


def prometheus_query(url: str, query: str, timeout: float) -> dict[str, Any]:
    full_url = url + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed for {query}: {payload}")
    return payload


def prom_vector_by_host(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    result = payload.get("data", {}).get("result", [])
    if not isinstance(result, list):
        return out
    for item in result:
        if not isinstance(item, dict):
            continue
        metric = item.get("metric", {})
        value = item.get("value", [])
        host = metric.get("host") if isinstance(metric, dict) else None
        if not host or not isinstance(value, list) or len(value) < 2:
            continue
        out[str(host)] = {"metric": metric, "value": value[1]}
    return out


def check_borg_from_prometheus(args: argparse.Namespace, now: dt.datetime) -> list[BackupStatus]:
    ts_payload = prometheus_query(args.prometheus_url, "borgmatic_last_run_timestamp_seconds", args.timeout)
    success_payload = prometheus_query(args.prometheus_url, "borgmatic_last_run_success", args.timeout)
    reachable_payload = prometheus_query(args.prometheus_url, "borgmatic_repository_reachable", args.timeout)
    archive_payload = prometheus_query(args.prometheus_url, "borgmatic_last_archive_info", args.timeout)

    timestamps = prom_vector_by_host(ts_payload)
    successes = prom_vector_by_host(success_payload)
    reachables = prom_vector_by_host(reachable_payload)
    archives = prom_vector_by_host(archive_payload)
    results: list[BackupStatus] = []
    for host in args.borg_hosts:
        ts_entry = timestamps.get(host)
        if not ts_entry:
            results.append(BackupStatus(
                component=f"Borgmatic backup ({host})",
                last_successful_backup_time=None,
                age_seconds=None,
                age_human=None,
                status=RED,
                evidence=f"missing borgmatic_last_run_timestamp_seconds for host={host}",
                source=args.prometheus_url,
                next_action=f"Check node_exporter/textfile collector and Borgmatic wrapper on {host}; Prometheus has no timestamp metric.",
            ))
            continue
        last_time = parse_timestamp(float(ts_entry["value"]))
        age_seconds, age_human = age_parts(last_time, now)
        age_status = classify_age(age_seconds, args.warn_hours, args.red_hours)
        success_value = float(successes.get(host, {}).get("value", "nan")) if host in successes else float("nan")
        reachable_value = float(reachables.get(host, {}).get("value", "nan")) if host in reachables else float("nan")
        problems: list[str] = []
        if success_value != 1.0:
            problems.append(f"borgmatic_last_run_success={success_value}")
        if reachable_value != 1.0:
            problems.append(f"borgmatic_repository_reachable={reachable_value}")
        archive_name = archives.get(host, {}).get("metric", {}).get("archive_name") if host in archives else None
        status = worst_status(RED if problems else GREEN, age_status)
        if status == GREEN:
            next_action = "No action; Prometheus reports a fresh successful Borgmatic run and reachable repository."
        elif problems:
            next_action = f"Inspect /var/lib/home-network/backup-status/{host}.json and the latest /var/log/home-network-borgmatic log on {host}."
        else:
            next_action = f"Check the {host} Borgmatic timer/service and wrapper output; success metric is present but timestamp is stale."
        evidence = (
            f"timestamp={ts_entry['value']}; success={success_value}; "
            f"repository_reachable={reachable_value}; archive={archive_name or 'unknown'}"
        )
        results.append(BackupStatus(
            component=f"Borgmatic backup ({host})",
            last_successful_backup_time=last_time.isoformat() if last_time and success_value == 1.0 else None,
            age_seconds=age_seconds,
            age_human=age_human,
            status=status,
            evidence=evidence,
            source=args.prometheus_url,
            next_action=next_action,
        ))
    return results


def check_local_borg_status(args: argparse.Namespace, now: dt.datetime, reason: str) -> list[BackupStatus]:
    host = socket.gethostname().split(".")[0]
    path = args.local_borg_status_dir / f"{host}.json"
    data, error = load_json_file(path)
    if error:
        return [BackupStatus(
            component=f"Borgmatic backup ({host}, local fallback)",
            last_successful_backup_time=None,
            age_seconds=None,
            age_human=None,
            status=RED,
            evidence=f"Prometheus unavailable ({reason}); {error}",
            source=f"{args.prometheus_url}; {path}",
            next_action="Restore Prometheus access or verify the local Borgmatic status JSON path/wrapper on this host.",
        )]
    assert data is not None
    last_time = parse_timestamp(data.get("updated_at"))
    age_seconds, age_human = age_parts(last_time, now)
    age_status = classify_age(age_seconds, args.warn_hours, args.red_hours)
    problems: list[str] = []
    if data.get("status") != "success":
        problems.append(f"status={data.get('status')!r}")
    if data.get("exit_code") != 0:
        problems.append(f"exit_code={data.get('exit_code')!r}")
    if data.get("repository_reachable") is not True:
        problems.append(f"repository_reachable={data.get('repository_reachable')!r}")
    status = worst_status(RED if problems else GREEN, age_status)
    return [BackupStatus(
        component=f"Borgmatic backup ({host}, local fallback)",
        last_successful_backup_time=last_time.isoformat() if last_time and not problems else None,
        age_seconds=age_seconds,
        age_human=age_human,
        status=status,
        evidence=(
            f"Prometheus unavailable ({reason}); status={data.get('status')}; "
            f"exit_code={data.get('exit_code')}; repository_reachable={data.get('repository_reachable')}; "
            f"archive={data.get('archive_name')}"
        ),
        source=str(path),
        next_action=(
            "No action for local host; restore central Prometheus visibility for cross-host status."
            if status == GREEN else
            "Inspect the local Borgmatic status JSON message/log and repair the wrapper or repository connectivity."
        ),
    )]


def check_borg(args: argparse.Namespace, now: dt.datetime) -> list[BackupStatus]:
    try:
        return check_borg_from_prometheus(args, now)
    except Exception as exc:
        central_failure = BackupStatus(
            component="Borgmatic backups (Prometheus)",
            last_successful_backup_time=None,
            age_seconds=None,
            age_human=None,
            status=RED,
            evidence=f"Prometheus query failed: {type(exc).__name__}: {exc}",
            source=args.prometheus_url,
            next_action="Restore Prometheus access or run on a host that can reach jellybase:9090; local fallback only proves the current host.",
        )
        if args.no_local_fallback:
            return [central_failure]
        return [central_failure, *check_local_borg_status(args, now, f"{type(exc).__name__}: {exc}")]


def print_text(results: list[BackupStatus]) -> None:
    print("Backup freshness status")
    print("=======================")
    for item in results:
        print(f"- component: {item.component}")
        print(f"  status: {item.status}")
        print(f"  last_successful_backup_time: {item.last_successful_backup_time or 'unknown'}")
        print(f"  age: {item.age_human or 'unknown'}")
        print(f"  source: {item.source}")
        print(f"  evidence: {item.evidence}")
        print(f"  next_action: {item.next_action}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check freshness of Hermes and Borg/Borgmatic backups using real metadata.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text.")
    parser.add_argument("--warn-hours", type=float, default=26.0, help="Age at or above this threshold is yellow. Default: 26.")
    parser.add_argument("--red-hours", type=float, default=48.0, help="Age at or above this threshold is red. Default: 48.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout for Prometheus queries. Default: 5 seconds.")
    parser.add_argument("--now", help="Override current time for tests, ISO-8601.")
    parser.add_argument("--hermes-jobs", type=Path, default=DEFAULT_HERMES_JOBS)
    parser.add_argument("--hermes-job-id", default=DEFAULT_HERMES_JOB_ID)
    parser.add_argument("--hermes-output-dir", type=Path, default=DEFAULT_HERMES_OUTPUT_DIR)
    parser.add_argument("--prometheus-url", default=os.environ.get("BACKUP_FRESHNESS_PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL))
    parser.add_argument("--borg-hosts", nargs="+", default=list(DEFAULT_BORG_HOSTS), help="Expected Borgmatic hosts in Prometheus metrics.")
    parser.add_argument("--local-borg-status-dir", type=Path, default=DEFAULT_LOCAL_BORG_STATUS)
    parser.add_argument("--no-local-fallback", action="store_true", help="Return a Prometheus-level red result instead of local JSON fallback.")
    args = parser.parse_args(argv)
    if args.warn_hours < 0 or args.red_hours <= 0 or args.warn_hours > args.red_hours:
        parser.error("thresholds must satisfy 0 <= warn-hours <= red-hours")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    now = parse_timestamp(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    if now is None:
        print(f"[FATAL] invalid --now timestamp: {args.now}", file=sys.stderr)
        return 2

    results = [check_hermes(args, now), *check_borg(args, now)]
    payload = {
        "generated_at": now.isoformat(),
        "summary_status": worst_status(*(item.status for item in results)),
        "results": [asdict(item) for item in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_text(results)
        print(f"\nsummary_status: {payload['summary_status']}")
    return 0 if payload["summary_status"] == GREEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
