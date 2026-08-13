#!/usr/bin/env python3
"""Fail-closed parent-context and authoritative governance timing controls."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import tempfile
import time
from typing import Any, Mapping
from urllib.parse import quote

import jsonschema
import yaml

import managerlib
import reviewctl


CATEGORIES = {"active_execution", "queue_wait", "reviewer_remediation", "operator_delay"}
OUTCOMES = {"PASS", "BLOCK", "TIMEOUT", "WAIT", "CONTINUE"}
_WORK_ITEM_RE = re.compile(r"^[A-Z]+-[0-9]+$")
_STAGE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
CONTROL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MANIFEST = CONTROL_ROOT / "projects" / "jellyssh" / "runtime.yaml"
SCHEMAS = {
    "timing": CONTROL_ROOT / "schemas" / "governance-timing.schema.json",
    "review": CONTROL_ROOT / "schemas" / "governed-review-contract.schema.json",
    "acceptance": CONTROL_ROOT / "schemas" / "governed-acceptance-request.schema.json",
}


class GovernanceError(RuntimeError):
    pass


def _load_schema(kind: str) -> dict[str, Any]:
    path = SCHEMAS[kind]
    try:
        runtime = yaml.safe_load(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
        expected = runtime["review_boundary"]["schema_sha256"][path.name]
        content = path.read_bytes()
        if path.is_symlink() or not path.is_file():
            raise GovernanceError(f"{kind} schema type drift")
        if "sha256:" + hashlib.sha256(content).hexdigest() != expected:
            raise GovernanceError(f"{kind} schema hash drift")
        schema = json.loads(content.decode("utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
    except GovernanceError:
        raise
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError, yaml.YAMLError, jsonschema.SchemaError) as exc:
        raise GovernanceError(f"{kind} schema is unavailable") from exc
    return schema


def _validate_schema(kind: str, value: dict[str, Any]) -> None:
    errors = sorted(
        jsonschema.Draft202012Validator(
            _load_schema(kind), format_checker=jsonschema.FormatChecker()
        ).iter_errors(value),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if errors:
        raise GovernanceError(f"{kind} schema drift: {errors[0].message}")


def _reject_secret_material(value: Any, label: str) -> None:
    try:
        managerlib.reject_secret_material(value, label)
    except managerlib.ManagerError as exc:
        raise GovernanceError(f"{label} contains secret-shaped material") from exc


def _canonical_sha256(value: Any) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _boot_id() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError as exc:
        raise GovernanceError("boot identity is unavailable") from exc
    if not re.fullmatch(r"[0-9a-f-]{36}", value):
        raise GovernanceError("boot identity is invalid")
    return value


def require_parent_context(environ: Mapping[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    if str(env.get("HERMES_DELEGATED_CHILD_CONTEXT", "")).strip():
        raise GovernanceError("Kanban mutation requires a normal parent/operator context")


def _reject_symlink_ancestors(path: Path) -> None:
    for ancestor in (path.parent, *path.parent.parents):
        if ancestor.is_symlink():
            raise GovernanceError("timing path traverses a symlinked directory")


def _validate_path(path: Path, *, must_exist: bool = False) -> Path:
    if not path.is_absolute():
        raise GovernanceError("timing path must be absolute")
    if path.suffix != ".json":
        raise GovernanceError("timing path must end in .json")
    _reject_symlink_ancestors(path)
    if path.is_symlink():
        raise GovernanceError("timing path cannot be a symlink")
    if must_exist and not path.is_file():
        raise GovernanceError("timing ledger is unavailable")
    if path.exists() and not path.is_file():
        raise GovernanceError("timing path must be a regular file")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_ancestors(path)
    if parent.is_symlink() or not parent.is_dir():
        raise GovernanceError("timing directory must be a real directory")
    return path


def _load(path: Path) -> dict[str, Any]:
    path = _validate_path(path, must_exist=True)
    try:
        content = path.read_bytes()
        value = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("timing ledger is invalid") from exc
    if not isinstance(value, dict):
        raise GovernanceError("timing ledger root must be an object")
    return value


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path = _validate_path(path)
    content = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary: Path | None = None
    directory_fd: int | None = None
    committed = False
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        temporary.replace(path)
        committed = True
        # Rename is the publication commit point.  Post-commit durability is
        # best effort: never report failure after PASS bytes are visible.
        try:
            os.fsync(directory_fd)
        except OSError:
            pass
    except OSError as exc:
        raise GovernanceError("timing ledger publication failed") from exc
    finally:
        if directory_fd is not None:
            try:
                os.close(directory_fd)
            except OSError:
                if not committed:
                    raise GovernanceError("timing ledger publication failed")
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _validate_identity(stage: str, category: str, outcome: str | None = None) -> None:
    if not _STAGE_RE.fullmatch(stage):
        raise GovernanceError("stage is invalid")
    if category not in CATEGORIES:
        raise GovernanceError("category is invalid")
    if outcome is not None and outcome not in OUTCOMES:
        raise GovernanceError("outcome is invalid")


def _request_digest(action: str, **values: Any) -> str:
    return _canonical_sha256({"action": action, **values})


def _replay(ledger: dict[str, Any], key: str, digest: str) -> bool:
    if not key or len(key) > 200:
        raise GovernanceError("idempotency key is invalid")
    previous = ledger.get("idempotency", {}).get(key)
    if previous is None:
        return False
    if previous != digest:
        raise GovernanceError("idempotency key conflicts with a different transition")
    return True


def _assert_clock(ledger: dict[str, Any], monotonic_ns: int, boot_id: str) -> None:
    if ledger.get("boot_id") != boot_id:
        raise GovernanceError("cross-boot monotonic transition is forbidden")
    current = ledger.get("current")
    anchor = current.get("started_monotonic_ns") if isinstance(current, dict) else ledger.get("started_monotonic_ns")
    if type(monotonic_ns) is not int or type(anchor) is not int or monotonic_ns < anchor:
        raise GovernanceError("monotonic time moved backwards")


def timing_init(
    path: Path,
    work_item: str,
    stage: str,
    category: str,
    at_utc: str,
    monotonic_ns: int,
    boot_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    _validate_path(path)
    if not _WORK_ITEM_RE.fullmatch(work_item):
        raise GovernanceError("work item is invalid")
    _validate_identity(stage, category)
    if type(monotonic_ns) is not int or monotonic_ns < 0:
        raise GovernanceError("monotonic time is invalid")
    digest = _request_digest(
        "timing-init", path=str(path), work_item=work_item, stage=stage, category=category,
        at_utc=at_utc, monotonic_ns=monotonic_ns, boot_id=boot_id,
    )
    if path.exists():
        ledger = _load(path)
        if _replay(ledger, idempotency_key, digest):
            return ledger
        raise GovernanceError("timing ledger already exists")
    ledger = {
        "schema_version": 1,
        "work_item": work_item,
        "boot_id": boot_id,
        "state": "running",
        "started_at_utc": at_utc,
        "started_monotonic_ns": monotonic_ns,
        "current": {
            "stage": stage,
            "category": category,
            "started_at_utc": at_utc,
            "started_monotonic_ns": monotonic_ns,
        },
        "intervals": [],
        "idempotency": {idempotency_key: digest},
    }
    _validate_schema("timing", ledger)
    _atomic_write(path, ledger)
    return ledger


def _close_current(ledger: dict[str, Any], outcome: str, at_utc: str, monotonic_ns: int) -> None:
    current = ledger.get("current")
    if not isinstance(current, dict):
        raise GovernanceError("timing ledger has no open interval")
    started_ns = current.get("started_monotonic_ns")
    if type(started_ns) is not int or monotonic_ns < started_ns:
        raise GovernanceError("interval duration is invalid")
    ledger.setdefault("intervals", []).append({
        **current,
        "ended_at_utc": at_utc,
        "ended_monotonic_ns": monotonic_ns,
        "duration_ns": monotonic_ns - started_ns,
        "outcome": outcome,
    })


def timing_transition(
    path: Path,
    next_stage: str,
    next_category: str,
    outcome: str,
    at_utc: str,
    monotonic_ns: int,
    boot_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    _validate_identity(next_stage, next_category, outcome)
    ledger = _load(path)
    digest = _request_digest(
        "timing-transition", path=str(path), next_stage=next_stage, next_category=next_category,
        outcome=outcome, at_utc=at_utc, monotonic_ns=monotonic_ns, boot_id=boot_id,
    )
    if _replay(ledger, idempotency_key, digest):
        return ledger
    if ledger.get("state") != "running":
        raise GovernanceError("finalized timing ledger cannot transition")
    _assert_clock(ledger, monotonic_ns, boot_id)
    _close_current(ledger, outcome, at_utc, monotonic_ns)
    ledger["current"] = {
        "stage": next_stage,
        "category": next_category,
        "started_at_utc": at_utc,
        "started_monotonic_ns": monotonic_ns,
    }
    ledger["idempotency"][idempotency_key] = digest
    _validate_schema("timing", ledger)
    _atomic_write(path, ledger)
    return ledger


def timing_finalize(
    path: Path,
    outcome: str,
    at_utc: str,
    monotonic_ns: int,
    boot_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise GovernanceError("outcome is invalid")
    ledger = _load(path)
    digest = _request_digest(
        "timing-finalize", path=str(path), outcome=outcome, at_utc=at_utc,
        monotonic_ns=monotonic_ns, boot_id=boot_id,
    )
    if _replay(ledger, idempotency_key, digest):
        return ledger
    if ledger.get("state") != "running":
        raise GovernanceError("timing ledger is already finalized")
    _assert_clock(ledger, monotonic_ns, boot_id)
    _close_current(ledger, outcome, at_utc, monotonic_ns)
    started_ns = ledger.get("started_monotonic_ns")
    if type(started_ns) is not int or monotonic_ns < started_ns:
        raise GovernanceError("total wall duration is invalid")
    category_totals = {category: 0 for category in sorted(CATEGORIES)}
    stage_totals: dict[str, int] = {}
    for interval in ledger["intervals"]:
        category_totals[interval["category"]] += interval["duration_ns"]
        stage_totals[interval["stage"]] = stage_totals.get(interval["stage"], 0) + interval["duration_ns"]
    interval_total = sum(category_totals.values())
    if sum(stage_totals.values()) != interval_total:
        raise GovernanceError("stage and category totals disagree")
    total_wall = monotonic_ns - started_ns
    gap = total_wall - interval_total
    if gap < 0:
        raise GovernanceError("intervals overlap total wall time")
    ledger.update({
        "state": "finalized",
        "current": None,
        "finalized_at_utc": at_utc,
        "finalized_monotonic_ns": monotonic_ns,
        "total_wall_ns": total_wall,
        "interval_total_ns": interval_total,
        "unattributed_gap_ns": gap,
        "category_totals_ns": category_totals,
        "stage_totals_ns": dict(sorted(stage_totals.items())),
    })
    ledger["idempotency"][idempotency_key] = digest
    _validate_schema("timing", ledger)
    _atomic_write(path, ledger)
    return ledger


def _load_snapshot(path: Path, label: str) -> tuple[dict[str, Any], str]:
    path = _validate_path(path, must_exist=True)
    try:
        content = path.read_bytes()
        value = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"{label} is invalid") from exc
    if not isinstance(value, dict):
        raise GovernanceError(f"{label} root must be an object")
    return value, "sha256:" + hashlib.sha256(content).hexdigest()


def _validate_authority(value: Any) -> dict[str, str]:
    required = {
        "repository", "base_commit", "specification_commit", "specification_path",
        "approved_specification_sha256", "target_commit", "target_tree",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise GovernanceError("authority keys do not match the contract")
    authority = {key: str(item) for key, item in value.items()}
    for key in ("base_commit", "specification_commit", "target_commit", "target_tree"):
        if not re.fullmatch(r"[0-9a-f]{40}", authority[key]):
            raise GovernanceError(f"authority {key} is invalid")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", authority["approved_specification_sha256"]):
        raise GovernanceError("authority specification digest is invalid")
    specification_path = Path(authority["specification_path"])
    if specification_path.is_absolute() or ".." in specification_path.parts or not authority["specification_path"].startswith("docs/"):
        raise GovernanceError("authority specification path is invalid")
    if not authority["repository"].strip():
        raise GovernanceError("authority repository is invalid")
    return authority


_BOARD_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_PROFILE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def _shared_hermes_root() -> Path:
    """Return the real invoking account's Hermes root, independent of HOME."""
    try:
        account_home = pwd.getpwuid(os.getuid()).pw_dir
    except (KeyError, OSError) as exc:
        raise GovernanceError("invoking account home is unavailable") from exc
    path = Path(account_home)
    if not path.is_absolute():
        raise GovernanceError("invoking account home is invalid")
    return path / ".hermes"


