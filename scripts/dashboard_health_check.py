#!/usr/bin/env python3
"""Deterministic dashboard health checker.

Consumes config/dashboard-inventory.json and validates all dashboard/Homepage
endpoints.  Per-check green/red output; non-zero exit on any required failure.

Stdout contract (consistent with no-agent cron):
  - Produces structured per-check output + summary.
  - Non-zero exit on any required check that fails.
  - No noisy stack traces for expected skips or non-HTTP entries.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]
    print("[WARN] PyYAML not installed; Homepage coverage comparison skipped", file=sys.stderr)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_INVENTORY = Path(
    os.environ.get(
        "DASHBOARD_INVENTORY",
        "/home/jellybot/dev_projects/hermes-ops/config/dashboard-inventory.json",
    )
)
USER_AGENT = "HermesDashboardHealthCheck/1.0 (+deterministic-cron)"

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------
GREEN = "GREEN"
RED = "RED"
SKIP = "SKIP"


@dataclass
class CheckOutcome:
    check_type: str          # http / port / asset / coverage
    entry_id: str
    display_name: str
    status: str              # GREEN / RED / SKIP
    detail: str = ""
    latency_ms: int | None = None
    expected: str = ""
    actual: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[FATAL] inventory not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"[FATAL] invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"[FATAL] inventory root must be a dict: {path}", file=sys.stderr)
        sys.exit(2)
    return data


def load_yaml_safe(path: Path) -> list[dict[str, Any]] | None:
    """Load YAML; return None if unavailable or missing."""
    if yaml is None:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as exc:
        print(f"[WARN] failed to parse {path}: {exc}", file=sys.stderr)
        return None


def tcp_reachable(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    """Check TCP connectivity to host:port."""
    try:
        # Resolve the address family (IPv4 or IPv6)
        fam = socket.AF_INET
        if ":" in host:  # bare IPv6
            fam = socket.AF_INET6
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=timeout, source_address=None) as sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            elapsed = int((time.monotonic() - start) * 1000)
            return True, f"connected in {elapsed}ms"
    except socket.timeout:
        return False, f"connection timeout after {timeout}s"
    except socket.error as exc:
        return False, str(exc)


def status_matches(status: int | None, expected: dict[str, Any]) -> bool:
    """Check if an HTTP status code matches the expected spec.

    Supports: exact ``status``, ``status_class`` (e.g. ``2xx``),
    ``status_min`` / ``status_max`` ranges, and ``allowed_status_classes``
    (list of class strings like ``["2xx", "3xx"]``).
    """
    if status is None:
        return False
    if "status" in expected:
        return status == int(expected["status"])
    if "allowed_status_classes" in expected:
        classes = expected["allowed_status_classes"]
        if isinstance(classes, list):
            for sc in classes:
                if status_class_match(status, str(sc)):
                    return True
            return False
    if "status_class" in expected:
        if expected["status_class"] == "2xx_or_3xx_or_auth":
            return status_class_match(status, "2xx") or status_class_match(status, "3xx") or status == 401
        return status_class_match(status, str(expected["status_class"]))
    if "status_min" in expected or "status_max" in expected:
        lo = int(expected.get("status_min", 100))
        hi = int(expected.get("status_max", 599))
        return lo <= status <= hi
    return 200 <= status <= 299


def status_class_match(status: int, cls: str) -> bool:
    """True if *status* falls in a ``Nxx`` class string."""
    if len(cls) == 3 and cls.endswith("xx") and cls[0].isdigit():
        lo = int(cls[0]) * 100
        return lo <= status < lo + 100
    return False


def expected_label(expected: dict[str, Any]) -> str:
    """Human-readable description of what was expected."""
    if "status" in expected:
        return f"status {expected['status']}"
    if "allowed_status_classes" in expected:
        return f"status in {expected['allowed_status_classes']}"
    if "status_class" in expected:
        return f"status {expected['status_class']}"
    if "status_min" in expected or "status_max" in expected:
        return f"status {expected.get('status_min', 100)}-{expected.get('status_max', 599)}"
    return "status 2xx"


def http_fetch(
    url: str,
    timeout: float,
    method: str = "GET",
) -> tuple[int | None, str | None, int]:
    """GET a URL and return (status, body, latency_ms).

    Does NOT raise on HTTP errors; returns the error code and body instead.
    Raises RuntimeError on transport-level failures.
    """
    start = time.monotonic()
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512_000).decode("utf-8", errors="replace")
            latency = int((time.monotonic() - start) * 1000)
            return resp.status, body, latency
    except urllib.error.HTTPError as exc:
        latency = int((time.monotonic() - start) * 1000)
        body = ""
        try:
            body = exc.read(64_000).decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, body, latency
    except Exception as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------

def check_http_entry(entry: dict[str, Any], defaults: dict[str, Any]) -> CheckOutcome:
    """Run HTTP check for one inventory entry."""
    eid: str = entry.get("id", "?")
    name: str = entry.get("display_name", eid)
    url: str = entry.get("url", "")
    expected: dict[str, Any] | None = entry.get("expected_http")
    req: bool = entry.get("required", True)

    if not (url.startswith("http://") or url.startswith("https://")):
        return CheckOutcome("http", eid, name, SKIP, detail="non-HTTP scheme")
    if expected is None:
        return CheckOutcome("http", eid, name, SKIP, detail="no expected_http configured")

    timeout = float(entry.get("timeout_seconds", defaults.get("timeout_seconds", 3)))
    retries = int(entry.get("retries", defaults.get("retries", 1)))
    retry_delay = float(defaults.get("retry_delay_seconds", 0.5))
    method = str(entry.get("method", defaults.get("method", "GET"))).upper()

    # Apply path_override if present
    check_url = url
    if "path_override" in expected:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        check_url = urlunparse(parsed._replace(path=expected["path_override"]))

    want_text = expected.get("text_contains")

    for attempt in range(1, retries + 2):
        try:
            status, body, latency_ms = http_fetch(check_url, timeout, method)
            ok = status_matches(status, expected)
            if ok and want_text:
                ok = str(want_text) in (body or "")

            lab = expected_label(expected)
            actual = f"status {status}" if status else "no response"

            if ok:
                return CheckOutcome(
                    "http", eid, name, GREEN,
                    detail=f"{actual} ({latency_ms}ms)",
                    latency_ms=latency_ms,
                    expected=lab,
                    actual=actual,
                )
            problem = f"expected {lab}"
            if want_text and str(want_text) not in (body or ""):
                problem += f" with text {want_text!r}"
            outcome = CheckOutcome(
                "http", eid, name, RED if req else SKIP,
                detail=f"{problem}, got {actual}",
                latency_ms=latency_ms,
                expected=lab,
                actual=actual,
            )
            if not req:
                return outcome  # non-required failures are SKIP
            if attempt <= retries:
                time.sleep(retry_delay)
                continue
            return outcome
        except Exception as exc:
            outcome = CheckOutcome(
                "http", eid, name, RED if req else SKIP,
                detail=str(exc),
                expected=expected_label(expected),
            )
            if not req:
                return outcome
            if attempt <= retries:
                time.sleep(retry_delay)
                continue
            return outcome
    return CheckOutcome("http", eid, name, RED if req else SKIP, detail="unknown failure")


def check_service_port(entry: dict[str, Any]) -> CheckOutcome | None:
    """TCP port-reachability check for entries with a service block.

    Skips 127.0.0.1 entries when not the checker host and non-TCP schemes.
    Returns None when the check should be silently skipped.
    """
    eid: str = entry.get("id", "?")
    name: str = entry.get("display_name", eid)
    svc: dict[str, Any] | None = entry.get("service")
    if not svc:
        return None
    host = svc.get("host")
    port = svc.get("port")
    scheme = svc.get("scheme", "http")
    req: bool = entry.get("required", True)

    if not host or not port:
        return None
    if scheme not in ("http", "https", "tcp"):
        # Only TCP-based schemes get port checks
        return None
    if host == "127.0.0.1" and svc.get("runtime_host", "") != "jellyberry":
        return CheckOutcome("port", eid, name, SKIP, detail="host-local endpoint on remote host")

    ok, detail = tcp_reachable(host, int(port))
    status = GREEN if ok else (RED if req else SKIP)
    return CheckOutcome("port", eid, name, status, detail=detail)


def check_plugin_assets(entry: dict[str, Any]) -> list[CheckOutcome]:
    """Verify plugin JS/CSS assets are reachable.

    Reads the plugin-manifest URL to discover plugin bundles, then checks
    each asset.  Accepts 401 for unauthenticated asset access when the
    manifest specifies ``unauthenticated_asset_status``.
    """
    outcomes: list[CheckOutcome] = []
    assets: list[dict[str, Any]] | None = entry.get("assets")
    if not assets:
        return outcomes

    # First, verify the manifest URL itself
    manifest_url: str = entry.get("url", "")
    if not manifest_url:
        return outcomes

    # Try to fetch the manifest
    try:
        status, body, latency = http_fetch(manifest_url, 5.0)
        if status != 200 or not body:
            outcomes.append(CheckOutcome(
                "asset", entry.get("id", "?"), entry.get("display_name", "?"),
                RED,
                detail=f"plugin manifest returned status {status}, cannot verify assets",
            ))
            return outcomes
    except Exception as exc:
        outcomes.append(CheckOutcome(
            "asset", entry.get("id", "?"), entry.get("display_name", "?"),
            RED,
            detail=f"plugin manifest unreachable: {exc}",
        ))
        return outcomes

    # Parse as JSON and look at plugin entries
    try:
        manifest_raw = json.loads(body)
    except json.JSONDecodeError:
        outcomes.append(CheckOutcome(
            "asset", entry.get("id", "?"), entry.get("display_name", "?"),
            RED,
            detail="plugin manifest is not valid JSON",
        ))
        return outcomes

    if isinstance(manifest_raw, dict):
        plugins_list: list[dict[str, Any]] = manifest_raw.get("plugins", [])
    elif isinstance(manifest_raw, list):
        plugins_list = manifest_raw
    else:
        outcomes.append(CheckOutcome(
            "asset", entry.get("id", "?"), entry.get("display_name", "?"),
            RED,
            detail=f"plugin manifest is unexpected type {type(manifest_raw).__name__}",
        ))
        return outcomes
    if not plugins_list:
        outcomes.append(CheckOutcome(
            "asset", entry.get("id", "?"), entry.get("display_name", "?"),
            RED,
            detail="plugin manifest has no plugins array",
        ))
        return outcomes

    # Build lookup of expected plugins
    expected = {a["plugin"]: a for a in assets}

    for plug in plugins_list:
        plug_name: str = plug.get("name", "?")
        spec = expected.get(plug_name)
        if not spec:
            outcomes.append(CheckOutcome(
                "asset", f"{entry.get('id', '?')}/{plug_name}", plug_name,
                GREEN if not spec else RED,
                detail="plugin present in manifest but not in inventory spec",
            ))
            continue

        entry_path = spec.get("entry", "dist/index.js")
        css_path = spec.get("css", "dist/style.css")
        unauthorized_acceptable = spec.get("unauthenticated_asset_status", 401)

        # Check JS entry
        for asset_path, asset_type in [(entry_path, "JS"), (css_path, "CSS")]:
            asset_url = manifest_url.rstrip("/").rsplit("/", 1)[0] + "/" + asset_path
            try:
                astat, _, alatency = http_fetch(asset_url, 5.0)
                if astat == 200 or astat == unauthorized_acceptable:
                    outcomes.append(CheckOutcome(
                        "asset", f"{entry.get('id', '?')}/{plug_name}/{asset_type}", f"{plug_name} {asset_type}",
                        GREEN,
                        detail=f"status {astat} ({alatency}ms)",
                        latency_ms=alatency,
                    ))
                else:
                    outcomes.append(CheckOutcome(
                        "asset", f"{entry.get('id', '?')}/{plug_name}/{asset_type}", f"{plug_name} {asset_type}",
                        RED,
                        detail=f"expected 200 or {unauthorized_acceptable}, got status {astat}",
                    ))
            except Exception as exc:
                outcomes.append(CheckOutcome(
                    "asset", f"{entry.get('id', '?')}/{plug_name}/{asset_type}", f"{plug_name} {asset_type}",
                    RED,
                    detail=str(exc),
                ))

    # Check for inventory-specified plugins missing from manifest
    manifest_names = {p.get("name") for p in plugins_list}
    for spec in assets:
        if spec.get("plugin") not in manifest_names:
            outcomes.append(CheckOutcome(
                "asset", f"{entry.get('id', '?')}/{spec.get('plugin')}", spec.get("plugin", "?"),
                RED,
                detail="specified in inventory but missing from live plugin manifest",
            ))

    return outcomes


def check_homepage_coverage(inventory: dict[str, Any]) -> list[CheckOutcome]:
    """Compare Homepage YAML entries against inventory entries.

    Reads services.yaml and bookmarks.yaml from the inventory's ``sources``
    list, extracts Homepage entry names and URLs, then cross-references
    against inventory entries that originate from Homepage.
    """
    outcomes: list[CheckOutcome] = []
    sources: list[str] = inventory.get("sources", [])
    if not sources:
        return outcomes

    # Collect inventory entries that come from Homepage sources
    homepage_inv: list[dict[str, Any]] = [
        e for e in inventory.get("entries", [])
        if e.get("source") in ("homepage-service", "homepage-bookmark")
    ]

    # Collect Homepage YAML sources
    homepage_yaml_paths = [
        p for p in sources
        if "homepage" in p and (p.endswith(".yaml") or p.endswith(".yml"))
    ]

    all_homepage_urls: set[str] = set()
    homepage_url_to_name: dict[str, str] = {}
    homepage_name_to_url: dict[str, str] = {}

    for yaml_path_str in homepage_yaml_paths:
        yaml_path = Path(yaml_path_str)
        if not yaml_path.exists():
            outcomes.append(CheckOutcome(
                "coverage", f"source:{yaml_path.name}", yaml_path_str,
                SKIP, detail="source file not found on checker host",
            ))
            continue

        data = load_yaml_safe(yaml_path)
        if data is None:
            outcomes.append(CheckOutcome(
                "coverage", f"source:{yaml_path.name}", yaml_path_str,
                SKIP, detail="could not parse",
            ))
            continue

        for cat_block in data:
            if not isinstance(cat_block, dict):
                continue
            for _cat_name, entries in cat_block.items():
                if not isinstance(entries, list):
                    continue
                for entry_block in entries:
                    if not isinstance(entry_block, dict):
                        continue
                    for svc_name, svc_info in entry_block.items():
                        if isinstance(svc_info, dict):
                            href = svc_info.get("href", "")
                        elif isinstance(svc_info, list) and svc_info:
                            # bookmarks.yaml wraps in a list
                            href = svc_info[0].get("href", "") if isinstance(svc_info[0], dict) else ""
                        else:
                            continue
                        all_homepage_urls.add(href)
                        homepage_url_to_name[href] = str(svc_name)
                        homepage_name_to_url[str(svc_name)] = href

    if not all_homepage_urls:
        outcomes.append(CheckOutcome(
            "coverage", "homepage-sources", "Homepage YAML",
            SKIP, detail="no entries found in Homepage YAML sources",
        ))
        return outcomes

    # Cross-reference inventory _homepage_ URL against actual Homepage hrefs
    inv_urls: set[str] = set()
    for e in homepage_inv:
        url = e.get("homepage_href") or e.get("url", "")
        if url:
            inv_urls.add(url)

    # Find Homepage entries not in the inventory
    missing_from_inv = all_homepage_urls - inv_urls
    for url in sorted(missing_from_inv):
        name = homepage_url_to_name.get(url, "?")
        outcomes.append(CheckOutcome(
            "coverage", f"hp-uncovered:{name}", name,
            RED if "://" in url and not url.startswith("mqtt://") and not url.startswith("postgresql://") and not url.startswith("ssh://") else SKIP,
            detail=f"in Homepage YAML but not in inventory: {url}",
        ))

    # Find inventory entries (from Homepage sources) that have no matching Homepage YAML entry
    for e in homepage_inv:
        url = e.get("homepage_href") or e.get("url", "")
        if url and url not in all_homepage_urls:
            outcomes.append(CheckOutcome(
                "coverage", f"inv-orphan:{e['id']}", e.get("display_name", e["id"]),
                SKIP,
                detail=f"in inventory but not found in Homepage YAML (possibly expected if removed or consolidated): {url}",
            ))

    return outcomes


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def render_results(outcomes: list[CheckOutcome]) -> str:
    """Human-readable per-check output."""
    lines: list[str] = []
    # Group by check type
    by_type: dict[str, list[CheckOutcome]] = {}
    for o in outcomes:
        by_type.setdefault(o.check_type, []).append(o)

    for ctype in ["http", "port", "asset", "coverage"]:
        items = by_type.get(ctype, [])
        if not items:
            continue
        label = {"http": "HTTP Checks", "port": "Port Checks", "asset": "Plugin Asset Checks", "coverage": "Homepage Coverage"}.get(ctype, ctype)
        lines.append(f"\n=== {label} ===")
        for o in sorted(items, key=lambda x: x.entry_id):
            sym = {"GREEN": "  OK", "RED": "FAIL", "SKIP": "skip"}.get(o.status, "????")
            latency = f" ({o.latency_ms}ms)" if o.latency_ms is not None else ""
            lines.append(f"  {sym}  {o.display_name}{latency}")
            if o.detail:
                lines.append(f"       {o.detail}")

    # Summary
    total = len(outcomes)
    green = sum(1 for o in outcomes if o.status == GREEN)
    red = sum(1 for o in outcomes if o.status == RED)
    skipped = sum(1 for o in outcomes if o.status == SKIP)
    lines.append(f"\n--- Summary: {total} checks, {green} ok, {red} failed, {skipped} skipped ---")
    if red:
        lines.append("FAILED checks detected — exiting with code 1")
    return "\n".join(lines)


def render_json_results(outcomes: list[CheckOutcome]) -> str:
    """JSON structured output for programmatic consumption."""
    return json.dumps({
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(outcomes),
        "green": sum(1 for o in outcomes if o.status == GREEN),
        "red": sum(1 for o in outcomes if o.status == RED),
        "skipped": sum(1 for o in outcomes if o.status == SKIP),
        "checks": [
            {
                "type": o.check_type,
                "entry_id": o.entry_id,
                "display_name": o.display_name,
                "status": o.status,
                "detail": o.detail,
                "latency_ms": o.latency_ms,
            }
            for o in outcomes
        ],
    }, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic dashboard health checker")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY, help="Path to dashboard-inventory.json")
    parser.add_argument("--json", action="store_true", help="Output structured JSON instead of human-readable")
    parser.add_argument("--no-http", action="store_true", help="Skip HTTP checks (port checks and coverage only)")
    parser.add_argument("--no-port", action="store_true", help="Skip TCP port reachability checks")
    parser.add_argument("--no-coverage", action="store_true", help="Skip Homepage coverage comparison")
    parser.add_argument("--no-assets", action="store_true", help="Skip plugin asset verification")
    args = parser.parse_args()

    inventory = load_json(args.inventory)
    defaults: dict[str, Any] = inventory.get("defaults", {})
    entries: list[dict[str, Any]] = inventory.get("entries", [])
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(entries, list):
        print("[FATAL] inventory must contain an entries array", file=sys.stderr)
        return 2

    outcomes: list[CheckOutcome] = []

    # Validate inventory structure first
    seen_ids: set[str] = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            outcomes.append(CheckOutcome("validation", f"entry[{i}]", f"entry[{i}]", RED, detail="not an object"))
            continue
        eid = e.get("id", f"entry[{i}]")
        if eid in seen_ids:
            outcomes.append(CheckOutcome("validation", eid, eid, RED, detail="duplicate id"))
        seen_ids.add(eid)

    # Run checks per entry
    for e in entries:
        if not isinstance(e, dict):
            continue
        eid: str = e.get("id", "?")
        cm: str = e.get("check_mode", "unknown")
        req: bool = e.get("required", True)

        # ---- HTTP checks ----
        if not args.no_http and cm in ("http", "external_http"):
            outcome = check_http_entry(e, defaults)
            if outcome:
                outcomes.append(outcome)
        elif cm == "skip":
            skip_reason = e.get("acceptable_skip_reason", "check_mode is skip")
            outcomes.append(CheckOutcome(
                "http", eid, e.get("display_name", eid),
                SKIP, detail=skip_reason,
            ))

        # ---- TCP port checks ----
        if not args.no_port:
            port_out = check_service_port(e)
            if port_out:
                outcomes.append(port_out)

        # ---- Plugin asset checks ----
        if not args.no_assets and e.get("assets"):
            outcomes.extend(check_plugin_assets(e))

    # ---- Homepage coverage ----
    if not args.no_coverage:
        outcomes.extend(check_homepage_coverage(inventory))

    # ---- Output ----
    if args.json:
        print(render_json_results(outcomes))
    else:
        print(render_results(outcomes))

    # ---- Exit code ----
    red_count = sum(1 for o in outcomes if o.status == RED)
    return 1 if red_count > 0 else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FATAL] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
