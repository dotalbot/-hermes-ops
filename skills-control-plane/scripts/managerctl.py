#!/usr/bin/env python3
"""CLI for governed project setup and Skills Manager lifecycle operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import managerlib


CONTROL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HERMES_HOME = Path.home() / ".hermes"


def _control_commit(control_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(control_root.parent), "rev-parse", "HEAD"],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    if completed.returncode != 0:
        raise managerlib.ManagerError("control-plane repository commit is unavailable")
    return completed.stdout.strip()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    value = managerlib._load_document(path, label)
    return value


def _write_output(path: Path | None, value: dict[str, Any] | str) -> None:
    if isinstance(value, str):
        data = value.encode("utf-8")
    else:
        data = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if path is None:
        sys.stdout.buffer.write(data)
        return
    if not path.is_absolute():
        raise managerlib.ManagerError("output path must be absolute")
    try:
        managerlib._atomic_write(path, data, 0o600)
    except OSError as exc:
        raise managerlib.ManagerError("output publication failed") from exc
    print(path)


def _adapter(args: argparse.Namespace) -> managerlib.LiveHermesAdapter:
    return managerlib.LiveHermesAdapter(args.hermes_home, args.hermes_bin)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-root", type=Path, default=CONTROL_ROOT)
    parser.add_argument("--hermes-home", type=Path, default=DEFAULT_HERMES_HOME)
    parser.add_argument("--hermes-bin", default="hermes")
    modules = parser.add_subparsers(dest="module", required=True)

    project = modules.add_parser("project")
    project_commands = project.add_subparsers(dest="command", required=True)
    plan = project_commands.add_parser("plan")
    plan.add_argument("--request", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    apply_cmd = project_commands.add_parser("apply")
    apply_cmd.add_argument("--plan", type=Path, required=True)
    apply_cmd.add_argument("--approve", required=True)
    apply_cmd.add_argument("--journal-dir", type=Path, required=True)
    doctor = project_commands.add_parser("doctor")
    doctor.add_argument("--request", type=Path, required=True)
    doctor.add_argument("--output", type=Path)
    reconcile = project_commands.add_parser("reconcile")
    reconcile.add_argument("--doctor-report", type=Path, required=True)
    reconcile.add_argument("--output", type=Path, required=True)
    rollback = project_commands.add_parser("rollback")
    rollback.add_argument("--journal", type=Path, required=True)
    rollback.add_argument("--approve", required=True)
    rollback.add_argument("--journal-dir", type=Path, required=True)

    fleet = modules.add_parser("fleet")
    fleet_commands = fleet.add_subparsers(dest="command", required=True)
    fleet_status = fleet_commands.add_parser("status")
    fleet_status.add_argument("--format", choices=("json", "markdown"), default="json")
    fleet_status.add_argument("--output", type=Path)

    skill = modules.add_parser("skill")
    skill_commands = skill.add_subparsers(dest="command", required=True)
    inventory = skill_commands.add_parser("inventory")
    inventory.add_argument("--output", type=Path)
    candidate = skill_commands.add_parser("candidate-plan")
    candidate.add_argument("--request", type=Path, required=True)
    candidate.add_argument("--output", type=Path, required=True)
    candidate_apply = skill_commands.add_parser("candidate")
    candidate_apply.add_argument("--plan", type=Path, required=True)
    candidate_apply.add_argument("--approve", required=True)
    candidate_apply.add_argument("--journal-dir", type=Path, required=True)
    impact = skill_commands.add_parser("impact")
    impact.add_argument("--request", type=Path, required=True)
    impact.add_argument("--output", type=Path)
    canary_plan = skill_commands.add_parser("canary-plan")
    canary_plan.add_argument("--request", type=Path, required=True)
    canary_plan.add_argument("--output", type=Path, required=True)
    canary = skill_commands.add_parser("canary")
    canary.add_argument("--plan", type=Path, required=True)
    canary.add_argument("--approve", required=True)
    canary.add_argument("--journal-dir", type=Path, required=True)
    update = skill_commands.add_parser("update-plan")
    update.add_argument("--request", type=Path, required=True)
    update.add_argument("--output", type=Path, required=True)
    promote = skill_commands.add_parser("promote")
    promote.add_argument("--plan", type=Path, required=True)
    promote.add_argument("--approve", required=True)
    promote.add_argument("--journal-dir", type=Path, required=True)
    skill_rollback = skill_commands.add_parser("rollback")
    skill_rollback.add_argument("--journal", type=Path, required=True)
    skill_rollback.add_argument("--approve", required=True)
    skill_rollback.add_argument("--journal-dir", type=Path, required=True)

    modules.add_parser("verify")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    control_root = args.control_root.resolve()
    try:
        if args.module == "project":
            adapter = _adapter(args)
            if args.command == "plan":
                plan = managerlib.build_project_plan(
                    args.request, control_root, adapter, control_commit=_control_commit(control_root)
                )
                _write_output(args.output, plan)
                return 1 if plan["blockers"] else 0
            if args.command == "reconcile":
                plan = managerlib.build_project_reconcile_plan(
                    args.doctor_report, control_root, adapter, control_commit=_control_commit(control_root)
                )
                _write_output(args.output, plan)
                return 1 if plan["blockers"] else 0
            if args.command == "apply":
                result = managerlib.apply_plan(
                    _read_json(args.plan, "manager plan"), args.approve,
                    control_root, adapter, args.journal_dir,
                )
                _write_output(None, result)
                return 0
            if args.command == "doctor":
                result = managerlib.doctor_project(args.request, control_root, adapter)
                _write_output(args.output, result)
                return 0 if result["state"] == "GREEN" else 1
            result = managerlib.rollback_journal(
                args.journal, args.approve, control_root, adapter, args.journal_dir
            )
            _write_output(None, result)
            return 0
        if args.module == "fleet":
            result = managerlib.fleet_status(control_root)
            rendered: dict[str, Any] | str = result if args.format == "json" else managerlib.render_fleet_markdown(result)
            _write_output(args.output, rendered)
            return 1 if result["state"] == "RED" else 0
        if args.module == "skill":
            if args.command == "inventory":
                result = managerlib.skill_inventory(control_root)
                _write_output(args.output, result)
                return 0
            if args.command == "candidate-plan":
                result = managerlib.build_skill_candidate_plan(
                    args.request, control_root, control_commit=_control_commit(control_root)
                )
                _write_output(args.output, result)
                return 1 if result["blockers"] else 0
            if args.command == "impact":
                result = managerlib.skill_impact(args.request, control_root)
                _write_output(args.output, result)
                return 0 if result["complete"] else 1
            if args.command == "canary-plan":
                result = managerlib.build_skill_canary_plan(
                    args.request, control_root, _adapter(args), control_commit=_control_commit(control_root)
                )
                _write_output(args.output, result)
                return 1 if result["blockers"] else 0
            if args.command == "update-plan":
                result = managerlib.build_skill_update_plan(
                    args.request, control_root, _adapter(args), control_commit=_control_commit(control_root)
                )
                _write_output(args.output, result)
                return 1 if result["blockers"] else 0
            if args.command == "rollback":
                result = managerlib.rollback_journal(
                    args.journal, args.approve, control_root, _adapter(args), args.journal_dir
                )
                _write_output(None, result)
                return 0
            result = managerlib.apply_plan(
                _read_json(args.plan, "skill promotion plan"), args.approve,
                control_root, _adapter(args), args.journal_dir,
            )
            _write_output(None, result)
            return 0
        result = managerlib.verify_manager(control_root)
        _write_output(None, result)
        return 0 if result["ok"] else 1
    except managerlib.ManagerError as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
