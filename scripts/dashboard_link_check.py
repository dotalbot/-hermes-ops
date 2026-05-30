#!/usr/bin/env python3
"""Deterministic no-agent dashboard link watchdog.

Stdout contract for Hermes no_agent cron:
- empty stdout: no actionable change, deliver nothing
- non-empty stdout: deliver this fixed alert/recovery/digest text verbatim
- non-zero exit: scheduler delivers an error alert
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(os.environ.get(
    "DASHBOARD_LINK_CHECK_CONFIG",
    "/home/jellybot/hermes-ops/config/dashboard-links.json",
))
DEFAULT_STATE = Path(os.environ.get(
    "DASHBOARD_LINK_CHECK_STATE",
    "/home/jellybot/.hermes/state/dashboard_link_check_state.json",
))
DEFAULT_LOCK = Path(os.environ.get(
    "DASHBOARD_LINK_CHECK_LOCK",
    "/home/jellybot/.hermes/state/dashboard_link_check.lock",
))
DEFAULT_LOG = Path(os.environ.get(
    "DASHBOARD_LINK_CHECK_LOG",
    "/home/jellybot/.hermes/logs/dashboard_link_check.log",
))
DEFAULT_USER_AGENT = "HermesDashboardLinkCheck/1.0 (+no-agent-cron)"
MAX_ALERT_LINES = 20
LOCK_STALE_SECONDS = 300


@dataclass
class CheckResult:
    label: str
    url: str
    ok: bool
    status: int | None = None
    latency_ms: int | None = None
    content_type: str | None = None
    error: str | None = None
    expected: str | None = None
    attempts: int = 1


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    try:
        DEFAULT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DEFAULT_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{utc_now()} {message}\n")
    except Exception:
        # Logging must never turn a good watchdog tick into noise.
        pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"config not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON config {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"config root must be an object: {path}")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def status_matches(status: int | None, expected: dict[str, Any]) -> bool:
    if status is None:
        return False
    if "status" in expected:
        return status == int(expected["status"])
    status_class = str(expected.get("status_class", "2xx"))
    if len(status_class) == 3 and status_class.endswith("xx") and status_class[0].isdigit():
        low = int(status_class[0]) * 100
        return low <= status < low + 100
    if "status_min" in expected or "status_max" in expected:
        return int(expected.get("status_min", 100)) <= status <= int(expected.get("status_max", 599))
    return 200 <= status <= 299


def expected_label(expected: dict[str, Any]) -> str:
    if "status" in expected:
        return f"status {expected['status']}"
    if "status_class" in expected:
        return f"status {expected['status_class']}"
    if "status_min" in expected or "status_max" in expected:
        return f"status {expected.get('status_min', 100)}-{expected.get('status_max', 599)}"
    return "status 2xx"


def fetch(url: str, timeout: float, method: str, user_agent: str) -> tuple[int | None, str | None, str | None, int]:
    start = time.monotonic()
    req = urllib.request.Request(url, method=method, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = b""
            # Only read a bounded prefix, enough for expected_text checks.
            if method != "HEAD":
                body = resp.read(512_000)
            latency_ms = int((time.monotonic() - start) * 1000)
            content_type = resp.headers.get("Content-Type")
            return resp.status, body.decode("utf-8", errors="replace"), content_type, latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        body = ""
        try:
            if method != "HEAD":
                body = exc.read(64_000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return exc.code, body, exc.headers.get("Content-Type") if exc.headers else None, latency_ms
    except Exception as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}")


def run_one(item: dict[str, Any], defaults: dict[str, Any]) -> CheckResult:
    label = str(item.get("label") or item.get("url") or "unnamed")
    url = str(item.get("url") or "")
    if not (url.startswith("http://") or url.startswith("https://")):
        return CheckResult(label, url, False, error="config error: url must start with http:// or https://")

    timeout = float(item.get("timeout_seconds", defaults.get("timeout_seconds", 3)))
    retries = int(item.get("retries", defaults.get("retries", 1)))
    method = str(item.get("method", defaults.get("method", "GET"))).upper()
    if method not in {"GET", "HEAD"}:
        return CheckResult(label, url, False, error=f"config error: unsupported method {method}")
    user_agent = str(defaults.get("user_agent", DEFAULT_USER_AGENT))
    expected = item.get("expected", {})
    if not isinstance(expected, dict):
        expected = {}
    want_text = expected.get("text_contains")

    last: CheckResult | None = None
    for attempt in range(1, retries + 2):
        try:
            status, body, content_type, latency_ms = fetch(url, timeout, method, user_agent)
            ok = status_matches(status, expected)
            if ok and want_text:
                ok = str(want_text) in (body or "")
            if ok:
                return CheckResult(label, url, True, status, latency_ms, content_type, expected=expected_label(expected), attempts=attempt)
            problem = f"expected {expected_label(expected)}"
            if want_text and str(want_text) not in (body or ""):
                problem += f" and text {want_text!r}"
            last = CheckResult(label, url, False, status, latency_ms, content_type, error=problem, expected=expected_label(expected), attempts=attempt)
        except Exception as exc:
            last = CheckResult(label, url, False, error=str(exc), expected=expected_label(expected), attempts=attempt)
        if attempt <= retries:
            time.sleep(float(defaults.get("retry_delay_seconds", 0.5)))
    return last or CheckResult(label, url, False, error="unknown failure", expected=expected_label(expected), attempts=1)


def fingerprint(results: list[CheckResult]) -> str:
    failures = [
        {
            "label": r.label,
            "url": r.url,
            "status": r.status,
            "error": r.error,
            "expected": r.expected,
        }
        for r in results
        if not r.ok
    ]
    blob = json.dumps(failures, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest() if failures else "ok"


def render_alert(results: list[CheckResult], recovered: bool = False) -> str:
    failed = [r for r in results if not r.ok]
    if recovered:
        return "Dashboard link check recovered: all configured dashboard links now pass."
    lines = ["Dashboard link check failed:"]
    for r in failed[:MAX_ALERT_LINES]:
        actual = f"status {r.status}" if r.status is not None else "no response"
        detail = r.error or "failed"
        lines.append(f"- {r.label}: expected {r.expected or 'status 2xx'}, got {actual}; {detail}; attempts={r.attempts}; url={r.url}")
    if len(failed) > MAX_ALERT_LINES:
        lines.append(f"- ...and {len(failed) - MAX_ALERT_LINES} more failures")
    return "\n".join(lines)


def render_digest(results: list[CheckResult], config_path: Path) -> str:
    failed = [r for r in results if not r.ok]
    lines = [
        "Dashboard link check digest:",
        f"- checked: {len(results)}",
        f"- passed: {len(results) - len(failed)}",
        f"- failed: {len(failed)}",
        f"- config: {config_path}",
    ]
    for r in results:
        state = "ok" if r.ok else "FAIL"
        actual = f"status {r.status}" if r.status is not None else "no response"
        latency = f", {r.latency_ms}ms" if r.latency_ms is not None else ""
        extra = f" ({r.error})" if r.error and not r.ok else ""
        lines.append(f"- {state}: {r.label} -> {actual}{latency}{extra}")
    return "\n".join(lines)


class Lock:
    def __init__(self, path: Path):
        self.path = path
        self.acquired = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        try:
            if self.path.exists() and now - self.path.stat().st_mtime > LOCK_STALE_SECONDS:
                self.path.unlink()
        except FileNotFoundError:
            pass
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            self.acquired = True
        except FileExistsError:
            # Overlapping cron tick: quiet success, no delivery.
            raise SystemExit(0)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="No-agent dashboard link watchdog")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--digest", action="store_true", help="always print a status digest")
    parser.add_argument("--no-state", action="store_true", help="do not suppress repeated identical alerts")
    args = parser.parse_args()

    digest = args.digest or os.environ.get("DASHBOARD_LINK_CHECK_DIGEST") == "1"
    config = read_json(args.config)
    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    links = config.get("links", [])
    if not isinstance(links, list) or not links:
        raise SystemExit("config must contain a non-empty links array")
    bad_link_indexes = [str(i) for i, item in enumerate(links) if not isinstance(item, dict)]
    if bad_link_indexes:
        raise SystemExit(f"links entries must be objects; bad index(es): {', '.join(bad_link_indexes)}")

    with Lock(args.lock):
        results = [run_one(item, defaults) for item in links]
        fp = fingerprint(results)
        state: dict[str, Any] = {}
        if args.state.exists():
            try:
                state = read_json(args.state)
            except SystemExit:
                state = {}

        if digest:
            print(render_digest(results, args.config))
        else:
            previous = state.get("last_fingerprint")
            if fp != "ok" and (args.no_state or previous != fp):
                print(render_alert(results))
            elif fp == "ok" and previous and previous != "ok":
                print(render_alert(results, recovered=True))

            write_json_atomic(args.state, {
                "last_checked_at": utc_now(),
                "last_fingerprint": fp,
                "checked": len(results),
                "failed": len([r for r in results if not r.ok]),
            })
        log(f"checked={len(results)} failed={len([r for r in results if not r.ok])} fingerprint={fp[:12]} digest={int(digest)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"dashboard_link_check fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