def _canonical_board_paths(board: str) -> tuple[Path, Path]:
    if not _BOARD_RE.fullmatch(board):
        raise GovernanceError("Kanban board slug is invalid")
    root = _shared_hermes_root()
    board_root = root / "kanban" / "boards" / board
    if board == "default":
        return root / "kanban.db", root / "kanban" / "logs"
    return board_root / "kanban.db", board_root / "logs"


def _snapshot_from_connection(
    connection: sqlite3.Connection,
    board: str,
    task_id: str,
    db_path: Path,
    log_root: Path,
) -> dict[str, Any]:
    if not re.fullmatch(r"t_[0-9a-f]{8}", task_id):
        raise GovernanceError("Kanban task id is invalid")
    task_row = connection.execute(
            "SELECT id, assignee, status, workspace_kind, max_runtime_seconds, "
            "max_retries, current_run_id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    terminal_task = task_row is not None and task_row["status"] in {"done", "blocked"}
    if terminal_task:
        run_row = connection.execute(
                "SELECT id, task_id, profile, status, max_runtime_seconds, started_at, "
                "ended_at, outcome, metadata, error FROM task_runs "
                "WHERE task_id = ? AND ended_at IS NOT NULL "
                "AND status IN ('done', 'completed', 'blocked') "
                "ORDER BY ended_at DESC, id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
    else:
        run_row = connection.execute(
                "SELECT id, task_id, profile, status, max_runtime_seconds, started_at, "
                "ended_at, outcome, metadata, error FROM task_runs "
                "WHERE task_id = ? AND id = ? LIMIT 1",
                (task_id, task_row["current_run_id"] if task_row is not None else None),
            ).fetchone()
    parent_rows = connection.execute(
            "SELECT parent_id FROM task_links WHERE child_id = ? ORDER BY parent_id",
            (task_id,),
        ).fetchall()
    if task_row is None or run_row is None:
        raise GovernanceError("canonical Kanban task or latest run is unavailable")
    raw_metadata = run_row["metadata"]
    if not isinstance(raw_metadata, str):
        raise GovernanceError("canonical Kanban run metadata is not text")
    metadata_bytes = raw_metadata.encode("utf-8")
    if not metadata_bytes or len(metadata_bytes) > 262_144:
        raise GovernanceError("canonical Kanban run metadata is unavailable or oversized")
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    if not isinstance(metadata, dict):
        raise GovernanceError("canonical Kanban run metadata root is invalid")
    terminal_run = run_row["status"] in {"done", "completed", "blocked"} and run_row["ended_at"] is not None
    if terminal_task:
        if task_row["current_run_id"] is not None or not terminal_run:
            raise GovernanceError("canonical terminal Kanban run continuity is invalid")
    elif task_row["current_run_id"] != run_row["id"] or terminal_run:
        raise GovernanceError("canonical active Kanban run continuity is invalid")
    snapshot = {
            "schema_version": 1,
            "source": "hermes-kanban-sqlite-ro",
            "board": board,
            "database_path": str(db_path),
            "log_path": str(log_root / f"{task_id}.log"),
            "detected_at_utc": _now_utc(),
            "detected_monotonic_ns": time.monotonic_ns(),
            "task": {
                "id": task_row["id"],
                "assignee": task_row["assignee"],
                "status": task_row["status"],
                "workspace_kind": task_row["workspace_kind"],
                "max_runtime_seconds": task_row["max_runtime_seconds"],
                "max_retries": task_row["max_retries"],
                "current_run_id": task_row["current_run_id"],
            },
            "parents": [row["parent_id"] for row in parent_rows],
            "run": {
                "id": run_row["id"],
                "task_id": run_row["task_id"],
                "profile": run_row["profile"],
                "status": run_row["status"],
                "max_runtime_seconds": run_row["max_runtime_seconds"],
                "started_at": run_row["started_at"],
                "ended_at": run_row["ended_at"],
                "outcome": run_row["outcome"],
                "metadata": metadata,
                "error": run_row["error"],
            },
    }
    _reject_secret_material(snapshot, "canonical Kanban snapshot")
    return snapshot


def _open_kanban_connection(board: str) -> tuple[sqlite3.Connection, Path, Path]:
    db_path, log_root = _canonical_board_paths(board)
    _reject_symlink_ancestors(db_path)
    if db_path.is_symlink() or not db_path.is_file():
        raise GovernanceError("canonical Kanban database is unavailable")
    uri = "file:" + quote(str(db_path), safe="/") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection, db_path, log_root


def _kanban_snapshots(board: str, task_ids: list[str]) -> list[tuple[dict[str, Any], str]]:
    """Capture multiple canonical tasks in one read transaction."""
    connection: sqlite3.Connection | None = None
    try:
        connection, db_path, log_root = _open_kanban_connection(board)
        connection.execute("BEGIN")
        snapshots = [
            _snapshot_from_connection(connection, board, task_id, db_path, log_root)
            for task_id in task_ids
        ]
        connection.execute("COMMIT")
    except (OSError, sqlite3.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("canonical Kanban snapshot failed") from exc
    finally:
        if connection is not None:
            connection.close()
    return [(snapshot, _kanban_source_digest(snapshot)) for snapshot in snapshots]


def _kanban_snapshot(board: str, task_id: str) -> tuple[dict[str, Any], str]:
    return _kanban_snapshots(board, [task_id])[0]


def _kanban_source_digest(snapshot: dict[str, Any]) -> str:
    authenticated = {
        key: snapshot[key]
        for key in ("schema_version", "source", "board", "database_path", "log_path", "task", "parents", "run")
    }
    return _canonical_sha256(authenticated)


def _require_stable_kanban_snapshot(board: str, task_id: str, expected_digest: str) -> None:
    _snapshot, observed_digest = _kanban_snapshot(board, task_id)
    if observed_digest != expected_digest:
        raise GovernanceError("canonical Kanban task or run changed before publication")


def _require_stable_kanban_snapshots(
    board: str, expected: list[tuple[str, str]],
) -> None:
    observed = _kanban_snapshots(board, [task_id for task_id, _digest in expected])
    if [digest for _snapshot, digest in observed] != [digest for _task_id, digest in expected]:
        raise GovernanceError("canonical Kanban task or run changed before publication")


def _kanban_provenance(snapshot: dict[str, Any], digest: str) -> dict[str, Any]:
    run = snapshot["run"]
    return {
        "source": snapshot["source"],
        "board": snapshot["board"],
        "task_id": snapshot["task"]["id"],
        "run_id": run["id"],
        "profile": run["profile"],
        "run_started_at": run["started_at"],
        "run_ended_at": run["ended_at"],
        "log_path": snapshot["log_path"],
        "parents": snapshot["parents"],
        "run_metadata": run["metadata"],
        "detected_at_utc": snapshot["detected_at_utc"],
        "detected_monotonic_ns": snapshot["detected_monotonic_ns"],
        "snapshot_sha256": digest,
    }


def bind_review_authority(
    contract_path: Path,
    capability_path: Path,
    output_path: Path,
    bound_at_utc: str | None = None,
) -> dict[str, Any]:
    contract, contract_digest = _load_snapshot(contract_path, "review contract")
    capability, capability_digest = _load_snapshot(capability_path, "capability evidence")
    _reject_secret_material(contract, "review contract")
    _reject_secret_material(capability, "capability evidence")
    required_contract = {
        "schema_version", "work_item", "review_card_id", "capability_evidence_sha256",
        "focused_check", "authority", "required_axes", "expected_workspace_kind", "expected_max_runtime_seconds",
        "expected_max_retries", "kanban_board", "expected_reviewer_profile",
    }
    if set(contract) != required_contract or contract.get("schema_version") != 1:
        raise GovernanceError("review contract keys do not match the contract")
    _validate_schema("review", contract)
    if not _WORK_ITEM_RE.fullmatch(str(contract.get("work_item", ""))):
        raise GovernanceError("review work item is invalid")
    card_id = str(contract.get("review_card_id", ""))
    if not re.fullmatch(r"t_[0-9a-f]{8}", card_id):
        raise GovernanceError("review card id is invalid")
    if contract.get("required_axes") != ["standards", "specification"]:
        raise GovernanceError("review axes must be standards and specification")
    if (
        contract.get("expected_workspace_kind") != "scratch"
        or contract.get("expected_max_runtime_seconds") != 1200
        or contract.get("expected_max_retries") != 1
    ):
        raise GovernanceError("review execution policy is invalid")
    board = str(contract.get("kanban_board", ""))
    reviewer_profile = str(contract.get("expected_reviewer_profile", ""))
    if not _BOARD_RE.fullmatch(board) or not _PROFILE_RE.fullmatch(reviewer_profile):
        raise GovernanceError("review Kanban board or reviewer profile is invalid")
    terminal, terminal_digest = _kanban_snapshot(board, card_id)
    authority = _validate_authority(contract.get("authority"))
    if contract.get("capability_evidence_sha256") != capability_digest:
        raise GovernanceError("capability evidence digest mismatch")
    spec = capability.get("review_specification")
    if not isinstance(spec, dict):
        raise GovernanceError("capability review specification is unavailable")
    try:
        spec = reviewctl.validate_review_specification(spec)
    except reviewctl.ReviewControlError as exc:
        raise GovernanceError("capability review specification is invalid") from exc
    if spec["review_type"] != "final":
        raise GovernanceError("governed review authority requires a final review specification")
    if contract.get("focused_check") != spec.get("focused_check"):
        raise GovernanceError("capability focused check mismatch")
    try:
        reviewctl.validate_capability_envelope(
            capability, spec, card_id, {}, revalidate_live=False
        )
    except reviewctl.ReviewControlError as exc:
        raise GovernanceError("capability evidence is not an authenticated non-semantic PASS") from exc
    capability_authority = {
        "repository": authority["repository"],
        "base_commit": spec.get("base_commit"),
        "specification_commit": spec.get("specification_commit"),
        "specification_path": spec.get("specification_path"),
        "approved_specification_sha256": capability.get("approved_specification", {}).get("sha256"),
        "target_commit": spec.get("expected_commit"),
        "target_tree": spec.get("expected_tree"),
    }
    if _validate_authority(capability_authority) != authority:
        raise GovernanceError("capability evidence authority mismatch")
    task = terminal.get("task")
    if (
        not isinstance(task, dict)
        or task.get("id") != card_id
        or task.get("status") != "done"
        or task.get("assignee") != reviewer_profile
    ):
        raise GovernanceError("review task is not terminal done for the exact card and reviewer")
    if (
        task.get("workspace_kind") != "scratch"
        or task.get("max_runtime_seconds") != 1200
        or task.get("max_retries") != 1
    ):
        raise GovernanceError("review task execution policy drift")
    run = terminal.get("run")
    if not isinstance(run, dict) or run.get("task_id") != card_id:
        raise GovernanceError("review run is not the canonical latest terminal run")
    if run.get("profile") != reviewer_profile or run.get("max_runtime_seconds") != 1200:
        raise GovernanceError("review run producer or runtime drift")
    if run.get("status") != "done" or run.get("outcome") != "completed" or run.get("error") is not None:
        raise GovernanceError("review run did not complete successfully")
    metadata = run.get("metadata")
    if not isinstance(metadata, dict):
        raise GovernanceError("review metadata is unavailable")
    if (
        metadata.get("work_item") != contract["work_item"]
        or metadata.get("verdict") != "PASS"
        or metadata.get("findings") != []
    ):
        raise GovernanceError("review identity or verdict is not a zero-finding PASS")
    if metadata.get("standards_axis") != "PASS" or metadata.get("specification_axis") != "PASS":
        raise GovernanceError("review axes did not both PASS")
    if metadata.get("capability_evidence_sha256") != capability_digest:
        raise GovernanceError("review terminal capability evidence mismatch")
    if _validate_authority(metadata.get("authority")) != authority:
        raise GovernanceError("review terminal authority mismatch")
    result = {
        "schema_version": 1,
        "kind": "governed-review-authority",
        "work_item": contract["work_item"],
        "review_card_id": card_id,
        "verdict": "PASS",
        "findings": [],
        "axes": {"standards": "PASS", "specification": "PASS"},
        "review_type": spec["review_type"],
        "focused_check": spec["focused_check"],
        "authority": authority,
        "capability_evidence_sha256": capability_digest,
        "review_contract_sha256": contract_digest,
        "kanban_provenance": _kanban_provenance(terminal, terminal_digest),
        "bound_at_utc": bound_at_utc or _now_utc(),
    }
    _require_stable_kanban_snapshot(board, card_id, terminal_digest)
    _atomic_write(output_path, result)
    return result


def bind_acceptance_authority(
    request_path: Path,
    review_authority_path: Path,
    output_path: Path,
    bound_at_utc: str | None = None,
) -> dict[str, Any]:
    request, request_digest = _load_snapshot(request_path, "acceptance request")
    review, review_digest = _load_snapshot(review_authority_path, "review authority")
    _reject_secret_material(request, "acceptance request")
    _reject_secret_material(review, "review authority")
    required_request = {
        "schema_version", "work_item", "acceptance_card_id", "review_card_id",
        "review_authority_sha256", "authority", "checks", "kanban_board",
        "expected_acceptance_profile",
    }
    if set(request) != required_request or request.get("schema_version") != 1:
        raise GovernanceError("acceptance request keys do not match the contract")
    _validate_schema("acceptance", request)
    if review.get("kind") != "governed-review-authority" or review.get("verdict") != "PASS" or review.get("findings") != []:
        raise GovernanceError("review authority is not an authorizing PASS")
    review_provenance = review.get("kanban_provenance")
    review_metadata = review_provenance.get("run_metadata") if isinstance(review_provenance, dict) else None
    if (
        not isinstance(review_metadata, dict)
        or review_metadata.get("verdict") != review.get("verdict")
        or review_metadata.get("findings") != review.get("findings")
        or {"standards": review_metadata.get("standards_axis"), "specification": review_metadata.get("specification_axis")} != review.get("axes")
        or review_metadata.get("capability_evidence_sha256") != review.get("capability_evidence_sha256")
        or _validate_authority(review_metadata.get("authority")) != _validate_authority(review.get("authority"))
    ):
        raise GovernanceError("review authority disagrees with its canonical run metadata")
    if request.get("review_authority_sha256") != review_digest:
        raise GovernanceError("review authority digest mismatch")
    if request.get("work_item") != review.get("work_item") or request.get("review_card_id") != review.get("review_card_id"):
        raise GovernanceError("acceptance request replays a different review")
    authority = _validate_authority(request.get("authority"))
    if authority != _validate_authority(review.get("authority")):
        raise GovernanceError("acceptance authority mismatch")
    acceptance_id = str(request.get("acceptance_card_id", ""))
    if not re.fullmatch(r"t_[0-9a-f]{8}", acceptance_id):
        raise GovernanceError("acceptance card id is invalid")
    board = str(request.get("kanban_board", ""))
    expected_profile = request.get("expected_acceptance_profile")
    if expected_profile is not None and not _PROFILE_RE.fullmatch(str(expected_profile)):
        raise GovernanceError("acceptance producer profile is invalid")
    review_provenance = review.get("kanban_provenance")
    if (
        not _BOARD_RE.fullmatch(board)
        or not isinstance(review_provenance, dict)
        or review_provenance.get("board") != board
        or review_provenance.get("task_id") != request["review_card_id"]
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(review_provenance.get("snapshot_sha256", "")))
    ):
        raise GovernanceError("acceptance Kanban board or review provenance is invalid")
    _require_stable_kanban_snapshot(
        board, request["review_card_id"], str(review_provenance["snapshot_sha256"])
    )
    terminal, terminal_digest = _kanban_snapshot(board, acceptance_id)
    task = terminal.get("task")
    if not isinstance(task, dict) or task.get("id") != acceptance_id or task.get("status") != "done":
        raise GovernanceError("acceptance task is not terminal done for the exact card")
    parents = terminal.get("parents")
    if parents != [request["review_card_id"]]:
        raise GovernanceError("acceptance card does not have the exact parent set")
    run = terminal.get("run")
    if not isinstance(run, dict) or run.get("task_id") != acceptance_id:
        raise GovernanceError("acceptance run is not the canonical latest terminal run")
    if run.get("status") not in {"done", "completed"} or run.get("outcome") != "completed" or run.get("error") is not None:
        raise GovernanceError("acceptance run did not complete successfully")
    if task.get("assignee") != expected_profile or run.get("profile") != expected_profile:
        raise GovernanceError("acceptance producer does not match the explicit contract")
    checks = request.get("checks")
    if not isinstance(checks, list) or not checks:
        raise GovernanceError("acceptance checks are unavailable")
    names: set[str] = set()
    normalized_checks: list[dict[str, Any]] = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"name", "ok", "evidence"}:
            raise GovernanceError("acceptance check keys do not match the contract")
        name = str(check.get("name", ""))
        evidence = str(check.get("evidence", ""))
        if (
            not _STAGE_RE.fullmatch(name)
            or name in names
            or check.get("ok") is not True
            or not evidence.strip()
            or len(evidence.encode("utf-8")) > 4096
        ):
            raise GovernanceError("acceptance contains a missing, duplicate, or failed check")
        names.add(name)
        normalized_checks.append({"name": name, "ok": True, "evidence": evidence})
    metadata = run.get("metadata")
    if not isinstance(metadata, dict):
        raise GovernanceError("acceptance run metadata is unavailable")
    required_metadata = {
        "work_item", "acceptance_card_id", "verdict", "review_card_id",
        "review_authority_sha256", "authority", "checks",
    }
    if not required_metadata.issubset(metadata):
        raise GovernanceError("acceptance run metadata is incomplete")
    if (
        metadata.get("work_item") != request["work_item"]
        or metadata.get("acceptance_card_id") != acceptance_id
        or metadata.get("verdict") != "PASS"
        or metadata.get("review_card_id") != request["review_card_id"]
        or metadata.get("review_authority_sha256") != review_digest
        or _validate_authority(metadata.get("authority")) != authority
        or metadata.get("checks") != normalized_checks
    ):
        raise GovernanceError("acceptance run metadata does not authenticate the requested PASS")
    result = {
        "schema_version": 1,
        "kind": "governed-acceptance-authority",
        "work_item": request["work_item"],
        "review_card_id": request["review_card_id"],
        "acceptance_card_id": acceptance_id,
        "verdict": "PASS",
        "authority": authority,
        "checks": normalized_checks,
        "review_authority_sha256": review_digest,
        "acceptance_request_sha256": request_digest,
        "kanban_provenance": _kanban_provenance(terminal, terminal_digest),
        "gates": {"pr_opening": "UNAUTHORIZED", "merge": "UNAUTHORIZED"},
        "bound_at_utc": bound_at_utc or _now_utc(),
    }
    _require_stable_kanban_snapshots(board, [
        (request["review_card_id"], str(review_provenance["snapshot_sha256"])),
        (acceptance_id, terminal_digest),
    ])
    _atomic_write(output_path, result)
    return result


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parent-check")
    init = sub.add_parser("timing-init")
    transition = sub.add_parser("timing-transition")
    finalize = sub.add_parser("timing-finalize")
    review_bind = sub.add_parser("review-bind")
    review_bind.add_argument("--contract", type=Path, required=True)
    review_bind.add_argument("--capability", type=Path, required=True)
    review_bind.add_argument("--output", type=Path, required=True)
    acceptance_bind = sub.add_parser("acceptance-bind")
    acceptance_bind.add_argument("--request", type=Path, required=True)
    acceptance_bind.add_argument("--review-authority", type=Path, required=True)
    acceptance_bind.add_argument("--output", type=Path, required=True)
    for item in (init, transition, finalize):
        item.add_argument("--path", type=Path, required=True)
        item.add_argument("--idempotency-key", required=True)
        item.add_argument("--at-utc")
        item.add_argument("--monotonic-ns", type=int)
        item.add_argument("--boot-id")
    init.add_argument("--work-item", required=True)
    init.add_argument("--stage", required=True)
    init.add_argument("--category", choices=sorted(CATEGORIES), required=True)
    transition.add_argument("--next-stage", required=True)
    transition.add_argument("--next-category", choices=sorted(CATEGORIES), required=True)
    transition.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    finalize.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "parent-check":
            require_parent_context()
            _print({"ok": True, "context": "parent-operator"})
            return 0
        if args.command == "review-bind":
            require_parent_context()
            _print(bind_review_authority(args.contract, args.capability, args.output))
            return 0
        if args.command == "acceptance-bind":
            require_parent_context()
            _print(bind_acceptance_authority(args.request, args.review_authority, args.output))
            return 0
        at_utc = args.at_utc or _now_utc()
        monotonic_ns = args.monotonic_ns if args.monotonic_ns is not None else time.monotonic_ns()
        boot_id = args.boot_id or _boot_id()
        if args.command == "timing-init":
            result = timing_init(args.path, args.work_item, args.stage, args.category, at_utc, monotonic_ns, boot_id, args.idempotency_key)
        elif args.command == "timing-transition":
            result = timing_transition(args.path, args.next_stage, args.next_category, args.outcome, at_utc, monotonic_ns, boot_id, args.idempotency_key)
        else:
            result = timing_finalize(args.path, args.outcome, at_utc, monotonic_ns, boot_id, args.idempotency_key)
        _print(result)
        return 0
    except GovernanceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
