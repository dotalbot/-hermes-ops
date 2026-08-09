#!/usr/bin/env python3
"""Fail-closed Skill Control Plane inspection and project-init dry-run tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any
from urllib.request import urlopen

import jsonschema
import yaml

from review_boundary import ReviewBoundaryError, ReviewRepository


CONTROL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CONTROL_ROOT.parent
DEFAULT_PROJECT = CONTROL_ROOT / "projects" / "jellyssh" / "project.yaml"
SCHEMA = CONTROL_ROOT / "schemas" / "project-skill-profile.schema.json"
CATALOG = CONTROL_ROOT / "catalog.yaml"
HASH_ALGORITHM = "sha256(sorted(u64be(path-length) + path + u64be(content-length) + content))"
ZERO_HASH = "sha256:" + ("0" * 64)
EXPECTED_REVIEW_TOOLS = frozenset({
    "repository_metadata", "list_repository_files", "read_repository_text",
    "review_git_diff", "review_git_show", "run_readonly_check",
})
EXPECTED_CONTROLLER_CHECKS = frozenset({
    "controller:sandbox-self-check:PASS",
    "controller:head-clean:PASS",
    "controller:diff-check:PASS",
    "controller:submodule-status:PASS",
    "controller:dart-format-check:PASS",
    "controller:flutter-analyze:BLOCK",
    "controller:flutter-test:BLOCK",
})
PINNED_SSH_OPTIONS = [
    "-F", "/dev/null",
    "-o", "BatchMode=yes",
    "-o", "ClearAllForwardings=yes",
    "-o", "StrictHostKeyChecking=yes",
    "-o", "UserKnownHostsFile=/home/jellybot/.hermes/profiles/jellybase_jellyssh_reviewer/jellybase_known_hosts",
    "-o", "GlobalKnownHostsFile=/dev/null",
    "-o", "HostKeyAlias=jellybase-lan-pinned",
    "-o", "HostKeyAlgorithms=ssh-ed25519",
    "-o", "HostName=192.168.1.2",
    "-o", "Port=22",
    "-o", "IdentityFile=/home/jellybot/.ssh/id_ed25519",
    "-o", "IdentitiesOnly=yes",
    "-o", "ProxyCommand=none",
    "-o", "ProxyJump=none",
]


class ControlPlaneError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlPlaneError(f"missing YAML: {path}") from exc
    except yaml.YAMLError as exc:
        raise ControlPlaneError(f"invalid YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlPlaneError(f"YAML root must be a mapping: {path}")
    return value


def tree_snapshot(path: Path) -> tuple[str, dict[str, bytes]]:
    """Capture one skill tree in memory and hash those exact captured bytes."""
    if path.is_symlink():
        raise ControlPlaneError(f"skill tree root is a symlink: {path}")
    if not path.is_dir():
        raise ControlPlaneError(f"skill tree is missing: {path}")
    digest = hashlib.sha256()
    file_count = 0
    files: dict[str, bytes] = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ControlPlaneError(f"skill tree contains a symlink: {item}")
        mode = item.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ControlPlaneError(f"skill tree contains a non-regular file: {item}")
        rel = item.relative_to(path).as_posix()
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        rel_bytes = rel.encode("utf-8")
        content = item.read_bytes()
        digest.update(len(rel_bytes).to_bytes(8, "big"))
        digest.update(rel_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        files[rel] = content
        file_count += 1
    if file_count == 0:
        raise ControlPlaneError(f"skill tree has no files: {path}")
    return "sha256:" + digest.hexdigest(), files


def tree_hash(path: Path) -> str:
    return tree_snapshot(path)[0]


def aggregate_hash(name: str, version: str, skills: list[dict[str, Any]]) -> str:
    payload = {
        "name": name,
        "version": version,
        "skills": [
            {"name": str(item["name"]), "bundle_sha256": str(item["bundle_sha256"])}
            for item in sorted(skills, key=lambda value: str(value["name"]))
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def descriptor_hash(document: dict[str, Any]) -> str:
    """Hash all descriptor governance/provenance fields except this digest itself."""
    payload = dict(document)
    payload.pop("manifest_sha256", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def is_zero_hash(value: object) -> bool:
    return value == ZERO_HASH


def file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def file_sha256_or_none(path: Path) -> str | None:
    try:
        return file_sha256(path)
    except (ControlPlaneError, OSError):
        return None


def validate_checkout(
    path: str,
    authority: dict[str, Any],
    label: str,
    ssh_target: str | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        repository = ReviewRepository(path, str(authority.get("commit", "")), ssh_target)
        metadata = repository.metadata()
        if metadata.get("head") != authority.get("commit"):
            errors.append(f"{label} commit drift")
        if metadata.get("branch") != "main":
            errors.append(f"{label} branch drift")
        if metadata.get("origin") != authority.get("remote"):
            errors.append(f"{label} remote drift")
        if repository.run_check("head-clean") != "CLEAN":
            errors.append(f"{label} checkout is not clean")
    except ReviewBoundaryError as exc:
        errors.append(f"{label} checkout validation failed: {exc}")
    return errors


def resolve_remote_path(path: str, ssh_target: str = "jellydev@jellybase-lan") -> str:
    raw = Path(path)
    if not raw.is_absolute() or ".." in raw.parts:
        raise ControlPlaneError("remote path is unsafe")
    command = shlex.join(["env", "-i", "PATH=/usr/bin:/bin", "readlink", "-f", "--", path])
    try:
        proc = subprocess.run(
            ["ssh", *PINNED_SSH_OPTIONS, "--", ssh_target, command],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ControlPlaneError(f"remote path probe failed: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise ControlPlaneError("remote path resolution failed")
    return proc.stdout.strip()


def run_remote_fixed(args: list[str], ssh_target: str, timeout: int = 30) -> str:
    command = shlex.join(["env", "-i", "HOME=/home/jellydev", "PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8", *args])
    proc = subprocess.run(
        ["ssh", *PINNED_SSH_OPTIONS, "--", ssh_target, command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise ControlPlaneError("remote fixed probe failed")
    return proc.stdout.strip()


def _resolve_descriptor(control_root: Path, entry: dict[str, Any]) -> Path:
    rel = str(entry.get("manifest", ""))
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ControlPlaneError("catalog manifest path is unsafe")
    path = (control_root / rel).resolve()
    try:
        path.relative_to(control_root.resolve())
    except ValueError as exc:
        raise ControlPlaneError("catalog manifest escapes control root") from exc
    return path


def validate_descriptor(control_root: Path, descriptor_path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    doc = load_yaml(descriptor_path)
    for key in ("schema_version", "kind", "name", "version", "state", "skills", "bundle_sha256", "manifest_sha256"):
        if key not in doc:
            errors.append(f"{descriptor_path}: missing {key}")
    skills = doc.get("skills")
    if doc.get("hash_algorithm") != HASH_ALGORITHM:
        errors.append(f"{descriptor_path}: undocumented or mismatched hash algorithm")
    if is_zero_hash(doc.get("bundle_sha256")):
        errors.append(f"{descriptor_path}: zero aggregate hash is forbidden")
    actual_manifest_hash = descriptor_hash(doc)
    if doc.get("manifest_sha256") != actual_manifest_hash:
        errors.append(
            f"{descriptor_path}: governance/provenance manifest drift: expected {doc.get('manifest_sha256')}, got {actual_manifest_hash}"
        )
    if not isinstance(skills, list) or not skills:
        errors.append(f"{descriptor_path}: skills must be a non-empty list")
        return doc, errors
    names: set[str] = set()
    for item in skills:
        if not isinstance(item, dict):
            errors.append(f"{descriptor_path}: skill entry is not a mapping")
            continue
        name = str(item.get("name", ""))
        if not name or name in names:
            errors.append(f"{descriptor_path}: missing or duplicate skill name {name!r}")
            continue
        names.add(name)
        if is_zero_hash(item.get("bundle_sha256")):
            errors.append(f"{descriptor_path}: zero skill hash is forbidden for {name}")
        rel = Path(str(item.get("path", "")))
        if rel.is_absolute() or ".." in rel.parts:
            errors.append(f"{descriptor_path}: unsafe skill path for {name}")
            continue
        skill_path = descriptor_path.parent / rel
        try:
            actual = tree_hash(skill_path)
        except ControlPlaneError as exc:
            errors.append(str(exc))
            continue
        if actual != item.get("bundle_sha256"):
            errors.append(
                f"{descriptor_path}: hash drift for {name}: expected {item.get('bundle_sha256')}, got {actual}"
            )
    if isinstance(skills, list) and all(isinstance(item, dict) for item in skills):
        actual_bundle = aggregate_hash(str(doc.get("name", "")), str(doc.get("version", "")), skills)
        if actual_bundle != doc.get("bundle_sha256"):
            errors.append(
                f"{descriptor_path}: aggregate drift: expected {doc.get('bundle_sha256')}, got {actual_bundle}"
            )
    return doc, errors


def validate_runtime(
    runtime_path: Path,
    project: dict[str, Any],
    control_root: Path = CONTROL_ROOT,
    declared_skills: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    declared_skills = declared_skills or {}
    runtime = load_yaml(runtime_path)
    schema_path = control_root / "schemas" / "runtime-state.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        validation_errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(runtime),
            key=lambda err: list(err.absolute_path),
        )
        errors.extend(
            f"runtime schema {'.'.join(map(str, err.absolute_path)) or '<root>'}: {err.message}"
            for err in validation_errors
        )
        if validation_errors:
            return errors
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return [f"runtime schema unavailable or invalid: {exc}"]
    required = {"schema_version", "project", "state", "paths", "profiles", "review_boundary", "repository_auth", "toolchain", "board"}
    missing = sorted(required - set(runtime))
    if missing:
        return [f"{runtime_path}: missing runtime keys: {', '.join(missing)}"]
    if runtime.get("project") != project.get("project", {}).get("slug"):
        errors.append(f"{runtime_path}: project slug mismatch")
    paths = runtime.get("paths")
    if not isinstance(paths, dict):
        errors.append(f"{runtime_path}: paths must be a mapping")
        runtime_paths: dict[str, Any] = {}
    else:
        runtime_paths = paths
        for key in (
            "coordinator_checkout", "coordinator_review_checkout", "implementation_checkout",
            "reviewer_checkout", "implementation_bridge", "reviewer_bridge",
        ):
            value = paths.get(key)
            segments = value.split("/") if isinstance(value, str) else []
            if (
                not isinstance(value, str)
                or not value.startswith("/")
                or value == "/"
                or "" in segments[1:]
                or any(segment in {".", ".."} for segment in segments)
            ):
                errors.append(f"{runtime_path}: {key} must be a normalized non-traversing absolute path")
        if paths.get("implementation_bridge") == paths.get("reviewer_bridge"):
            errors.append(f"{runtime_path}: implementation and review bridges must differ")
    boundary = runtime.get("review_boundary")
    if not isinstance(boundary, dict) or boundary.get("type") != "mcp-controller-evidence-no-model-tools":
        errors.append(f"{runtime_path}: reviewer boundary must be mcp-controller-evidence-no-model-tools")
    else:
        exposed = set(boundary.get("exposed_tools") or [])
        forbidden = set(boundary.get("forbidden_toolsets") or [])
        expected_exposed = EXPECTED_REVIEW_TOOLS
        if exposed != expected_exposed:
            errors.append(f"{runtime_path}: reviewer must expose exactly the six approved read-only MCP tools")
        if not {"terminal", "file", "code_execution", "kanban", "memory"}.issubset(forbidden):
            errors.append(f"{runtime_path}: reviewer forbidden toolsets are incomplete")
        if (
            boundary.get("review_root") != project.get("profiles", {}).get("reviewer", {}).get("workspace")
            or boundary.get("transport") != "ssh"
            or boundary.get("ssh_target") != "jellydev@jellybase-lan"
        ):
            errors.append(f"{runtime_path}: reviewer boundary host/workspace drift")
        component_paths = {
            "reviewctl.py": control_root / "scripts" / "reviewctl.py",
            "review_boundary.py": control_root / "scripts" / "review_boundary.py",
            "jellyssh_review_mcp.py": control_root / "scripts" / "jellyssh_review_mcp.py",
            "projectctl.py": control_root / "scripts" / "projectctl.py",
        }
        component_hashes = boundary.get("implementation_sha256")
        if not isinstance(component_hashes, dict) or set(component_hashes) != set(component_paths):
            errors.append(f"{runtime_path}: controller implementation hash manifest shape drift")
        else:
            for name, component_path in component_paths.items():
                if component_path.is_symlink() or not component_path.is_file():
                    errors.append(f"controller implementation component type drift: {name}")
                elif file_sha256(component_path) != component_hashes.get(name):
                    errors.append(f"controller implementation hash drift: {name}")
        if boundary.get("project_manifest_sha256") != file_sha256(
            control_root / "projects" / "jellyssh" / "project.yaml"
        ):
            errors.append(f"{runtime_path}: project authority manifest hash drift")
        try:
            evidence_rel = Path(str(boundary.get("controller_evidence", "")))
            if evidence_rel.is_absolute() or ".." in evidence_rel.parts:
                raise ControlPlaneError("controller evidence path is unsafe")
            evidence_path = (control_root.parent / evidence_rel).resolve()
            evidence_path.relative_to(control_root.parent.resolve())
            if file_sha256(evidence_path) != boundary.get("controller_evidence_sha256"):
                errors.append("controller review evidence hash drift")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            expected_checks = EXPECTED_CONTROLLER_CHECKS
            if (
                evidence.get("project") != "jellyssh"
                or evidence.get("expected_commit") != project.get("authority", {}).get("commit")
                or evidence.get("verdict") != "BLOCK"
                or evidence.get("controller_model") != "openrouter/deepseek/deepseek-v3.2"
                or set(evidence.get("checks") or []) != expected_checks
            ):
                errors.append("controller review evidence contract drift")
        except (ControlPlaneError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"controller review evidence invalid: {type(exc).__name__}")
        try:
            ui_rel = Path(str(boundary.get("conditional_ui_evidence", "")))
            if ui_rel.is_absolute() or ".." in ui_rel.parts:
                raise ControlPlaneError("conditional UI evidence path is unsafe")
            ui_path = (control_root.parent / ui_rel).resolve()
            ui_path.relative_to(control_root.parent.resolve())
            if file_sha256(ui_path) != boundary.get("conditional_ui_evidence_sha256"):
                errors.append("conditional UI review evidence hash drift")
            ui_evidence = json.loads(ui_path.read_text(encoding="utf-8"))
            if (
                boundary.get("conditional_ui_model") != "openrouter/google/gemini-3.1-pro-preview"
                or boundary.get("conditional_ui_routing_state") != "verified"
                or ui_evidence.get("project") != "jellyssh"
                or ui_evidence.get("expected_commit") != project.get("authority", {}).get("commit")
                or ui_evidence.get("review_type") != "mobile-ux"
                or ui_evidence.get("verdict") != "BLOCK"
                or ui_evidence.get("controller_model") != "openrouter/google/gemini-3.1-pro-preview"
                or set(ui_evidence.get("checks") or []) != EXPECTED_CONTROLLER_CHECKS
            ):
                errors.append("conditional UI review evidence contract drift")
        except (ControlPlaneError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"conditional UI review evidence invalid: {type(exc).__name__}")

    profile_specs = runtime.get("profiles")
    if not isinstance(profile_specs, dict):
        errors.append(f"{runtime_path}: profiles must be a mapping")
    else:
        for role in ("implementation", "reviewer"):
            live = profile_specs.get(role)
            declared = project.get("profiles", {}).get(role, {})
            if not isinstance(live, dict):
                errors.append(f"{runtime_path}: missing runtime profile {role}")
                continue
            if live.get("name") != declared.get("name"):
                errors.append(f"{runtime_path}: {role} profile name mismatch")
                continue
            if live.get("state") not in {"installed", "verified", "routable"}:
                continue
            profile_root = Path.home() / ".hermes" / "profiles" / str(live["name"])
            if not profile_root.is_dir():
                errors.append(f"runtime profile is missing: {profile_root}")
                continue
            try:
                config = load_yaml(profile_root / "config.yaml")
            except ControlPlaneError as exc:
                errors.append(str(exc))
                continue
            expected_model = declared.get("model", {})
            actual_model = config.get("model", {})
            if actual_model.get("provider") != expected_model.get("provider"):
                errors.append(f"{role} provider drift")
            if actual_model.get("default") != expected_model.get("model"):
                errors.append(f"{role} model drift")
            if config.get("fallback_providers") != [] or config.get("fallback_model") not in (None, "", []):
                errors.append(f"{role} fallback routes must be empty")
            kanban = config.get("kanban", {})
            if (
                kanban.get("auto_decompose") is not False
                or int(kanban.get("max_spawn", 0)) != 1
                or int(kanban.get("max_in_progress", 0)) != 1
                or (kanban.get("default_assignee") or "") != ""
                or (kanban.get("orchestrator_profile") or "") != ""
            ):
                errors.append(f"{role} conservative Kanban settings drift")
            try:
                hcfg = json.loads((profile_root / "hindsight" / "config.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{role} Hindsight config invalid: {exc}")
                hcfg = {}
            if hcfg.get("bank_id") != declared.get("bank"):
                errors.append(f"{role} Hindsight bank drift")
            if bool(hcfg.get("auto_recall")) != bool(declared.get("auto_recall")):
                errors.append(f"{role} Hindsight recall drift")
            if bool(hcfg.get("auto_retain")) != bool(declared.get("auto_retain")):
                errors.append(f"{role} Hindsight retention drift")
            expected_skills = set(live.get("skills") or [])
            bundle_name = str(declared.get("bundle", ""))
            authoritative_skills = set(project.get("skill_layers", {}).get("bundles", {}).get(bundle_name) or [])
            if expected_skills != authoritative_skills:
                errors.append(
                    f"{role} runtime skill set does not match authoritative bundle {bundle_name}: "
                    f"runtime={sorted(expected_skills)}, bundle={sorted(authoritative_skills)}"
                )
            actual_skills = {item.parent.name for item in (profile_root / "skills").glob("*/SKILL.md")}
            if actual_skills != expected_skills:
                errors.append(
                    f"{role} skill set drift: expected {sorted(expected_skills)}, got {sorted(actual_skills)}"
                )
            try:
                managed = json.loads((profile_root / "managed-skills.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{role} managed-skill manifest invalid: {exc}")
                managed = {}
            managed_by_name = {
                item.get("name"): item
                for item in managed.get("skills", [])
                if isinstance(item, dict)
            }
            for name in sorted(expected_skills):
                item = managed_by_name.get(name)
                if item is None:
                    errors.append(f"{role} managed-skill entry missing: {name}")
                    continue
                try:
                    actual_hash = tree_hash(profile_root / "skills" / name)
                except ControlPlaneError as exc:
                    errors.append(str(exc))
                    continue
                if actual_hash != item.get("bundle_sha256"):
                    errors.append(f"{role} installed skill hash drift: {name}")
                authority = declared_skills.get(name)
                if authority is None or actual_hash != authority.get("bundle_sha256"):
                    errors.append(f"{role} installed skill does not match project authority: {name}")
                if item.get("bundle_sha256") != (authority or {}).get("bundle_sha256"):
                    errors.append(f"{role} managed-skill manifest does not match project authority: {name}")
            if role == "implementation":
                terminal = config.get("terminal", {})
                if (
                    terminal.get("backend") != "ssh"
                    or terminal.get("cwd") != runtime_paths.get("implementation_bridge")
                    or terminal.get("ssh_host") != "jellybase-lan"
                    or terminal.get("ssh_user") != "jellydev"
                    or terminal.get("ssh_file_sync") is not False
                    or declared.get("workspace") != runtime_paths.get("implementation_checkout")
                ):
                    errors.append("implementation SSH workspace binding drift")
            else:
                cli_tools = config.get("platform_toolsets", {}).get("cli")
                disabled = set(config.get("agent", {}).get("disabled_toolsets") or [])
                server = config.get("mcp_servers", {}).get("jellyssh_review", {})
                if cli_tools != ["mcp-jellyssh_review"]:
                    errors.append("reviewer CLI toolset is not restricted to mcp-jellyssh_review")
                if not {"terminal", "file", "code_execution", "kanban", "memory"}.issubset(disabled):
                    errors.append("reviewer disabled toolsets are incomplete")
                if server.get("sampling", {}).get("enabled") is not False:
                    errors.append("reviewer MCP sampling must be disabled")
                if server.get("trust") != "untrusted":
                    errors.append("reviewer MCP must use untrusted trust tier with explicit read-only annotations")
                terminal = config.get("terminal", {})
                server_env = server.get("env", {})
                if (
                    terminal.get("backend") != "ssh"
                    or terminal.get("cwd") != runtime_paths.get("reviewer_bridge")
                    or terminal.get("ssh_host") != "jellybase-lan"
                    or terminal.get("ssh_user") != "jellydev"
                    or terminal.get("ssh_port") != 22
                    or terminal.get("ssh_key") != "/home/jellybot/.ssh/id_ed25519"
                    or terminal.get("ssh_file_sync") is not False
                    or terminal.get("persistent_shell") is not False
                    or terminal.get("timeout") != 330
                    or declared.get("workspace") != runtime_paths.get("reviewer_checkout")
                ):
                    errors.append("reviewer SSH workspace binding drift")
                if (
                    server_env.get("JELLYSSH_REVIEW_ROOT") != runtime_paths.get("reviewer_checkout")
                    or server_env.get("JELLYSSH_REVIEW_SSH_TARGET") != "jellydev@jellybase-lan"
                    or server_env.get("JELLYSSH_EXPECTED_COMMIT") != project.get("authority", {}).get("commit")
                    or server_env.get("JELLYSSH_REVIEW_BASE_COMMIT") != project.get("authority", {}).get("commit")
                    or set(server_env) != {
                        "JELLYSSH_REVIEW_ROOT",
                        "JELLYSSH_EXPECTED_COMMIT",
                        "JELLYSSH_REVIEW_BASE_COMMIT",
                        "JELLYSSH_REVIEW_SSH_TARGET",
                    }
                ):
                    errors.append("reviewer MCP root drift")
                if (
                    set(server) != {"command", "args", "env", "timeout", "connect_timeout", "trust", "sampling", "tools"}
                    or server.get("command") != "/home/jellybot/.hermes/hermes-agent/venv/bin/python"
                    or server.get("args") != [str(CONTROL_ROOT / "scripts" / "jellyssh_review_mcp.py")]
                    or server.get("timeout") != 330
                    or server.get("connect_timeout") != 30
                    or set(server.get("sampling", {})) != {"enabled"}
                    or set(server.get("tools", {})) != {"include", "resources", "prompts"}
                    or set(server.get("tools", {}).get("include") or []) != EXPECTED_REVIEW_TOOLS
                    or len(server.get("tools", {}).get("include") or []) != len(EXPECTED_REVIEW_TOOLS)
                    or server.get("tools", {}).get("resources") is not False
                    or server.get("tools", {}).get("prompts") is not False
                ):
                    errors.append("reviewer MCP server shape drift")

    if isinstance(paths, dict):
        authority = project.get("authority", {})
        for key in ("coordinator_checkout", "coordinator_review_checkout"):
            errors.extend(validate_checkout(str(paths.get(key, "")), authority, key))
        for key in ("implementation_checkout", "reviewer_checkout"):
            errors.extend(
                validate_checkout(
                    str(paths.get(key, "")), authority, key, "jellydev@jellybase-lan"
                )
            )
        for target_key, bridge_key in (
            ("coordinator_checkout", "implementation_bridge"),
            ("coordinator_review_checkout", "reviewer_bridge"),
        ):
            target = Path(str(paths.get(target_key, "")))
            bridge = Path(str(paths.get(bridge_key, "")))
            if not bridge.is_symlink() or bridge.resolve(strict=False) != target.resolve(strict=False):
                errors.append(f"local runtime bridge drift: {bridge} -> {target}")
        for target_key, bridge_key in (
            ("implementation_checkout", "implementation_bridge"),
            ("reviewer_checkout", "reviewer_bridge"),
        ):
            target = str(paths.get(target_key, ""))
            bridge = str(paths.get(bridge_key, ""))
            try:
                if resolve_remote_path(bridge) != target:
                    errors.append(f"remote runtime bridge drift: {bridge} -> {target}")
            except ControlPlaneError as exc:
                errors.append(str(exc))
        ssh_target = "jellydev@jellybase-lan"
        try:
            sandbox_runtime = str((boundary if isinstance(boundary, dict) else {}).get("sandbox_runtime", ""))
            if resolve_remote_path(sandbox_runtime, ssh_target) != sandbox_runtime:
                errors.append("review sandbox runtime path drift")
            tool_output = run_remote_fixed(
                [sandbox_runtime + "/flutter/bin/flutter", "--version", "--machine"],
                ssh_target,
                timeout=60,
            )
            installed = runtime.get("toolchain", {}).get("installed", {})
            if json.loads(tool_output).get("frameworkVersion") != installed.get("flutter"):
                errors.append("live review runtime Flutter version drift")
            dart_output = run_remote_fixed([sandbox_runtime + "/flutter/bin/dart", "--version"], ssh_target)
            if str(installed.get("dart")) not in dart_output:
                errors.append("live review runtime Dart version drift")
            boundary_data = boundary if isinstance(boundary, dict) else {}
            if run_remote_fixed(["hostname"], ssh_target) != boundary_data.get("remote_hostname"):
                errors.append("review remote hostname drift")
            machine_line = run_remote_fixed(["sha256sum", "/etc/machine-id"], ssh_target)
            machine_hash = machine_line.split(None, 1)[0] if machine_line else ""
            if "sha256:" + machine_hash != boundary_data.get("remote_machine_id_sha256"):
                errors.append("review remote machine identity drift")
            pin_path = Path(str(boundary_data.get("pinned_known_hosts_path", "")))
            if pin_path.is_symlink() or not pin_path.is_file() or stat.S_IMODE(pin_path.stat().st_mode) != 0o600:
                errors.append("review pinned host-key file mode/type drift")
            else:
                pin_probe = subprocess.run(
                    ["ssh-keygen", "-lf", str(pin_path)],
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=10,
                )
                if (
                    pin_probe.returncode != 0
                    or str(boundary_data.get("ssh_host_key_fingerprint", "")) not in pin_probe.stdout
                    or "ED25519" not in pin_probe.stdout
                ):
                    errors.append("review pinned host-key fingerprint drift")
            image_id = run_remote_fixed(
                ["docker", "image", "inspect", boundary_data.get("sandbox_image_digest", ""), "--format={{.Id}}"],
                ssh_target,
            )
            if image_id != boundary_data.get("sandbox_image_digest"):
                errors.append("review sandbox image digest drift")
            hash_code = (
                "from pathlib import Path;import hashlib,stat,sys;root=Path(sys.argv[1]);h=hashlib.sha256();"
                "entries=sorted(root.rglob('*'),key=lambda p:p.relative_to(root).as_posix().encode());"
                "\nfor p in entries:\n r=p.relative_to(root).as_posix().encode();m=p.lstat().st_mode;"
                "k,d=(b'D',b'') if stat.S_ISDIR(m) else ((b'F',p.read_bytes()) if stat.S_ISREG(m) else (_ for _ in ()).throw(SystemExit('non-regular project-state entry')));"
                "\n for part in (k,r,d): h.update(len(part).to_bytes(8,'big'));h.update(part)\n"
                "print('sha256:'+h.hexdigest())"
            )
            project_state_hash = run_remote_fixed(
                ["python3", "-c", hash_code, sandbox_runtime + "/project-state"],
                ssh_target,
            )
            if project_state_hash != boundary_data.get("project_state_sha256"):
                errors.append("review sandbox project-state hash drift")
            if boundary_data.get("project_state_commit") != authority.get("commit"):
                errors.append("review sandbox project-state commit drift")
        except (ControlPlaneError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            errors.append(f"review sandbox runtime discovery failed: {type(exc).__name__}")

        try:
            source_repo = ReviewRepository(
                paths["coordinator_checkout"],
                expected_commit=str(authority.get("commit", "")),
            )
            pubspec = yaml.safe_load(
                source_repo.git_show(str(authority.get("commit", "")), "app/pubspec.yaml")
            )
            dependencies = pubspec.get("dependencies", {}) if isinstance(pubspec, dict) else {}
            dev_dependencies = pubspec.get("dev_dependencies", {}) if isinstance(pubspec, dict) else {}
            if "flutter" not in dependencies or not ({"drift", "drift_flutter"} & set(dependencies)):
                errors.append("live stack discovery does not confirm Flutter plus Drift/data")
            if "flutter_test" not in dev_dependencies:
                errors.append("live stack discovery does not confirm Flutter test support")
        except (ReviewBoundaryError, OSError, yaml.YAMLError) as exc:
            errors.append(f"live stack discovery failed: {type(exc).__name__}")

        try:
            key_path = str(runtime.get("repository_auth", {}).get("jellybase_key_path", "")) + ".pub"
            fingerprint_output = run_remote_fixed(
                ["ssh-keygen", "-E", "sha256", "-lf", key_path], ssh_target
            )
            if str(runtime.get("repository_auth", {}).get("public_key_fingerprint", "")) not in fingerprint_output:
                errors.append("Jellybase repository-key fingerprint drift")
        except (ControlPlaneError, OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"Jellybase repository-key discovery failed: {type(exc).__name__}")

    try:
        with urlopen("http://jellyhome:18888/v1/default/banks", timeout=10) as response:  # nosec B310 - fixed LAN endpoint
            bank_payload = json.loads(response.read(1024 * 1024))
        bank_ids: set[str] = set()

        def collect_bank_ids(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"id", "bank_id", "name"} and isinstance(item, str):
                        bank_ids.add(item)
                    collect_bank_ids(item)
            elif isinstance(value, list):
                for item in value:
                    collect_bank_ids(item)

        collect_bank_ids(bank_payload)
        if "jellyssh-main" not in bank_ids:
            errors.append("live Hindsight discovery did not find jellyssh-main")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"live Hindsight bank discovery failed: {type(exc).__name__}")
    toolchain_data = runtime.get("toolchain", {})
    if isinstance(toolchain_data, dict):
        try:
            quality_rel = Path(str(toolchain_data.get("quality_gate_evidence", "")))
            if quality_rel.is_absolute() or ".." in quality_rel.parts:
                raise ControlPlaneError("quality evidence path is unsafe")
            quality_path = (control_root.parent / quality_rel).resolve()
            quality_path.relative_to(control_root.parent.resolve())
            if file_sha256(quality_path) != toolchain_data.get("quality_gate_evidence_sha256"):
                errors.append("Flutter quality evidence hash drift")
            quality = json.loads(quality_path.read_text(encoding="utf-8"))
            restricted = quality.get("restricted_controller", {})
            if (
                quality.get("project") != "jellyssh"
                or quality.get("expected_commit") != project.get("authority", {}).get("commit")
                or len(quality.get("findings") or []) != 4
                or restricted.get("sandbox_self_check") != "PASS"
                or restricted.get("dart_format") != "PASS-135-files-0-changed"
                or restricted.get("flutter_analyze") != "BLOCK"
                or restricted.get("flutter_test") != "BLOCK"
            ):
                errors.append("Flutter quality evidence contract drift")
        except (ControlPlaneError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Flutter quality evidence invalid: {type(exc).__name__}")
    board = runtime.get("board", {})
    board_root = Path.home() / ".hermes" / "kanban" / "boards" / str(board.get("slug", ""))
    if board.get("state") == "verified-empty":
        try:
            board_meta = json.loads((board_root / "board.json").read_text(encoding="utf-8"))
            if board_meta.get("slug") != board.get("slug") or board_meta.get("default_workdir") != board.get("default_workdir"):
                errors.append("board metadata drift")
            connection = sqlite3.connect(f"file:{board_root / 'kanban.db'}?mode=ro", uri=True)
            try:
                task_count = int(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
            finally:
                connection.close()
            if task_count != 0 or board.get("task_count") != 0:
                errors.append("JellySSH board must remain empty")
        except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
            errors.append(f"board evidence invalid: {exc}")
    try:
        global_config = load_yaml(Path.home() / ".hermes" / "config.yaml")
        global_kanban = global_config.get("kanban", {})
        if (
            global_kanban.get("auto_decompose") is not False
            or int(global_kanban.get("max_spawn", 0)) != 1
            or int(global_kanban.get("max_in_progress", 0)) != 1
            or (global_kanban.get("default_assignee") or "") != ""
            or (global_kanban.get("orchestrator_profile") or "") != ""
        ):
            errors.append("global conservative Kanban settings drift")
    except ControlPlaneError as exc:
        errors.append(str(exc))
    rollback = runtime.get("rollback", {})
    if isinstance(rollback, dict):
        for path_key, hash_key in (
            ("source_baseline_archive", "source_baseline_archive_sha256"),
            ("current_target_profiles_archive", "current_target_profiles_archive_sha256"),
        ):
            try:
                if file_sha256(Path(str(rollback.get(path_key, "")))) != rollback.get(hash_key):
                    errors.append(f"rollback archive hash drift: {path_key}")
            except OSError as exc:
                errors.append(f"rollback archive unavailable: {path_key}: {type(exc).__name__}")
    if runtime.get("state") == "setup-verified-routing-blocked":
        profile_states = {
            role: value.get("state") if isinstance(value, dict) else None
            for role, value in (profile_specs or {}).items()
        } if isinstance(profile_specs, dict) else {}
        if (
            not isinstance(boundary, dict)
            or boundary.get("routing_state") != "verified"
            or profile_states.get("implementation") != "verified"
            or profile_states.get("reviewer") != "verified"
            or runtime.get("board", {}).get("state") != "verified-empty"
        ):
            errors.append("setup-verified state lacks verified profiles, reviewer route, or empty board evidence")
    return errors


def scan(project_path: Path = DEFAULT_PROJECT, control_root: Path = CONTROL_ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    schema_path = control_root / "schemas" / "project-skill-profile.schema.json"
    catalog_path = control_root / "catalog.yaml"
    try:
        project = load_yaml(project_path)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        validation_errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(project),
            key=lambda err: list(err.absolute_path),
        )
        errors.extend(
            f"project schema {'.'.join(map(str, err.absolute_path)) or '<root>'}: {err.message}"
            for err in validation_errors
        )
        catalog = load_yaml(catalog_path)
    except (ControlPlaneError, OSError, ValueError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "skills": {}, "project": None}

    try:
        actual_manifest_path = project_path.resolve().relative_to(control_root.parent.resolve()).as_posix()
    except ValueError:
        errors.append("project manifest is outside the control-plane repository")
        actual_manifest_path = ""
    if project.get("authority", {}).get("project_manifest_path") != actual_manifest_path:
        errors.append("project manifest authority path does not match the scanned manifest")

    declared_skills: dict[str, dict[str, Any]] = {}
    descriptor_docs: dict[tuple[str, str], dict[str, Any]] = {}
    for section, kind in (("releases", "core_release"), ("packs", "capability_pack")):
        entries = catalog.get(section)
        if not isinstance(entries, list):
            errors.append(f"catalog {section} must be a list")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"catalog {section} entry is not a mapping")
                continue
            try:
                descriptor_path = _resolve_descriptor(control_root, entry)
                doc, found = validate_descriptor(control_root, descriptor_path)
                errors.extend(found)
            except ControlPlaneError as exc:
                errors.append(str(exc))
                continue
            key = (str(doc.get("name", "")), str(doc.get("version", "")))
            if entry.get("bundle_sha256") != doc.get("bundle_sha256"):
                errors.append(f"catalog hash does not match descriptor for {key[0]}@{key[1]}")
            if entry.get("manifest_sha256") != doc.get("manifest_sha256"):
                errors.append(f"catalog manifest hash does not match descriptor for {key[0]}@{key[1]}")
            descriptor_docs[key] = doc
            for skill in doc.get("skills") or []:
                name = str(skill.get("name", ""))
                if name in declared_skills:
                    errors.append(f"shared skill shadowing: {name}")
                declared_skills[name] = {
                    "layer": kind,
                    "owner": doc.get("name"),
                    "version": doc.get("version"),
                    "bundle_sha256": skill.get("bundle_sha256"),
                }

    layers = project.get("skill_layers", {})
    refs = [layers.get("core_release")] + list(layers.get("capability_packs") or [])
    active_artifacts: set[str] = set()
    seen_refs: set[tuple[str, str]] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            errors.append("project release reference is not a mapping")
            continue
        key = (str(ref.get("name", "")), str(ref.get("version", "")))
        if key in seen_refs:
            errors.append(f"duplicate project artifact reference {key[0]}@{key[1]}")
        seen_refs.add(key)
        active_artifacts.add(f"{key[0]}@{key[1]}")
        if is_zero_hash(ref.get("bundle_sha256")):
            errors.append(f"project uses a zero hash for {key[0]}@{key[1]}")
        doc = descriptor_docs.get(key)
        if doc is None:
            errors.append(f"project references missing catalog artifact {key[0]}@{key[1]}")
        elif ref.get("bundle_sha256") != doc.get("bundle_sha256"):
            errors.append(f"project hash does not match catalog for {key[0]}@{key[1]}")
        elif ref.get("manifest_sha256") != doc.get("manifest_sha256"):
            errors.append(f"project manifest hash does not match catalog for {key[0]}@{key[1]}")

    project_dir = project_path.parent
    project_slug = str(project.get("project", {}).get("slug", ""))
    seen_overlays: set[str] = set()
    for overlay in layers.get("project_overlays") or []:
        name = str(overlay.get("name", ""))
        if name in seen_overlays:
            errors.append(f"duplicate project overlay: {name}")
        seen_overlays.add(name)
        if not name.startswith(project_slug + "-"):
            errors.append(f"project overlay is not project-prefixed: {name}")
        if is_zero_hash(overlay.get("bundle_sha256")):
            errors.append(f"project overlay uses a zero hash: {name}")
        for artifact in overlay.get("tested_against") or []:
            if artifact not in active_artifacts:
                errors.append(f"overlay {name} tested_against unknown artifact {artifact}")
        declared_path = Path(str(overlay.get("path", "")))
        repository_root = control_root.parent.resolve()
        if declared_path.is_absolute() or ".." in declared_path.parts:
            errors.append(f"project overlay path is unsafe: {name}")
            continue
        candidate = (repository_root / declared_path).resolve(strict=False)
        try:
            candidate.relative_to(repository_root)
        except ValueError:
            errors.append(f"project overlay path escapes repository authority: {name}")
            continue
        if name in declared_skills:
            errors.append(f"project overlay shadows shared skill: {name}")
            continue
        try:
            actual = tree_hash(candidate)
        except ControlPlaneError as exc:
            errors.append(str(exc))
            continue
        if actual != overlay.get("bundle_sha256"):
            errors.append(f"project overlay hash drift for {name}: expected {overlay.get('bundle_sha256')}, got {actual}")
        declared_skills[name] = {
            "layer": "project_overlay",
            "owner": project.get("project", {}).get("slug"),
            "version": overlay.get("version"),
            "bundle_sha256": actual,
        }

    for bundle, names in (layers.get("bundles") or {}).items():
        for name in names or []:
            if name not in declared_skills:
                errors.append(f"bundle {bundle} references unknown skill {name}")

    profile_names = {
        str(binding.get("name", ""))
        for binding in (project.get("profiles") or {}).values()
        if isinstance(binding, dict)
    }
    bundle_names = set((layers.get("bundles") or {}).keys())
    implementation_workspace = project.get("profiles", {}).get("implementation", {}).get("workspace")
    reviewer_workspace = project.get("profiles", {}).get("reviewer", {}).get("workspace")
    if implementation_workspace == reviewer_workspace:
        errors.append("implementation and reviewer workspaces must not be shared")
    for role, binding in (project.get("profiles") or {}).items():
        workspace = str(binding.get("workspace", "")) if isinstance(binding, dict) else ""
        if not Path(workspace).is_absolute() or ".." in Path(workspace).parts:
            errors.append(f"profile {role} workspace must be an absolute non-traversing path")
        model = binding.get("model", {}).get("model", "") if isinstance(binding, dict) else ""
        if "latest" in str(model).lower():
            errors.append(f"profile {role} uses a floating model alias")
    for expert, binding in (project.get("expert_policy") or {}).items():
        if expert == "risk_levels" or not isinstance(binding, dict):
            continue
        if binding.get("profile") not in profile_names:
            errors.append(f"expert {expert} references unknown profile {binding.get('profile')}")
        if binding.get("bundle") not in bundle_names:
            errors.append(f"expert {expert} references unknown bundle {binding.get('bundle')}")
        if "latest" in str(binding.get("model", {}).get("model", "")).lower():
            errors.append(f"expert {expert} uses a floating model alias")
    ui_binding = project.get("expert_policy", {}).get("ui", {})
    if (
        ui_binding.get("profile") != project.get("profiles", {}).get("reviewer", {}).get("name")
        or ui_binding.get("model") != {
            "provider": "openrouter",
            "model": "google/gemini-3.1-pro-preview",
            "fallback": "block",
        }
        or ui_binding.get("bundle") != "ui-review"
    ):
        errors.append("conditional UI expert route must use the exact Gemini controller override and UI bundle")

    project_state = project.get("project", {}).get("state")
    if project_state in {"verified", "routable"}:
        non_verified = [
            role for role, binding in (project.get("profiles") or {}).items()
            if binding.get("state") not in {"verified", "routable"}
        ]
        if non_verified:
            errors.append(f"{project_state} project has unverified profiles: {', '.join(non_verified)}")

    runtime_path = project_dir / "runtime.yaml"
    try:
        errors.extend(validate_runtime(runtime_path, project, control_root, declared_skills))
    except ControlPlaneError as exc:
        errors.append(str(exc))

    if project.get("promotion", {}).get("candidate_routable") is not False:
        errors.append("candidate_routable must remain false before a separate promotion gate")
    if project.get("project", {}).get("state") == "routable":
        errors.append("Phase 2 control plane structurally forbids a routable project state")

    return {
        "ok": not errors,
        "project": project.get("project", {}).get("slug"),
        "project_state": project.get("project", {}).get("state"),
        "hash_algorithm": HASH_ALGORITHM,
        "errors": errors,
        "warnings": warnings,
        "skills": declared_skills,
        "source_digests": {
            "project_manifest": file_sha256_or_none(project_path),
            "runtime_manifest": file_sha256_or_none(runtime_path),
            "catalog": file_sha256_or_none(catalog_path),
        },
    }


def plan(project_path: Path = DEFAULT_PROJECT, control_root: Path = CONTROL_ROOT) -> dict[str, Any]:
    result = scan(project_path, control_root)
    actions: list[dict[str, str]] = []
    blockers: list[str] = list(result["errors"])
    if result.get("project") is None:
        return {
            "ok": False,
            "project": None,
            "project_state": None,
            "actions": actions,
            "blockers": blockers or [f"project manifest unavailable: {project_path}"],
        }
    project = load_yaml(project_path)
    try:
        runtime = load_yaml(project_path.parent / "runtime.yaml")
    except ControlPlaneError as exc:
        runtime = {}
        if str(exc) not in blockers:
            blockers.append(str(exc))
    hermes_home = Path.home() / ".hermes"
    for role in ("implementation", "reviewer"):
        profile = project.get("profiles", {}).get(role, {})
        name = str(profile.get("name", ""))
        profile_dir = hermes_home / "profiles" / name
        if profile_dir.is_dir():
            actions.append({"state": "present", "action": f"verify profile {name}"})
        else:
            actions.append({"state": "pending", "action": f"create isolated profile {name}"})
    paths = runtime.get("paths", {})
    for key in ("coordinator_checkout", "coordinator_review_checkout"):
        value = Path(str(paths.get(key, "")))
        actions.append({"state": "present" if value.is_dir() else "pending", "action": f"verify local {key} {value}"})
    auth = runtime.get("repository_auth", {})
    if auth.get("registration_state") != "verified":
        blockers.append("Jellybase repository deploy key is not registered and verified")
    toolchain = runtime.get("toolchain", {})
    if toolchain.get("dispatch_state") != "verified":
        blockers.append("selected-ticket Flutter/Android quality gate is not verified; development dispatch must remain disabled")
    boundary = runtime.get("review_boundary", {})
    if boundary.get("routing_state") != "verified":
        blockers.append("reviewer structured-result route is not verified; native Kanban tool injection remains prohibited")
    pending_decisions = [
        item.get("id", "unknown")
        for item in runtime.get("governance_decisions", [])
        if isinstance(item, dict) and item.get("state") != "independently-reviewed"
    ]
    if pending_decisions:
        blockers.append("governance decisions await independent review: " + ", ".join(pending_decisions))
    board = runtime.get("board", {})
    board_slug = str(board.get("slug", ""))
    board_dir = hermes_home / "kanban" / "boards" / board_slug
    actions.append({"state": "present" if board_dir.is_dir() else "pending", "action": f"create empty board {board_slug}"})
    return {"ok": not blockers, "project": result.get("project"), "actions": actions, "blockers": blockers}


def render_markdown(result: dict[str, Any], plan_result: dict[str, Any]) -> str:
    lines = [
        f"# Skill Control Plane status: {result.get('project') or 'unknown'}",
        "",
        f"- Manifest validation: {'PASS' if result.get('ok') else 'BLOCK'}",
        f"- Project state: `{result.get('project_state')}`",
        f"- Governed skills: {len(result.get('skills') or {})}",
        f"- Routable now: `false`",
        "",
        "## Actions",
        "",
    ]
    for item in plan_result.get("actions", []):
        lines.append(f"- [{item['state']}] {item['action']}")
    lines.extend(["", "## Blockers", ""])
    blockers = plan_result.get("blockers") or []
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- None at the manifest/control-plane layer; live smoke evidence is still required.")
    lines.extend(["", "## Skill layers", ""])
    for name, item in sorted((result.get("skills") or {}).items()):
        lines.append(f"- `{name}` — {item['layer']} / {item['owner']}@{item['version']}")
    lines.append("")
    return "\n".join(lines)


def render_status_json(result: dict[str, Any], plan_result: dict[str, Any]) -> str:
    payload = {
        "schema_version": 1,
        "project": result.get("project"),
        "manifest_ok": bool(result.get("ok")),
        "routable": False,
        "project_state": result.get("project_state"),
        "source_digests": result.get("source_digests", {}),
        "skills": result.get("skills", {}),
        "actions": plan_result.get("actions", []),
        "blockers": plan_result.get("blockers", []),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_generated(path: Path, content: str) -> None:
    generated = (CONTROL_ROOT / "generated").resolve()
    generated.mkdir(parents=True, exist_ok=True)
    target = path.resolve(strict=False)
    if target.parent != generated or target.suffix not in {".md", ".json"}:
        raise ControlPlaneError("status output must be a direct .md or .json child of skills-control-plane/generated")
    if path.is_symlink():
        raise ControlPlaneError("status output cannot be a symlink")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=generated, delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target)
        directory_fd = os.open(generated, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _emit(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    print("PASS" if value.get("ok") else "BLOCK")
    for key in ("errors", "warnings", "blockers"):
        for item in value.get(key) or []:
            print(f"{key[:-1].upper()}: {item}")
    for item in value.get("actions") or []:
        print(f"{item['state'].upper()}: {item['action']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    sub.add_parser("verify")
    sub.add_parser("audit")
    sub.add_parser("plan")
    init = sub.add_parser("project-init")
    init.add_argument("--dry-run", action="store_true")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--output", type=Path)
    status_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)

    if args.command in {"scan", "verify", "audit"}:
        result = scan(args.project)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
    if args.command == "plan":
        result = plan(args.project)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
    if args.command == "project-init":
        if not args.dry_run:
            print("BLOCK: project-init requires --dry-run; apply is deliberately not implemented in Phase 2", file=sys.stderr)
            return 2
        result = plan(args.project)
        _emit(result, args.json)
        return 0 if result["ok"] else 1
    result = scan(args.project)
    plan_result = plan(args.project)
    rendered = render_status_json(result, plan_result) if args.format == "json" else render_markdown(result, plan_result)
    if args.output:
        try:
            write_generated(args.output, rendered)
        except ControlPlaneError as exc:
            print(f"BLOCK: {exc}", file=sys.stderr)
            return 2
        print(args.output.resolve())
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0 if result.get("ok") and not plan_result.get("blockers") else 1


if __name__ == "__main__":
    raise SystemExit(main())
