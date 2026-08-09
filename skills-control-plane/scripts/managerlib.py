#!/usr/bin/env python3
"""Generic, approval-bound Skills Manager and project setup primitives."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import struct
import subprocess
import tempfile
from typing import Any

import jsonschema
import yaml


class ManagerError(RuntimeError):
    pass


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SECRET_KEY_RE = re.compile(r"(?:^|[._-])(api[_-]?key|password|passphrase|private[_-]?key|secret|token)(?:$|[._-])", re.I)
_SECRET_FILE_RE = re.compile(
    r"(?i)^(?:\.env(?:\..*)?|auth\.json|credentials?(?:\..*)?|secrets?(?:\..*)?|id_(?:rsa|ed25519)|.*private[-_.]?key.*)$"
)
_SECRET_CONTENT_RE = re.compile(
    rb"(?i)(?:-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|(?:api[_-]?key|token|password|passphrase)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{20,})"
)
_PROFILE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_ALLOWED_ACTIONS = {
    "write-managed-file",
    "create-profile",
    "set-profile-config",
    "materialize-tree",
    "create-empty-board",
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def document_digest(document: dict[str, Any], digest_field: str) -> str:
    payload = copy.deepcopy(document)
    payload.pop(digest_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _assert_regular_input(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ManagerError(f"{label} cannot be a symlink: {path}")
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise ManagerError(f"{label} is unavailable: {path}") from exc
    if not stat.S_ISREG(mode):
        raise ManagerError(f"{label} must be a regular file: {path}")


def _load_document(path: Path, label: str) -> dict[str, Any]:
    _assert_regular_input(path, label)
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ManagerError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ManagerError(f"{label} root must be an object: {path}")
    return value


def _load_schema(control_root: Path, name: str) -> dict[str, Any]:
    path = control_root / "schemas" / name
    value = _load_document(path, "manager schema")
    try:
        jsonschema.Draft202012Validator.check_schema(value)
    except jsonschema.SchemaError as exc:
        raise ManagerError(f"invalid manager schema: {name}") from exc
    return value


def _validate(document: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'.'.join(map(str, item.absolute_path)) or '<root>'}: {item.message}" for item in errors[:20]
        )
        raise ManagerError(f"{label} schema validation failed: {detail}")


def _reject_secret_keys(value: Any, path: str = "<root>") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                raise ManagerError(f"secret-bearing key is forbidden in manager input: {path}.{key}")
            _reject_secret_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_keys(child, f"{path}[{index}]")
    elif isinstance(value, str) and _SECRET_CONTENT_RE.search(value.encode("utf-8")):
        raise ManagerError(f"secret-shaped value is forbidden in manager input: {path}")


def _contains_secret(value: Any) -> bool:
    try:
        _reject_secret_keys(value)
    except ManagerError:
        return True
    return False


def _zero_hash_paths(value: Any, path: str = "<root>") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).endswith("sha256") and child == "sha256:" + "0" * 64:
                found.append(child_path)
            found.extend(_zero_hash_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_zero_hash_paths(child, f"{path}[{index}]"))
    return found


def _safe_relative(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ManagerError(f"{label} must be a non-traversing relative path")
    return path


def _safe_absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ManagerError(f"{label} must be an absolute non-traversing path")
    return path


def _assert_under(path: Path, root: Path, label: str) -> None:
    try:
        if root.is_symlink():
            raise ManagerError(f"{label} authority root cannot be a symlink: {root}")
        resolved_root = root.resolve(strict=False)
        resolved_path = path.resolve(strict=False)
        relative = resolved_path.relative_to(resolved_root)
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ManagerError(f"{label} has a symlink ancestor: {current}")
    except ManagerError:
        raise
    except (OSError, ValueError) as exc:
        raise ManagerError(f"{label} escapes its authority root: {path}") from exc


def _git(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if check and completed.returncode != 0:
        raise ManagerError(f"git inspection failed for {repo}: {' '.join(args)}")
    return completed.stdout.strip()


def observe_repository(repo: Path) -> dict[str, Any]:
    if not repo.is_dir() or not (repo / ".git").exists():
        raise ManagerError(f"repository is not a Git checkout: {repo}")
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    changes = []
    for line in status.splitlines():
        if len(line) < 4:
            raise ManagerError(f"unparseable Git status entry in {repo}")
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        changes.append(value)
    return {
        "remote": _git(repo, "remote", "get-url", "origin"),
        "branch": _git(repo, "branch", "--show-current"),
        "commit": _git(repo, "rev-parse", "HEAD"),
        "clean": not changes,
        "changes": sorted(changes),
    }


def _file_observation(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ManagerError(f"managed target cannot be a symlink: {path}")
    if not path.exists():
        return {"state": "absent"}
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ManagerError(f"managed target is not a regular file: {path}")
    content = path.read_bytes()
    return {"state": "file", "sha256": bytes_digest(content), "mode": stat.S_IMODE(mode), "bytes": len(content)}


def tree_snapshot_from_mapping(files: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    digest = hashlib.sha256()
    ordered: dict[str, bytes] = {}
    for relative, content in sorted(files.items()):
        normalized = _safe_relative(relative, "managed tree member").as_posix()
        if any(_SECRET_FILE_RE.fullmatch(part) for part in Path(normalized).parts):
            raise ManagerError(f"managed tree contains a secret-shaped path: {normalized}")
        if _SECRET_CONTENT_RE.search(content):
            raise ManagerError(f"managed tree contains secret-shaped content: {normalized}")
        if normalized in ordered:
            raise ManagerError(f"duplicate managed tree member: {normalized}")
        ordered[normalized] = content
        path_bytes = normalized.encode("utf-8")
        digest.update(struct.pack(">Q", len(path_bytes)))
        digest.update(path_bytes)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return "sha256:" + digest.hexdigest(), ordered


def tree_snapshot(path: Path) -> tuple[str, dict[str, bytes]]:
    if path.is_symlink() or not path.is_dir():
        raise ManagerError(f"managed tree must be a real directory: {path}")
    files: dict[str, bytes] = {}
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        relative = child.relative_to(path).as_posix()
        if child.is_symlink():
            raise ManagerError(f"managed tree contains a symlink: {child}")
        mode = child.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ManagerError(f"managed tree contains a non-regular file: {child}")
        files[relative] = child.read_bytes()
    return tree_snapshot_from_mapping(files)


def _tree_observation(path: Path, *, capture: bool = False) -> dict[str, Any]:
    if path.is_symlink():
        raise ManagerError(f"managed tree cannot be a symlink: {path}")
    if not path.exists():
        return {"state": "absent"}
    digest, files = tree_snapshot(path)
    result: dict[str, Any] = {"state": "tree", "sha256": digest, "files": len(files)}
    if capture:
        result["content_b64"] = {
            name: base64.b64encode(content).decode("ascii") for name, content in files.items()
        }
    return result


def _write_tree(path: Path, files: dict[str, bytes]) -> None:
    if path.is_symlink():
        raise ManagerError(f"managed tree cannot be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{path.name}.", dir=path.parent))
    old: Path | None = None
    try:
        for name, content in sorted(files.items()):
            relative = _safe_relative(name, "managed tree member")
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(target, content, 0o600)
        if path.exists():
            old = Path(tempfile.mkdtemp(prefix=f".{path.name}.old.", dir=path.parent))
            old.rmdir()
            path.replace(old)
        temp.replace(path)
        if old is not None:
            shutil.rmtree(old)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
        if old is not None and old.exists() and not path.exists():
            old.replace(path)


def _atomic_write(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ManagerError(f"managed target cannot be a symlink: {path}")
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        temp.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


class HermesAdapter:
    """Runtime seam. Tests use a fake; live execution uses a subprocess adapter."""

    def profile_exists(self, name: str) -> bool:
        raise NotImplementedError

    def profile_observation(self, name: str) -> dict[str, Any]:
        return {"exists": self.profile_exists(name), "ownership": None}

    def board_exists(self, slug: str) -> bool:
        raise NotImplementedError

    def board_observation(self, slug: str) -> dict[str, Any]:
        return {"exists": self.board_exists(slug)}

    def profile_skill_root(self, name: str) -> Path:
        raise NotImplementedError

    def get_profile_config(self, name: str, key: str) -> Any:
        return None

    def create_profile(self, action: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete_profile(self, name: str) -> None:
        raise NotImplementedError

    def set_profile_config(self, action: dict[str, Any]) -> None:
        raise NotImplementedError

    def unset_profile_config(self, name: str, key: str) -> None:
        raise NotImplementedError

    def create_board(self, action: dict[str, Any]) -> None:
        raise NotImplementedError

    def archive_board(self, slug: str) -> None:
        raise NotImplementedError


class LiveHermesAdapter(HermesAdapter):
    def __init__(self, hermes_home: Path, hermes_bin: str = "hermes") -> None:
        self.hermes_home = hermes_home
        self.hermes_bin = hermes_bin

    def _run(self, args: list[str]) -> str:
        completed = subprocess.run(
            [self.hermes_bin, *args], check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        )
        if completed.returncode != 0:
            raise ManagerError(f"Hermes adapter command failed: {' '.join(args[:4])}")
        return completed.stdout.strip()

    def profile_exists(self, name: str) -> bool:
        return (self.hermes_home / "profiles" / name / "config.yaml").is_file()

    def profile_observation(self, name: str) -> dict[str, Any]:
        if not self.profile_exists(name):
            return {"exists": False, "ownership": None}
        marker = self.hermes_home / "profiles" / name / ".skills-manager-owner.json"
        ownership = None
        if marker.exists():
            if marker.is_symlink() or not marker.is_file():
                raise ManagerError(f"profile ownership marker is unsafe: {marker}")
            ownership = _load_document(marker, "profile ownership marker")
        return {"exists": True, "ownership": ownership}

    def board_exists(self, slug: str) -> bool:
        return (self.hermes_home / "kanban" / "boards" / slug / "board.json").is_file()

    def board_observation(self, slug: str) -> dict[str, Any]:
        root = self.hermes_home / "kanban" / "boards" / slug
        descriptor = root / "board.json"
        if not descriptor.exists():
            return {"exists": False}
        value = _load_document(descriptor, "board descriptor")
        database = root / "kanban.db"
        if database.is_symlink() or not database.is_file():
            raise ManagerError(f"board database is unavailable: {database}")
        uri = f"file:{database}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=5) as connection:
                task_count = int(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        except sqlite3.Error as exc:
            raise ManagerError(f"board database inspection failed: {slug}") from exc
        return {
            "exists": True,
            "name": value.get("name"),
            "description": value.get("description"),
            "default_workdir": value.get("default_workdir"),
            "task_count": task_count,
            "ownership": self._read_owner(root / ".skills-manager-owner.json", "board ownership marker"),
        }

    @staticmethod
    def _read_owner(path: Path, label: str) -> dict[str, Any] | None:
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise ManagerError(f"{label} is unsafe: {path}")
        return _load_document(path, label)

    def profile_skill_root(self, name: str) -> Path:
        return self.hermes_home / "profiles" / name / "skills"

    def get_profile_config(self, name: str, key: str) -> Any:
        if not self.profile_exists(name):
            return None
        output = self._run(["-p", name, "config", "get", key])
        try:
            return yaml.safe_load(output)
        except yaml.YAMLError:
            return output

    def create_profile(self, action: dict[str, Any]) -> None:
        params = action["parameters"]
        args = ["profile", "create", action["target"], "--clone-from", params["clone_from"], "--description", params["description"]]
        if params.get("no_skills"):
            args.append("--no-skills")
        args.append("--no-alias")
        self._run(args)
        marker = self.hermes_home / "profiles" / action["target"] / ".skills-manager-owner.json"
        try:
            _atomic_write(marker, canonical_json(params["ownership"]) + b"\n", 0o600)
        except Exception:
            self.delete_profile(action["target"])
            raise

    def delete_profile(self, name: str) -> None:
        self._run(["profile", "delete", "-y", name])

    def set_profile_config(self, action: dict[str, Any]) -> None:
        params = action["parameters"]
        value = json.dumps(params["value"], sort_keys=True) if isinstance(params["value"], (dict, list, bool)) else str(params["value"])
        self._run(["-p", action["target"], "config", "set", params["key"], value])

    def unset_profile_config(self, name: str, key: str) -> None:
        self._run(["-p", name, "config", "unset", key])

    def create_board(self, action: dict[str, Any]) -> None:
        params = action["parameters"]
        self._run([
            "kanban", "boards", "create", action["target"],
            "--name", params["name"], "--description", params["description"],
            "--default-workdir", params["default_workdir"],
        ])
        marker = self.hermes_home / "kanban" / "boards" / action["target"] / ".skills-manager-owner.json"
        try:
            _atomic_write(marker, canonical_json(params["ownership"]) + b"\n", 0o600)
        except Exception:
            self.archive_board(action["target"])
            raise

    def archive_board(self, slug: str) -> None:
        self._run(["kanban", "boards", "rm", slug])


def _declared_skill_sources(manifest: dict[str, Any], control_root: Path) -> dict[str, Path]:
    catalog = _load_document(control_root / "catalog.yaml", "skill catalog")
    _reject_secret_keys(catalog)
    sources: dict[str, Path] = {}

    def add(name: str, source: Path, expected_sha: str) -> None:
        _assert_under(source, control_root, "declared skill source")
        actual_sha, _ = tree_snapshot(source)
        if actual_sha != expected_sha:
            raise ManagerError(f"declared skill hash mismatch: {name}")
        if name in sources and sources[name].resolve() != source.resolve():
            raise ManagerError(f"declared skill is shadowed by multiple sources: {name}")
        sources[name] = source

    layers = manifest["skill_layers"]
    declarations = [("releases", layers["core_release"])] + [
        ("packs", item) for item in layers.get("capability_packs", [])
    ]
    for collection_name, declaration in declarations:
        matches = [
            item for item in catalog.get(collection_name, [])
            if isinstance(item, dict)
            and item.get("name") == declaration.get("name")
            and item.get("version") == declaration.get("version")
        ]
        if len(matches) != 1:
            raise ManagerError(
                f"declared skill layer is not uniquely registered: {declaration.get('name')}@{declaration.get('version')}"
            )
        catalog_item = matches[0]
        if catalog_item.get("bundle_sha256") != declaration.get("bundle_sha256"):
            raise ManagerError(f"declared layer bundle differs from catalog: {declaration.get('name')}")
        if catalog_item.get("manifest_sha256") != declaration.get("manifest_sha256"):
            raise ManagerError(f"declared layer manifest differs from catalog: {declaration.get('name')}")
        descriptor_path = control_root / _safe_relative(str(catalog_item["manifest"]), "layer manifest")
        _assert_under(descriptor_path, control_root, "layer manifest")
        descriptor = _load_document(descriptor_path, "layer manifest")
        _reject_secret_keys(descriptor)
        if descriptor.get("name") != declaration.get("name") or descriptor.get("version") != declaration.get("version"):
            raise ManagerError(f"layer descriptor identity mismatch: {declaration.get('name')}")
        for skill in descriptor.get("skills", []):
            if not isinstance(skill, dict):
                raise ManagerError("layer descriptor contains an invalid skill")
            source = descriptor_path.parent / _safe_relative(str(skill.get("path", "")), "layer skill path")
            add(str(skill.get("name", "")), source, str(skill.get("bundle_sha256", "")))

    for overlay in layers.get("project_overlays", []):
        source = control_root.parent / _safe_relative(str(overlay["path"]), "project overlay path")
        add(str(overlay["name"]), source, str(overlay["bundle_sha256"]))
    return sources


def _managed_file_action(action_id: str, target: Path, content: bytes, authority_root: Path) -> dict[str, Any]:
    _assert_under(target, authority_root, "managed file")
    before = _file_observation(target)
    return {
        "id": action_id,
        "kind": "write-managed-file",
        "target": str(target),
        "parameters": {
            "content_b64": base64.b64encode(content).decode("ascii"),
            "content_sha256": bytes_digest(content),
            "mode": 0o600,
            "authority_root": str(authority_root.resolve()),
        },
        "rollback": {"before": before},
    }


def build_project_plan(
    request_path: Path,
    control_root: Path,
    adapter: HermesAdapter,
    *,
    control_commit: str,
) -> dict[str, Any]:
    request = _load_document(request_path, "project setup request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "project-setup-request.schema.json"), "project setup request")
    if not re.fullmatch(r"[0-9a-f]{40}", control_commit):
        raise ManagerError("control commit must be a full lowercase SHA")

    slug = request["project"]["slug"]
    ownership = {"schema_version": 1, "owner": "skills-manager", "project": slug}
    repo = _safe_absolute(request["repository"]["path"], "repository path")
    contract_rel = _safe_relative(request["repository"]["contract_path"], "project contract path")
    contract_target = repo / contract_rel
    manifest = request["project_manifest"]
    _validate(manifest, _load_schema(control_root, "project-definition.schema.json"), "embedded project manifest")
    manifest_bytes = yaml.safe_dump(manifest, sort_keys=False, width=1000).encode("utf-8")
    observed = observe_repository(repo)
    managed_contract_only = (
        observed.get("changes") == [contract_rel.as_posix()]
        and contract_target.is_file()
        and not contract_target.is_symlink()
        and contract_target.read_bytes() == manifest_bytes
    )
    expected_repo = {
        "remote": request["repository"]["remote"],
        "branch": request["repository"]["branch"],
        "commit": request["repository"]["commit"],
        "clean": True,
    }
    blockers: list[str] = []
    authority = manifest.get("authority", {})
    expected_manifest_path = f"skills-control-plane/projects/{slug}/project.yaml"
    if manifest.get("project", {}).get("slug") != slug:
        blockers.append("project manifest slug does not match setup request")
    if manifest.get("project", {}).get("display_name") != request["project"]["display_name"]:
        blockers.append("project manifest display name does not match setup request")
    if manifest.get("project", {}).get("state") == "routable":
        blockers.append("project setup manifest must remain non-routable")
    runtime_manifest = request.get("runtime_manifest", {"schema_version": 1, "project": slug, "state": "proposed"})
    if str(runtime_manifest.get("project", slug)) != slug:
        blockers.append("runtime manifest project does not match setup request")
    if _runtime_is_routable(runtime_manifest):
        blockers.append("project setup runtime manifest must remain non-routable")
    for key in ("remote", "commit"):
        if authority.get(key) != request["repository"][key]:
            blockers.append(f"project manifest authority {key} does not match setup request")
    if authority.get("project_manifest_path") != expected_manifest_path:
        blockers.append("project manifest authority path does not match project slug")
    zero_hashes = _zero_hash_paths(manifest)
    if zero_hashes:
        blockers.append("project manifest contains zero authority hashes: " + ", ".join(zero_hashes))
    declared_profiles = {
        role: binding for role, binding in (manifest.get("profiles") or {}).items()
        if isinstance(binding, dict)
    }
    requested_profiles = {item["role"]: item for item in request["profiles"]}
    if set(declared_profiles) != set(requested_profiles):
        blockers.append("setup profile roles do not exactly match the project manifest")
    for role in sorted(set(declared_profiles) & set(requested_profiles)):
        declared = declared_profiles[role]
        requested = requested_profiles[role]
        if declared.get("name") != requested.get("name"):
            blockers.append(f"setup profile name does not match manifest: {role}")
        if declared.get("state") == "routable":
            blockers.append(f"setup profile binding must remain non-routable: {role}")
        expected_settings = {
            "model.provider": declared.get("model", {}).get("provider"),
            "model.default": declared.get("model", {}).get("model"),
            "model.fallback": declared.get("model", {}).get("fallback"),
            "terminal.cwd": declared.get("workspace"),
        }
        for key, expected in expected_settings.items():
            if requested.get("settings", {}).get(key) != expected:
                blockers.append(f"setup profile setting does not match manifest: {role} {key}")
    declared_profile_names = {
        str(binding.get("name")) for binding in declared_profiles.values() if isinstance(binding, dict)
    }
    reviewer_profile_names = {
        str(binding.get("name"))
        for binding in declared_profiles.values()
        if isinstance(binding, dict) and binding.get("reviewer_write_boundary") in {"proposed", "verified"}
    }
    declared_bundles = set((manifest.get("skill_layers", {}).get("bundles") or {}).keys())
    for expert, binding in sorted((manifest.get("expert_policy") or {}).items()):
        if expert == "risk_levels" or not isinstance(binding, dict):
            continue
        profile_name = str(binding.get("profile", ""))
        if profile_name not in declared_profile_names:
            blockers.append(f"expert binding profile is not declared for this project: {expert}")
        if profile_name not in reviewer_profile_names:
            blockers.append(f"expert binding profile is not a declared reviewer profile: {expert}")
        if str(binding.get("bundle", "")) not in declared_bundles:
            blockers.append(f"expert binding bundle is not declared for this project: {expert}")
    handoff = manifest.get("execution_policy", {}).get("implementation_review_handoff", {})
    if isinstance(handoff, dict):
        target_profile = str(handoff.get("target_profile", ""))
        if target_profile not in declared_profile_names:
            blockers.append("implementation review handoff target profile is not declared for this project")
        if target_profile not in reviewer_profile_names:
            blockers.append("implementation review handoff target profile is not a declared reviewer profile")
        if str(handoff.get("target_bundle", "")) not in declared_bundles:
            blockers.append("implementation review handoff target bundle is not declared for this project")
    for key, expected in expected_repo.items():
        if key == "clean" and managed_contract_only:
            continue
        if observed.get(key) != expected:
            label = "not clean" if key == "clean" else f"{key} mismatch"
            blockers.append(f"repository {label}: expected {expected!r}, observed {observed.get(key)!r}")

    actions: list[dict[str, Any]] = []
    preconditions: list[dict[str, Any]] = [
        {"kind": "authority", "target": str(control_root.parent.resolve()), "expected": control_commit},
        {"kind": "git", "target": str(repo), "expected": observed},
    ]
    next_id = 1

    def add(action: dict[str, Any]) -> None:
        nonlocal next_id
        actions.append(action)
        next_id += 1

    control_projects = control_root / "projects"
    control_target = control_projects / slug / "project.yaml"
    runtime_target = control_projects / slug / "runtime.yaml"

    runtime_bytes = yaml.safe_dump(request.get("runtime_manifest", {"schema_version": 1, "project": slug, "state": "proposed"}), sort_keys=False, width=1000).encode("utf-8")

    if request["effects"]["write_control_manifest"]:
        for target, content in ((control_target, manifest_bytes), (runtime_target, runtime_bytes)):
            action = _managed_file_action(f"a{next_id:03d}", target, content, control_projects)
            preconditions.append({"kind": "file", "target": str(target), "expected": action["rollback"]["before"]})
            add(action)
    if request["effects"]["write_project_contract"]:
        action = _managed_file_action(f"a{next_id:03d}", contract_target, manifest_bytes, repo)
        preconditions.append({"kind": "file", "target": str(contract_target), "expected": action["rollback"]["before"]})
        add(action)

    if request["effects"]["create_profiles"]:
        seen_names: set[str] = set()
        for profile in sorted(request["profiles"], key=lambda item: item["name"]):
            name = profile["name"]
            if name in seen_names:
                blockers.append(f"duplicate profile name: {name}")
                continue
            seen_names.add(name)
            clone_from = profile["clone_from"]
            baseline_observation = adapter.profile_observation(clone_from)
            baseline_exists = bool(baseline_observation.get("exists"))
            if not any(item["kind"] == "profile" and item["target"] == clone_from for item in preconditions):
                preconditions.append({"kind": "profile", "target": clone_from, "expected": baseline_observation})
            if not baseline_exists:
                blockers.append(f"profile baseline does not exist: {clone_from}")
            observation = adapter.profile_observation(name)
            exists = bool(observation.get("exists"))
            preconditions.append({"kind": "profile", "target": name, "expected": observation})
            if exists and observation.get("ownership") != ownership:
                blockers.append(f"existing profile is not owned by this project setup: {name}")
            actions.append({
                "id": f"a{next_id:03d}", "kind": "create-profile", "target": name,
                "parameters": {
                    "clone_from": profile["clone_from"], "description": profile["description"],
                    "no_skills": profile["no_skills"], "ownership": ownership,
                },
                "rollback": {"created": not exists},
            })
            next_id += 1
            for key, value in sorted(profile["settings"].items()):
                current_value = adapter.get_profile_config(name, key) if exists else None
                if _contains_secret(current_value):
                    blockers.append(f"existing profile config contains a secret-shaped value: {name} {key}")
                    current_value = "[REDACTED]"
                preconditions.append({
                    "kind": "profile-config", "target": f"{name}#{key}", "expected": current_value,
                })
                actions.append({
                    "id": f"a{next_id:03d}", "kind": "set-profile-config", "target": name,
                    "parameters": {"key": key, "value": value},
                    "rollback": {"previous": current_value},
                })
                next_id += 1

    if request["effects"]["materialize_profile_skills"]:
        skill_sources = _declared_skill_sources(manifest, control_root)
        bundles = manifest["skill_layers"]["bundles"]
        for profile in sorted(request["profiles"], key=lambda item: item["name"]):
            role = profile["role"]
            binding = manifest["profiles"].get(role)
            if not isinstance(binding, dict):
                blockers.append(f"profile role has no manifest binding: {role}")
                continue
            bundle_name = binding.get("bundle")
            skill_names = bundles.get(bundle_name)
            if not isinstance(skill_names, list):
                blockers.append(f"profile bundle is not declared: {role}/{bundle_name}")
                continue
            observation = adapter.profile_observation(profile["name"])
            if not any(
                item["kind"] == "profile" and item["target"] == profile["name"]
                for item in preconditions
            ):
                preconditions.append({"kind": "profile", "target": profile["name"], "expected": observation})
            if observation.get("exists"):
                expected_owner = {"schema_version": 1, "owner": "skills-manager", "project": slug}
                if observation.get("ownership") != expected_owner:
                    blockers.append(f"profile skill target is not project-owned: {profile['name']}")
                    continue
            elif not request["effects"]["create_profiles"]:
                blockers.append(f"profile skill target does not exist: {profile['name']}")
                continue
            authority = adapter.profile_skill_root(profile["name"])
            for skill_name in sorted(set(str(item) for item in skill_names)):
                source = skill_sources.get(skill_name)
                if source is None:
                    blockers.append(f"bundle skill has no declared source: {bundle_name}/{skill_name}")
                    continue
                action, target_precondition = _materialize_tree_action(
                    f"a{next_id:03d}", source, authority / skill_name, authority
                )
                actions.append(action)
                preconditions.extend([
                    target_precondition,
                    {"kind": "tree", "target": str(source), "expected": _tree_observation(source)},
                ])
                next_id += 1

    if request["effects"]["create_empty_board"]:
        board = request["board"]
        observation = adapter.board_observation(board["slug"])
        preconditions.append({"kind": "board", "target": board["slug"], "expected": observation})
        if observation.get("exists"):
            desired_board = {
                "exists": True,
                "name": board["name"],
                "description": board["description"],
                "default_workdir": board["default_workdir"],
                "task_count": 0,
                "ownership": ownership,
            }
            if observation != desired_board:
                blockers.append("existing board is not an exact empty setup board")
        actions.append({
            "id": f"a{next_id:03d}", "kind": "create-empty-board", "target": board["slug"],
            "parameters": {
                "name": board["name"], "description": board["description"],
                "default_workdir": board["default_workdir"], "ownership": ownership,
            },
            "rollback": {"created": not observation.get("exists", False)},
        })

    unique_preconditions: dict[tuple[str, str], dict[str, Any]] = {}
    for item in preconditions:
        key = (item["kind"], item["target"])
        if key in unique_preconditions and unique_preconditions[key] != item:
            raise ManagerError(f"conflicting plan preconditions: {item['kind']} {item['target']}")
        unique_preconditions[key] = item
    preconditions = list(unique_preconditions.values())

    plan: dict[str, Any] = {
        "schema_version": 1,
        "kind": "project-setup",
        "project": slug,
        "created_from": {"request_sha256": bytes_digest(request_path.read_bytes()), "control_commit": control_commit},
        "preconditions": sorted(preconditions, key=lambda item: (item["kind"], item["target"])),
        "actions": actions,
        "blockers": sorted(set(blockers)),
        "plan_sha256": "sha256:" + "0" * 64,
    }
    plan["plan_sha256"] = document_digest(plan, "plan_sha256")
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "manager plan")
    _validate_plan_semantics(plan)
    return plan


def _recheck_preconditions(plan: dict[str, Any], adapter: HermesAdapter) -> None:
    for item in plan["preconditions"]:
        kind, target, expected = item["kind"], item["target"], item["expected"]
        if kind == "git":
            actual = observe_repository(Path(target))
        elif kind == "file":
            actual = _file_observation(Path(target))
        elif kind == "tree":
            actual = _tree_observation(Path(target))
        elif kind == "profile":
            actual = adapter.profile_observation(target)
        elif kind == "profile-config":
            if "#" not in target:
                raise ManagerError("invalid profile-config precondition target")
            profile, key = target.split("#", 1)
            actual = adapter.get_profile_config(profile, key)
        elif kind == "board":
            actual = adapter.board_observation(target)
        elif kind == "authority":
            actual = _git(Path(target), "rev-parse", "HEAD")
        else:
            continue
        if actual != expected:
            raise ManagerError(f"apply precondition drift: {kind} {target}")


def _journal_digest(journal: dict[str, Any]) -> str:
    return document_digest(journal, "journal_sha256")


def _write_journal(path: Path, journal: dict[str, Any], control_root: Path) -> None:
    journal["journal_sha256"] = _journal_digest(journal)
    _validate(journal, _load_schema(control_root, "manager-journal.schema.json"), "manager journal")
    _atomic_write(path, json.dumps(journal, indent=2, sort_keys=True).encode("utf-8") + b"\n", 0o600)


def _validate_plan_semantics(plan: dict[str, Any]) -> None:
    actions = plan.get("actions") or []
    expected_ids = [f"a{index:03d}" for index in range(1, len(actions) + 1)]
    actual_ids = [action.get("id") for action in actions]
    if actual_ids != expected_ids:
        raise ManagerError("manager action IDs must be unique, ordered, and contiguous")
    preconditions = {(item.get("kind"), item.get("target")) for item in plan.get("preconditions") or []}
    if len(preconditions) != len(plan.get("preconditions") or []):
        raise ManagerError("manager plan contains duplicate preconditions")
    authority = [item for item in plan.get("preconditions") or [] if item.get("kind") == "authority"]
    if len(authority) != 1 or authority[0].get("expected") != plan.get("created_from", {}).get("control_commit"):
        raise ManagerError("manager plan lacks its exact control-plane commit precondition")
    for action in actions:
        kind, target, params = action["kind"], action["target"], action["parameters"]
        if kind not in _ALLOWED_ACTIONS:
            raise ManagerError(f"unsupported manager action: {kind}")
        if not isinstance(params, dict):
            raise ManagerError(f"manager action parameters must be an object: {action['id']}")
        if kind == "write-managed-file":
            if set(params) != {"content_b64", "content_sha256", "mode", "authority_root"}:
                raise ManagerError("write-managed-file parameters are not exact")
            authority = _safe_absolute(params["authority_root"], "managed file authority")
            path = _safe_absolute(target, "managed file target")
            _assert_under(path, authority, "managed file")
            try:
                content = base64.b64decode(params["content_b64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise ManagerError("managed file content is not valid base64") from exc
            if bytes_digest(content) != params["content_sha256"] or params["mode"] not in {0o600, 0o644}:
                raise ManagerError("managed file content hash or mode is invalid")
            if ("file", target) not in preconditions:
                raise ManagerError("managed file action lacks an exact precondition")
        elif kind == "materialize-tree":
            if set(params) != {"source_root", "source_tree_sha256", "authority_root"}:
                raise ManagerError("materialize-tree parameters are not exact")
            source = _safe_absolute(params["source_root"], "managed tree source")
            authority = _safe_absolute(params["authority_root"], "managed tree authority")
            target_path = _safe_absolute(target, "managed tree target")
            _assert_under(target_path, authority, "managed tree")
            if not _SHA256_RE.fullmatch(str(params["source_tree_sha256"])):
                raise ManagerError("managed tree source hash is invalid")
            if ("tree", target) not in preconditions or ("tree", str(source)) not in preconditions:
                raise ManagerError("managed tree action lacks source or target preconditions")
        elif kind == "create-profile":
            if set(params) != {"clone_from", "description", "no_skills", "ownership"}:
                raise ManagerError("create-profile parameters are not exact")
            if not _PROFILE_NAME_RE.fullmatch(target) or not _PROFILE_NAME_RE.fullmatch(str(params["clone_from"])):
                raise ManagerError("profile names are invalid")
            if params["ownership"] != {"schema_version": 1, "owner": "skills-manager", "project": plan["project"]}:
                raise ManagerError("profile ownership marker is not exact")
            if not isinstance(params["description"], str) or not params["description"] or not isinstance(params["no_skills"], bool):
                raise ManagerError("profile creation parameters are invalid")
            if ("profile", target) not in preconditions:
                raise ManagerError("profile action lacks an exact precondition")
        elif kind == "set-profile-config":
            if set(params) != {"key", "value"}:
                raise ManagerError("set-profile-config parameters are not exact")
            key = str(params["key"])
            if _SECRET_KEY_RE.search(key) or not re.fullmatch(r"(model|terminal|memory|hindsight|skills|kanban|mcp_servers)\.[A-Za-z0-9_.-]+", key):
                raise ManagerError("profile configuration key is not allowlisted")
            if ("profile-config", f"{target}#{key}") not in preconditions:
                raise ManagerError("profile configuration action lacks an exact precondition")
        elif kind == "create-empty-board":
            if set(params) != {"name", "description", "default_workdir", "ownership"}:
                raise ManagerError("create-empty-board parameters are not exact")
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", target):
                raise ManagerError("board slug is invalid")
            if params["ownership"] != {"schema_version": 1, "owner": "skills-manager", "project": plan["project"]}:
                raise ManagerError("board ownership marker is not exact")
            _safe_absolute(params["default_workdir"], "board default workdir")
            if ("board", target) not in preconditions:
                raise ManagerError("board action lacks an exact precondition")


def _apply_action(action: dict[str, Any], adapter: HermesAdapter) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, str]:
    kind, target, params = action["kind"], action["target"], action["parameters"]
    if kind not in _ALLOWED_ACTIONS:
        raise ManagerError(f"unsupported manager action: {kind}")
    if kind == "write-managed-file":
        path = Path(target)
        authority = Path(params["authority_root"])
        _assert_under(path, authority, "managed file")
        before = _file_observation(path)
        content = base64.b64decode(params["content_b64"], validate=True)
        if bytes_digest(content) != params["content_sha256"]:
            raise ManagerError(f"managed content hash mismatch: {target}")
        if before.get("sha256") == params["content_sha256"]:
            return "noop", before, before, "exact managed bytes already present"
        backup = dict(before)
        if before["state"] == "file":
            backup["content_b64"] = base64.b64encode(path.read_bytes()).decode("ascii")
        _atomic_write(path, content, int(params["mode"]))
        return "applied", backup, _file_observation(path), "managed file written atomically"
    if kind == "create-profile":
        if adapter.profile_exists(target):
            observation = adapter.profile_observation(target)
            return "noop", observation, observation, "profile already exists"
        before = adapter.profile_observation(target)
        adapter.create_profile(action)
        return "applied", before, adapter.profile_observation(target), "profile created"
    if kind == "set-profile-config":
        current = adapter.get_profile_config(target, params["key"])
        if current == params["value"]:
            return "noop", {"value": current}, {"value": current}, "profile setting already exact"
        adapter.set_profile_config(action)
        return "applied", {"value": current}, {"value": params["value"]}, "profile setting updated"
    if kind == "materialize-tree":
        path = Path(target)
        authority = Path(params["authority_root"])
        _assert_under(path, authority, "managed tree")
        source = _safe_absolute(params["source_root"], "managed tree source")
        source_digest, source_files = tree_snapshot(source)
        if source_digest != params["source_tree_sha256"]:
            raise ManagerError(f"managed tree source hash drift: {source}")
        before = _tree_observation(path, capture=True)
        if before.get("sha256") == source_digest:
            after = {key: value for key, value in before.items() if key != "content_b64"}
            return "noop", after, after, "exact managed tree already present"
        _write_tree(path, source_files)
        return "applied", before, _tree_observation(path), "managed tree materialized atomically"
    if kind == "create-empty-board":
        if adapter.board_exists(target):
            observation = adapter.board_observation(target)
            return "noop", observation, observation, "board already exists"
        before = adapter.board_observation(target)
        adapter.create_board(action)
        return "applied", before, adapter.board_observation(target), "empty board created"
    raise ManagerError(f"action implementation is unavailable: {kind}")


def apply_plan(
    plan: dict[str, Any],
    approval: str,
    control_root: Path,
    adapter: HermesAdapter,
    journal_dir: Path,
) -> dict[str, Any]:
    _reject_secret_keys(plan)
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "manager plan")
    _validate_plan_semantics(plan)
    actual = document_digest(plan, "plan_sha256")
    if plan.get("plan_sha256") != actual or approval != actual or not _SHA256_RE.fullmatch(approval):
        raise ManagerError("plan approval hash mismatch")
    if plan.get("blockers"):
        raise ManagerError("blocked manager plan cannot be applied")
    for action in plan["actions"]:
        if action["kind"] not in _ALLOWED_ACTIONS:
            raise ManagerError(f"unsupported manager action: {action['kind']}")
    _recheck_preconditions(plan, adapter)

    journal_dir.mkdir(parents=True, exist_ok=True)
    if journal_dir.is_symlink():
        raise ManagerError("journal directory cannot be a symlink")
    os.chmod(journal_dir, 0o700)
    journal_path = journal_dir / f"apply-{actual.split(':', 1)[1][:16]}.json"
    if journal_path.exists() or journal_path.is_symlink():
        raise ManagerError(f"journal already exists: {journal_path}")
    journal: dict[str, Any] = {
        "schema_version": 1, "operation": "apply", "plan_sha256": actual,
        "state": "in-progress", "entries": [], "journal_sha256": "sha256:" + "0" * 64,
    }
    _write_journal(journal_path, journal, control_root)
    for action in plan["actions"]:
        journal_target = (
            f"{action['target']}#{action['parameters']['key']}"
            if action["kind"] == "set-profile-config"
            else action["target"]
        )
        try:
            state, before, after, message = _apply_action(action, adapter)
            journal["entries"].append({
                "action_id": action["id"], "kind": action["kind"], "target": journal_target,
                "state": state, "before": before, "after": after, "message": message,
            })
            _write_journal(journal_path, journal, control_root)
        except Exception as exc:
            journal["entries"].append({
                "action_id": action["id"], "kind": action["kind"], "target": journal_target,
                "state": "failed", "before": None, "after": None,
                "message": f"{type(exc).__name__}: action failed",
            })
            journal["state"] = "failed"
            _write_journal(journal_path, journal, control_root)
            if isinstance(exc, ManagerError):
                raise
            raise ManagerError(f"manager action failed: {action['id']}") from exc
    journal["state"] = "completed"
    _write_journal(journal_path, journal, control_root)
    return journal


def rollback_journal(
    journal_path: Path,
    approval: str,
    control_root: Path,
    adapter: HermesAdapter,
    rollback_dir: Path,
) -> dict[str, Any]:
    source = _load_document(journal_path, "manager journal")
    _reject_secret_keys(source)
    _validate(source, _load_schema(control_root, "manager-journal.schema.json"), "manager journal")
    actual = document_digest(source, "journal_sha256")
    if source.get("journal_sha256") != actual or approval != actual or not _SHA256_RE.fullmatch(approval):
        raise ManagerError("rollback approval hash mismatch")
    if source.get("operation") != "apply" or source.get("state") != "completed":
        raise ManagerError("only a completed apply journal can be rolled back")

    for entry in source["entries"]:
        if entry["state"] == "noop":
            continue
        if entry["state"] != "applied":
            raise ManagerError(f"journal contains non-rollbackable entry: {entry['action_id']}")
        kind, item_target = entry["kind"], entry["target"]
        if kind == "write-managed-file":
            current = _file_observation(Path(item_target))
        elif kind == "materialize-tree":
            current = _tree_observation(Path(item_target))
        elif kind == "create-profile":
            current = adapter.profile_observation(item_target)
        elif kind == "create-empty-board":
            current = adapter.board_observation(item_target)
        elif kind == "set-profile-config":
            if "#" not in item_target:
                raise ManagerError("profile-setting rollback key unavailable")
            profile, key = item_target.split("#", 1)
            current = {"value": adapter.get_profile_config(profile, key)}
        else:
            raise ManagerError(f"rollback is unavailable for action kind: {kind}")
        if current != entry["after"]:
            raise ManagerError(f"rollback precondition drift: {kind} {item_target}")

    rollback_dir.mkdir(parents=True, exist_ok=True)
    if rollback_dir.is_symlink():
        raise ManagerError("rollback directory cannot be a symlink")
    os.chmod(rollback_dir, 0o700)
    target = rollback_dir / f"rollback-{actual.split(':', 1)[1][:16]}.json"
    if target.exists() or target.is_symlink():
        raise ManagerError(f"rollback journal already exists: {target}")
    result: dict[str, Any] = {
        "schema_version": 1,
        "operation": "rollback",
        "plan_sha256": source["plan_sha256"],
        "state": "in-progress",
        "entries": [],
        "journal_sha256": "sha256:" + "0" * 64,
    }
    _write_journal(target, result, control_root)

    for entry in reversed(source["entries"]):
        if entry["state"] == "noop":
            continue
        if entry["state"] != "applied":
            raise ManagerError(f"journal contains non-rollbackable entry: {entry['action_id']}")
        kind, item_target = entry["kind"], entry["target"]
        try:
            if kind == "write-managed-file":
                path = Path(item_target)
                current = _file_observation(path)
                if current != entry["after"]:
                    raise ManagerError(f"rollback precondition drift: {path}")
                before = entry["before"] or {"state": "absent"}
                if before.get("state") == "absent":
                    path.unlink()
                else:
                    content_b64 = before.get("content_b64")
                    if not isinstance(content_b64, str):
                        raise ManagerError(f"rollback bytes unavailable: {path}")
                    content = base64.b64decode(content_b64, validate=True)
                    if bytes_digest(content) != before.get("sha256"):
                        raise ManagerError(f"rollback bytes hash mismatch: {path}")
                    _atomic_write(path, content, int(before.get("mode", 0o600)))
            elif kind == "set-profile-config":
                key = ""
                # The apply journal intentionally contains no arbitrary action payload.
                # Recover the key from the corresponding approved plan is impossible here,
                # so target-qualified keys are journalled below during apply.
                if "#" not in item_target:
                    raise ManagerError("profile-setting rollback key unavailable")
                profile, key = item_target.split("#", 1)
                current = adapter.get_profile_config(profile, key)
                expected_after = (entry["after"] or {}).get("value")
                if current != expected_after:
                    raise ManagerError(f"rollback precondition drift: {profile}#{key}")
                previous = (entry["before"] or {}).get("value")
                if previous is None:
                    adapter.unset_profile_config(profile, key)
                else:
                    adapter.set_profile_config({"target": profile, "parameters": {"key": key, "value": previous}})
            elif kind == "materialize-tree":
                path = Path(item_target)
                current = _tree_observation(path)
                if current != entry["after"]:
                    raise ManagerError(f"rollback precondition drift: {path}")
                before = entry["before"] or {"state": "absent"}
                if before.get("state") == "absent":
                    shutil.rmtree(path)
                else:
                    encoded = before.get("content_b64")
                    if not isinstance(encoded, dict):
                        raise ManagerError(f"rollback tree bytes unavailable: {path}")
                    files = {
                        _safe_relative(str(name), "rollback tree member").as_posix(): base64.b64decode(content, validate=True)
                        for name, content in encoded.items()
                    }
                    expected, _ = tree_snapshot_from_mapping(files)
                    if expected != before.get("sha256"):
                        raise ManagerError(f"rollback tree hash mismatch: {path}")
                    _write_tree(path, files)
            elif kind == "create-profile":
                current = adapter.profile_observation(item_target)
                if current != entry["after"]:
                    raise ManagerError(f"rollback precondition drift: profile {item_target}")
                adapter.delete_profile(item_target)
            elif kind == "create-empty-board":
                current = adapter.board_observation(item_target)
                if current != entry["after"]:
                    raise ManagerError(f"rollback precondition drift: board {item_target}")
                adapter.archive_board(item_target)
            else:
                raise ManagerError(f"rollback is unavailable for action kind: {kind}")
            result["entries"].append({
                "action_id": entry["action_id"], "kind": kind, "target": item_target,
                "state": "rolled-back", "before": entry["after"], "after": entry["before"],
                "message": "approved rollback applied",
            })
            _write_journal(target, result, control_root)
        except Exception as exc:
            result["state"] = "failed"
            result["entries"].append({
                "action_id": entry["action_id"], "kind": kind, "target": item_target,
                "state": "failed", "before": entry.get("after"), "after": None,
                "message": f"{type(exc).__name__}: rollback failed",
            })
            _write_journal(target, result, control_root)
            if isinstance(exc, ManagerError):
                raise
            raise ManagerError(f"rollback failed: {entry['action_id']}") from exc
    result["state"] = "rolled-back"
    _write_journal(target, result, control_root)
    return result


def _runtime_state_value(runtime_manifest: dict[str, Any]) -> str:
    return str(runtime_manifest.get("project_state", runtime_manifest.get("state", ""))).lower()


def _runtime_is_routable(runtime_manifest: dict[str, Any]) -> bool:
    values = {
        str(runtime_manifest.get("state", "")).lower(),
        str(runtime_manifest.get("project_state", "")).lower(),
    }
    return "routable" in values


def _doctor_success_state(runtime_manifest: dict[str, Any]) -> str:
    raw_state = _runtime_state_value(runtime_manifest)
    if "blocked" in raw_state or raw_state == "routable":
        return "RED"
    if raw_state in {"inventory-only", "intentionally-non-routable", "non-routable"}:
        return "GREY"
    if raw_state in {"reviewed-update-available", "update-available"}:
        return "BLUE"
    if raw_state in {"pinned", "deliberately-pinned", "overlay-rebase-required", "test-due"}:
        return "AMBER"
    return "GREEN"


def doctor_project(request_path: Path, control_root: Path, adapter: HermesAdapter) -> dict[str, Any]:
    request = _load_document(request_path, "project setup request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "project-setup-request.schema.json"), "project setup request")
    _validate(request["project_manifest"], _load_schema(control_root, "project-definition.schema.json"), "embedded project manifest")
    slug = request["project"]["slug"]
    ownership = {"schema_version": 1, "owner": "skills-manager", "project": slug}
    repo = _safe_absolute(request["repository"]["path"], "repository path")
    contract_rel = _safe_relative(request["repository"]["contract_path"], "project contract path")
    manifest_bytes = yaml.safe_dump(request["project_manifest"], sort_keys=False, width=1000).encode("utf-8")
    runtime_manifest = request.get("runtime_manifest", {"schema_version": 1, "project": slug, "state": "proposed"})
    runtime_bytes = yaml.safe_dump(runtime_manifest, sort_keys=False, width=1000).encode("utf-8")
    findings: list[dict[str, str]] = []

    def error(code: str, message: str) -> None:
        findings.append({"severity": "error", "code": code, "message": message})

    if str(runtime_manifest.get("project", slug)) != slug:
        error("runtime-project-mismatch", "runtime manifest project does not match setup request")
    if _runtime_is_routable(runtime_manifest):
        error("runtime-routable", "project setup runtime manifest must remain non-routable")

    try:
        observed = observe_repository(repo)
        for key in ("remote", "branch", "commit"):
            if observed[key] != request["repository"][key]:
                error(f"repository-{key}", f"repository {key} drift")
        allowed_contract = observed["changes"] == [contract_rel.as_posix()] and (repo / contract_rel).is_file() and (repo / contract_rel).read_bytes() == manifest_bytes
        if not observed["clean"] and not allowed_contract:
            error("repository-dirty", "repository has unmanaged changes")
    except ManagerError as exc:
        error("repository-unavailable", str(exc))

    expected_files = []
    if request["effects"]["write_control_manifest"]:
        expected_files.extend([
            (control_root / "projects" / slug / "project.yaml", manifest_bytes),
            (control_root / "projects" / slug / "runtime.yaml", runtime_bytes),
        ])
    if request["effects"]["write_project_contract"]:
        expected_files.append((repo / contract_rel, manifest_bytes))
    for path, content in expected_files:
        try:
            observed_file = _file_observation(path)
            if observed_file.get("sha256") != bytes_digest(content):
                error("managed-file-drift", f"managed file missing or drifted: {path}")
        except ManagerError as exc:
            error("managed-file-unsafe", str(exc))

    if request["effects"]["create_profiles"]:
        for profile in request["profiles"]:
            observation = adapter.profile_observation(profile["name"])
            if not observation.get("exists"):
                error("profile-missing", f"profile missing: {profile['name']}")
                continue
            if observation.get("ownership") != ownership:
                error("profile-unowned", f"profile is not owned by this project setup: {profile['name']}")
            for key, value in sorted(profile["settings"].items()):
                if adapter.get_profile_config(profile["name"], key) != value:
                    error("profile-config-drift", f"profile setting drift: {profile['name']} {key}")
    if request["effects"]["materialize_profile_skills"]:
        try:
            sources = _declared_skill_sources(request["project_manifest"], control_root)
            bundles = request["project_manifest"]["skill_layers"]["bundles"]
            for profile in request["profiles"]:
                binding = request["project_manifest"]["profiles"].get(profile["role"], {})
                expected_names = sorted(set(bundles.get(binding.get("bundle"), [])))
                root = adapter.profile_skill_root(profile["name"])
                actual_names: list[str] = []
                if root.exists():
                    if root.is_symlink() or not root.is_dir():
                        error("profile-skills-unsafe", f"profile skill root is unsafe: {root}")
                        continue
                    for child in sorted(root.iterdir(), key=lambda item: item.name):
                        if child.is_symlink() or not child.is_dir():
                            error("profile-skill-unsafe", f"profile skill entry is unsafe: {child}")
                            continue
                        actual_names.append(child.name)
                if actual_names != expected_names:
                    error(
                        "profile-skill-set-drift",
                        f"profile skill set drift: {profile['name']} expected={expected_names} actual={actual_names}",
                    )
                for name in expected_names:
                    if name not in sources:
                        error("profile-skill-source-missing", f"declared skill source missing: {name}")
                        continue
                    expected_tree = _tree_observation(sources[name])
                    actual_tree = _tree_observation(root / name)
                    if actual_tree != expected_tree:
                        error("profile-skill-hash-drift", f"profile skill hash drift: {profile['name']}/{name}")
        except ManagerError as exc:
            error("profile-skill-authority", str(exc))
    if request["effects"]["create_empty_board"]:
        board = request["board"]
        desired_board = {
            "exists": True, "name": board["name"], "description": board["description"],
            "default_workdir": board["default_workdir"], "task_count": 0,
            "ownership": ownership,
        }
        if adapter.board_observation(board["slug"]) != desired_board:
            error("board-drift", f"board is missing, non-empty, or drifted: {board['slug']}")

    return {
        "schema_version": 1,
        "project": slug,
        "state": "RED" if findings else _doctor_success_state(runtime_manifest),
        "routable": False,
        "findings": sorted(findings, key=lambda item: (item["code"], item["message"])),
        "request_sha256": bytes_digest(request_path.read_bytes()),
        "request_path": str(request_path.resolve()),
    }


def build_project_reconcile_plan(
    doctor_report_path: Path,
    control_root: Path,
    adapter: HermesAdapter,
    *,
    control_commit: str,
) -> dict[str, Any]:
    report = _load_document(doctor_report_path, "project doctor report")
    _reject_secret_keys(report)
    if report.get("schema_version") != 1 or not report.get("project"):
        raise ManagerError("doctor report is not a project doctor report")
    request_path = _safe_absolute(str(report.get("request_path", "")), "doctor report request path")
    request_sha256 = str(report.get("request_sha256", ""))
    if not _SHA256_RE.fullmatch(request_sha256):
        raise ManagerError("doctor report lacks an exact request digest")
    if bytes_digest(request_path.read_bytes()) != request_sha256:
        raise ManagerError("doctor report request digest mismatch")
    plan = build_project_plan(request_path, control_root, adapter, control_commit=control_commit)
    if plan["project"] != report["project"]:
        plan["blockers"] = sorted(set(plan["blockers"] + ["doctor report project does not match request"]))
    plan["kind"] = "project-reconcile"
    plan["plan_sha256"] = document_digest(plan, "plan_sha256")
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "project reconcile plan")
    _validate_plan_semantics(plan)
    return plan


def fleet_status(control_root: Path) -> dict[str, Any]:
    projects_root = control_root / "projects"
    rows: list[dict[str, Any]] = []
    if not projects_root.is_dir():
        return {
            "schema_version": 1, "state": "GREEN", "projects": [], "skills": [],
            "pending_candidates": [], "control_blockers": [],
            "summary": {"GREEN": 0, "BLUE": 0, "AMBER": 0, "RED": 0, "GREY": 0},
        }
    for directory in sorted(projects_root.iterdir(), key=lambda item: item.name):
        if directory.is_symlink() or not directory.is_dir():
            continue
        manifest_path = directory / "project.yaml"
        runtime_path = directory / "runtime.yaml"
        try:
            manifest = _load_document(manifest_path, "project manifest")
            runtime = _load_document(runtime_path, "runtime manifest")
            _reject_secret_keys(manifest)
            _reject_secret_keys(runtime)
            project = manifest.get("project", {})
            layers = manifest.get("skill_layers", {})
            core = layers.get("core_release") or {}
            packs = layers.get("capability_packs") or []
            overlays = layers.get("project_overlays") or []
            runtime_state = runtime.get("project_state", runtime.get("state", "unknown"))
            state = _doctor_success_state(runtime)
            rows.append({
                "slug": str(project.get("slug", directory.name)),
                "display_name": str(project.get("display_name", directory.name)),
                "state": state,
                "routing_state": runtime_state,
                "core": f"{core.get('name', 'none')}@{core.get('version', 'none')}" if core else "none",
                "packs": sorted(f"{item.get('name')}@{item.get('version')}" for item in packs if isinstance(item, dict)),
                "overlays": sorted(str(item.get("name")) for item in overlays if isinstance(item, dict)),
                "manifest_sha256": bytes_digest(manifest_path.read_bytes()),
                "runtime_sha256": bytes_digest(runtime_path.read_bytes()),
            })
        except ManagerError as exc:
            rows.append({
                "slug": directory.name, "display_name": directory.name, "state": "RED",
                "routing_state": "unavailable", "core": "unknown", "packs": [], "overlays": [],
                "error": str(exc),
            })
    skill_rows: list[dict[str, Any]] = []
    pending_candidates: list[dict[str, Any]] = []
    control_blockers: list[str] = []
    try:
        inventory = skill_inventory(control_root)
        for artifact in inventory["artifacts"]:
            projects = []
            for project in inventory["projects"]:
                if artifact["layer"] == "release":
                    binding = project.get("core_release") or {}
                    uses = binding.get("name") == artifact.get("name") and binding.get("version") == artifact.get("version")
                else:
                    uses = any(
                        item.get("name") == artifact.get("name") and item.get("version") == artifact.get("version")
                        for item in project.get("capability_packs", []) if isinstance(item, dict)
                    )
                if uses:
                    projects.append({"slug": project["slug"], "profiles": project["profiles"]})
            skill_rows.append({
                "layer": artifact["layer"], "name": artifact.get("name"), "version": artifact.get("version"),
                "bundle_sha256": artifact.get("bundle_sha256"), "projects": projects,
            })
    except ManagerError as exc:
        control_blockers.append(str(exc))

    candidates_root = control_root / "candidates"
    for layer_name, directory_name in (("release", "releases"), ("pack", "packs")):
        layer_root = candidates_root / directory_name
        if not layer_root.exists():
            continue
        if layer_root.is_symlink() or not layer_root.is_dir():
            control_blockers.append(f"unsafe candidate layer directory: {layer_root}")
            continue
        for name_root in sorted(layer_root.iterdir(), key=lambda item: item.name):
            if name_root.is_symlink() or not name_root.is_dir():
                control_blockers.append(f"unsafe candidate artifact directory: {name_root}")
                continue
            for version_root in sorted(name_root.iterdir(), key=lambda item: item.name):
                try:
                    _semver(version_root.name)
                    tree_sha, files = tree_snapshot(version_root)
                    pending_candidates.append({
                        "layer": layer_name, "name": name_root.name, "version": version_root.name,
                        "tree_sha256": tree_sha, "files": len(files), "state": "non-routable",
                    })
                except ManagerError as exc:
                    control_blockers.append(str(exc))

    summary = {state: sum(1 for row in rows if row["state"] == state) for state in ("GREEN", "BLUE", "AMBER", "RED", "GREY")}
    state = "RED" if summary["RED"] or control_blockers else "GREEN"
    return {
        "schema_version": 1, "state": state, "projects": rows,
        "skills": sorted(skill_rows, key=lambda item: (item["layer"], str(item["name"]), _semver(str(item["version"])))),
        "pending_candidates": sorted(pending_candidates, key=lambda item: (item["layer"], item["name"], _semver(item["version"]))),
        "control_blockers": sorted(control_blockers), "summary": summary,
    }


def render_fleet_markdown(report: dict[str, Any]) -> str:
    lines = ["# Skill Control Center", "", "## Projects", ""]
    if not report.get("projects"):
        lines.append("- No registered projects.")
    for row in report.get("projects", []):
        lines.extend([
            f"- **{row['display_name']}** (`{row['slug']}`) — **{row['state']}**",
            f"  - Routing: `{row.get('routing_state', 'unknown')}`",
            f"  - Core: `{row.get('core', 'unknown')}`",
            f"  - Packs: {', '.join(f'`{item}`' for item in row.get('packs', [])) or 'none'}",
            f"  - Overlays: {', '.join(f'`{item}`' for item in row.get('overlays', [])) or 'none'}",
        ])
    lines.extend(["", "## Skill inventory", ""])
    if not report.get("skills"):
        lines.append("- No governed releases or packs.")
    for item in report.get("skills", []):
        project_names = ", ".join(f"`{project['slug']}`" for project in item.get("projects", [])) or "none"
        lines.append(
            f"- `{item.get('layer')}:{item.get('name')}@{item.get('version')}` — projects: {project_names}"
        )
    lines.extend(["", "## Pending candidates", ""])
    if not report.get("pending_candidates"):
        lines.append("- None.")
    for item in report.get("pending_candidates", []):
        lines.append(
            f"- `{item['layer']}:{item['name']}@{item['version']}` — `{item['state']}` — `{item['tree_sha256']}`"
        )
    if report.get("control_blockers"):
        lines.extend(["", "## Control blockers", ""])
        lines.extend(f"- {item}" for item in report["control_blockers"])
    lines.extend(["", "## Summary", "", f"- Control state: **{report.get('state', 'GREY')}**"])
    for state in ("GREEN", "BLUE", "AMBER", "RED", "GREY"):
        lines.append(f"- {state}: {report.get('summary', {}).get(state, 0)}")
    lines.append("")
    return "\n".join(lines)


def _semver(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ManagerError(f"invalid semantic version: {value}")
    return tuple(int(item) for item in value.split("."))  # type: ignore[return-value]


def _project_references_candidate(manifest: dict[str, Any], layer: str, name: str) -> bool:
    layers = manifest.get("skill_layers", {})
    if layer == "release":
        return (layers.get("core_release") or {}).get("name") == name
    return any(isinstance(item, dict) and item.get("name") == name for item in layers.get("capability_packs", []))


def _project_uses_version(manifest: dict[str, Any], layer: str, name: str, version: str) -> bool:
    layers = manifest.get("skill_layers", {})
    if layer == "release":
        value = layers.get("core_release") or {}
        return value.get("name") == name and value.get("version") == version
    return any(
        isinstance(item, dict) and item.get("name") == name and item.get("version") == version
        for item in layers.get("capability_packs", [])
    )


def skill_inventory(control_root: Path) -> dict[str, Any]:
    catalog_path = control_root / "catalog.yaml"
    catalog = _load_document(catalog_path, "skill catalog")
    _reject_secret_keys(catalog)
    releases = [
        {"layer": "release", **item}
        for item in catalog.get("releases", []) if isinstance(item, dict)
    ]
    packs = [
        {"layer": "pack", **item}
        for item in catalog.get("packs", []) if isinstance(item, dict)
    ]
    projects = []
    for item in catalog.get("projects", []):
        if not isinstance(item, dict):
            continue
        manifest_rel = _safe_relative(str(item.get("manifest", "")), "catalog project manifest")
        manifest_path = control_root / manifest_rel
        manifest = _load_document(manifest_path, "project manifest")
        _reject_secret_keys(manifest)
        layers = manifest.get("skill_layers", {})
        projects.append({
            "slug": item.get("slug"),
            "core_release": layers.get("core_release"),
            "capability_packs": layers.get("capability_packs", []),
            "project_overlays": layers.get("project_overlays", []),
            "profiles": sorted(
                str(binding.get("name")) for binding in (manifest.get("profiles") or {}).values()
                if isinstance(binding, dict) and binding.get("name")
            ),
        })
    payload = {
        "schema_version": 1,
        "catalog_sha256": bytes_digest(catalog_path.read_bytes()),
        "artifacts": sorted(releases + packs, key=lambda item: (item["layer"], str(item.get("name")), _semver(str(item.get("version"))))),
        "projects": sorted(projects, key=lambda item: str(item["slug"])),
    }
    payload["inventory_sha256"] = document_digest(payload, "inventory_sha256")
    return payload


def _evidence_ok(
    item: dict[str, Any],
    candidate: dict[str, Any],
    control_commit: str,
    expected_kind: str,
    control_root: Path,
) -> bool:
    try:
        path = _safe_absolute(item["path"], "evidence path")
        _assert_regular_input(path, "promotion evidence")
        if bytes_digest(path.read_bytes()) != item["sha256"] or item["sha256"] == "sha256:" + "0" * 64:
            return False
        evidence = _load_document(path, "lifecycle evidence")
        _reject_secret_keys(evidence)
        _validate(evidence, _load_schema(control_root, "lifecycle-evidence.schema.json"), "lifecycle evidence")
        return (
            evidence["kind"] == expected_kind
            and evidence["result"] == "PASS"
            and evidence["project"] == item["project"]
            and evidence["candidate_bundle_sha256"] == candidate["bundle_sha256"]
            and evidence["candidate_manifest_sha256"] == candidate["manifest_sha256"]
            and evidence["control_commit"] == control_commit
            and all(check["result"] == "PASS" for check in evidence["checks"])
        )
    except ManagerError:
        return False


def _materialize_tree_action(
    action_id: str,
    source: Path,
    target: Path,
    authority_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _assert_under(target, authority_root, "managed tree")
    source_digest, _ = tree_snapshot(source)
    before = _tree_observation(target)
    action = {
        "id": action_id,
        "kind": "materialize-tree",
        "target": str(target),
        "parameters": {
            "source_root": str(source.resolve()),
            "source_tree_sha256": source_digest,
            "authority_root": str(authority_root.resolve()),
        },
        "rollback": {"before": before},
    }
    return action, {"kind": "tree", "target": str(target), "expected": before}


def build_skill_candidate_plan(
    request_path: Path,
    control_root: Path,
    *,
    control_commit: str,
) -> dict[str, Any]:
    request = _load_document(request_path, "skill candidate request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "skill-candidate-request.schema.json"), "skill candidate request")
    if not re.fullmatch(r"[0-9a-f]{40}", control_commit):
        raise ManagerError("control commit must be a full lowercase SHA")
    candidate = request["candidate"]
    source = _safe_absolute(candidate["source_path"], "candidate source")
    source_digest, _ = tree_snapshot(source)
    manifest_rel = _safe_relative(candidate["manifest_path"], "candidate manifest path")
    manifest_path = source / manifest_rel
    _assert_under(manifest_path, source, "candidate manifest")
    _assert_regular_input(manifest_path, "candidate manifest")
    blockers: list[str] = []
    if source_digest != candidate["bundle_sha256"]:
        blockers.append("candidate bundle hash mismatch")
    if bytes_digest(manifest_path.read_bytes()) != candidate["manifest_sha256"]:
        blockers.append("candidate manifest hash mismatch")

    catalog = _load_document(control_root / "catalog.yaml", "skill catalog")
    _reject_secret_keys(catalog)
    collection_key = "releases" if candidate["layer"] == "release" else "packs"
    same_name = [
        item for item in catalog.get(collection_key, [])
        if isinstance(item, dict) and item.get("name") == candidate["name"]
    ]
    if same_name and _semver(candidate["version"]) <= max(_semver(str(item["version"])) for item in same_name):
        blockers.append("candidate version does not advance the immutable release line")
    layer_dir = "releases" if candidate["layer"] == "release" else "packs"
    candidate_root = control_root / "candidates"
    destination = candidate_root / layer_dir / candidate["name"] / candidate["version"]
    observed_destination = _tree_observation(destination)
    if observed_destination.get("state") == "tree" and observed_destination.get("sha256") != source_digest:
        blockers.append("immutable candidate destination already exists with different bytes")
    action, target_precondition = _materialize_tree_action("a001", source, destination, candidate_root)
    plan: dict[str, Any] = {
        "schema_version": 1,
        "kind": "skill-candidate",
        "project": None,
        "created_from": {
            "request_sha256": bytes_digest(request_path.read_bytes()),
            "control_commit": control_commit,
        },
        "preconditions": sorted([
            {"kind": "authority", "target": str(control_root.parent.resolve()), "expected": control_commit},
            {"kind": "tree", "target": str(source), "expected": _tree_observation(source)},
            target_precondition,
        ], key=lambda item: (item["kind"], item["target"])),
        "actions": [action],
        "blockers": sorted(set(blockers)),
        "plan_sha256": "sha256:" + "0" * 64,
    }
    plan["plan_sha256"] = document_digest(plan, "plan_sha256")
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "skill candidate plan")
    _validate_plan_semantics(plan)
    return plan


def skill_impact(request_path: Path, control_root: Path) -> dict[str, Any]:
    request = _load_document(request_path, "skill candidate request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "skill-candidate-request.schema.json"), "skill candidate request")
    candidate = request["candidate"]
    catalog_path = control_root / "catalog.yaml"
    catalog = _load_document(catalog_path, "skill catalog")
    _reject_secret_keys(catalog)
    impacted: list[dict[str, Any]] = []
    for item in catalog.get("projects", []):
        if not isinstance(item, dict) or not item.get("slug"):
            continue
        manifest_path = control_root / _safe_relative(str(item.get("manifest", "")), "catalog project manifest")
        manifest = _load_document(manifest_path, "project manifest")
        _reject_secret_keys(manifest)
        if _project_references_candidate(manifest, candidate["layer"], candidate["name"]):
            impacted.append({
                "project": str(item["slug"]),
                "manifest_sha256": bytes_digest(manifest_path.read_bytes()),
                "profiles": sorted(
                    str(binding.get("name")) for binding in (manifest.get("profiles") or {}).values()
                    if isinstance(binding, dict) and binding.get("name")
                ),
                "reason": f"pins {candidate['layer']} {candidate['name']}",
            })
    report: dict[str, Any] = {
        "schema_version": 1,
        "candidate": {
            "layer": candidate["layer"], "name": candidate["name"], "version": candidate["version"],
            "bundle_sha256": candidate["bundle_sha256"],
        },
        "catalog_sha256": bytes_digest(catalog_path.read_bytes()),
        "complete": True,
        "impacted_projects": sorted(impacted, key=lambda item: item["project"]),
        "impact_sha256": "sha256:" + "0" * 64,
    }
    report["impact_sha256"] = document_digest(report, "impact_sha256")
    return report


def build_skill_canary_plan(
    request_path: Path,
    control_root: Path,
    adapter: HermesAdapter,
    *,
    control_commit: str,
) -> dict[str, Any]:
    request = _load_document(request_path, "skill canary request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "skill-canary-request.schema.json"), "skill canary request")
    if not re.fullmatch(r"[0-9a-f]{40}", control_commit):
        raise ManagerError("control commit must be a full lowercase SHA")
    candidate = request["candidate"]
    source = _safe_absolute(candidate["source_path"], "candidate source")
    layer_dir = "releases" if candidate["layer"] == "release" else "packs"
    expected_source = control_root / "candidates" / layer_dir / candidate["name"] / candidate["version"]
    blockers: list[str] = []
    if source.resolve(strict=False) != expected_source.resolve(strict=False):
        blockers.append("canary source must be the exact non-routable candidate authority path")
    source_digest, _ = tree_snapshot(source)
    manifest = source / _safe_relative(candidate["manifest_path"], "candidate manifest path")
    _assert_under(manifest, source, "candidate manifest")
    _assert_regular_input(manifest, "candidate manifest")
    if source_digest != candidate["bundle_sha256"]:
        blockers.append("candidate bundle hash mismatch")
    if bytes_digest(manifest.read_bytes()) != candidate["manifest_sha256"]:
        blockers.append("candidate manifest hash mismatch")
    relative = expected_source.relative_to(control_root.parent).as_posix()
    if not _git(control_root.parent, "ls-files", "--", relative).splitlines():
        blockers.append("candidate must be committed before canary rollout")
    if _git(control_root.parent, "diff", "--name-only", "HEAD", "--", relative):
        blockers.append("candidate differs from the authority commit")

    catalog = _load_document(control_root / "catalog.yaml", "skill catalog")
    _reject_secret_keys(catalog)
    project_entry = next(
        (item for item in catalog.get("projects", []) if isinstance(item, dict) and item.get("slug") == request["project"]),
        None,
    )
    project_manifest: dict[str, Any] = {}
    if project_entry is None:
        blockers.append("canary project is not registered")
    else:
        project_path = control_root / _safe_relative(str(project_entry.get("manifest", "")), "catalog project manifest")
        project_manifest = _load_document(project_path, "project manifest")
        _reject_secret_keys(project_manifest)
        if not _project_references_candidate(project_manifest, candidate["layer"], candidate["name"]):
            blockers.append("canary project is not impacted by the candidate line")
    if not _evidence_ok(
        request["compatibility_evidence"], candidate, control_commit, "compatibility", control_root
    ) or request["compatibility_evidence"]["project"] != request["project"]:
        blockers.append("exact passing compatibility evidence is required before canary rollout")

    declared_profiles = {
        str(value.get("name")) for value in (project_manifest.get("profiles") or {}).values()
        if isinstance(value, dict) and value.get("name")
    }
    profile = request["profile"]
    observation = adapter.profile_observation(profile)
    if profile not in declared_profiles:
        blockers.append("canary profile is not authoritative for the project")
    if not observation.get("exists"):
        blockers.append("canary profile does not exist")
    expected_owner = {"schema_version": 1, "owner": "skills-manager", "project": request["project"]}
    if observation.get("ownership") != expected_owner:
        blockers.append("canary profile is not manager-owned by the project")

    actions: list[dict[str, Any]] = []
    preconditions: list[dict[str, Any]] = [
        {"kind": "authority", "target": str(control_root.parent.resolve()), "expected": control_commit},
        {"kind": "profile", "target": profile, "expected": observation},
        {"kind": "tree", "target": str(source), "expected": _tree_observation(source)},
    ]
    authority = adapter.profile_skill_root(profile)
    seen: set[str] = set()
    for skill in sorted(request["skills"], key=lambda item: item["name"]):
        if skill["name"] in seen:
            blockers.append(f"duplicate canary skill target: {skill['name']}")
            continue
        seen.add(skill["name"])
        skill_source = source / _safe_relative(skill["source_relative_path"], "candidate skill source")
        _assert_under(skill_source, source, "candidate skill source")
        action, target_precondition = _materialize_tree_action(
            f"a{len(actions) + 1:03d}", skill_source, authority / skill["name"], authority
        )
        actions.append(action)
        preconditions.extend([
            target_precondition,
            {"kind": "tree", "target": str(skill_source), "expected": _tree_observation(skill_source)},
        ])
    plan: dict[str, Any] = {
        "schema_version": 1, "kind": "skill-canary", "project": request["project"],
        "created_from": {
            "request_sha256": bytes_digest(request_path.read_bytes()), "control_commit": control_commit,
        },
        "preconditions": sorted(preconditions, key=lambda item: (item["kind"], item["target"])),
        "actions": actions, "blockers": sorted(set(blockers)),
        "plan_sha256": "sha256:" + "0" * 64,
    }
    plan["plan_sha256"] = document_digest(plan, "plan_sha256")
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "skill canary plan")
    _validate_plan_semantics(plan)
    return plan


def build_skill_update_plan(
    request_path: Path,
    control_root: Path,
    adapter: HermesAdapter,
    *,
    control_commit: str,
) -> dict[str, Any]:
    request = _load_document(request_path, "skill update request")
    _reject_secret_keys(request)
    _validate(request, _load_schema(control_root, "skill-update-request.schema.json"), "skill update request")
    if not re.fullmatch(r"[0-9a-f]{40}", control_commit):
        raise ManagerError("control commit must be a full lowercase SHA")
    candidate = request["candidate"]
    source = _safe_absolute(candidate["source_path"], "candidate source")
    candidate_layer_dir = "releases" if candidate["layer"] == "release" else "packs"
    expected_candidate = control_root / "candidates" / candidate_layer_dir / candidate["name"] / candidate["version"]
    blockers: list[str] = []
    if source.resolve(strict=False) != expected_candidate.resolve(strict=False):
        blockers.append("promotion source must be the exact non-routable candidate authority path")
    else:
        candidate_relative = expected_candidate.relative_to(control_root.parent).as_posix()
        if not _git(control_root.parent, "ls-files", "--", candidate_relative).splitlines():
            blockers.append("candidate must be committed to the control-plane authority before promotion")
        if _git(control_root.parent, "diff", "--name-only", "HEAD", "--", candidate_relative):
            blockers.append("candidate differs from the control-plane authority commit")
    source_digest, _ = tree_snapshot(source)
    manifest_rel = _safe_relative(candidate["manifest_path"], "candidate manifest path")
    manifest_path = source / manifest_rel
    _assert_under(manifest_path, source, "candidate manifest")
    _assert_regular_input(manifest_path, "candidate manifest")
    if source_digest != candidate["bundle_sha256"]:
        blockers.append("candidate bundle hash mismatch")
    if bytes_digest(manifest_path.read_bytes()) != candidate["manifest_sha256"]:
        blockers.append("candidate manifest hash mismatch")

    catalog_path = control_root / "catalog.yaml"
    catalog = _load_document(catalog_path, "skill catalog")
    _reject_secret_keys(catalog)
    collection_key = "releases" if candidate["layer"] == "release" else "packs"
    collection = [item for item in catalog.get(collection_key, []) if isinstance(item, dict)]
    same_name = [item for item in collection if item.get("name") == candidate["name"]]
    if same_name and _semver(candidate["version"]) <= max(_semver(str(item["version"])) for item in same_name):
        if not any(item.get("version") == candidate["version"] and item.get("bundle_sha256") == source_digest for item in same_name):
            blockers.append("candidate version does not advance the immutable release line")

    layer_dir = "releases" if candidate["layer"] == "release" else "packs"
    destination = control_root / layer_dir / candidate["name"] / candidate["version"]
    destination_observation = _tree_observation(destination)
    if destination_observation.get("state") == "tree" and destination_observation.get("sha256") != source_digest:
        blockers.append("immutable candidate destination already exists with different bytes")

    catalog_projects: dict[str, tuple[Path, dict[str, Any]]] = {}
    derived_impacted: list[str] = []
    for item in catalog.get("projects", []):
        if not isinstance(item, dict) or not item.get("slug"):
            continue
        project_path = control_root / _safe_relative(str(item.get("manifest", "")), "catalog project manifest")
        project_manifest = _load_document(project_path, "project manifest")
        _reject_secret_keys(project_manifest)
        slug = str(item["slug"])
        catalog_projects[slug] = (project_path, project_manifest)
        if _project_references_candidate(project_manifest, candidate["layer"], candidate["name"]):
            derived_impacted.append(slug)
    derived_impacted.sort()
    declared = sorted(request["declared_impacted_projects"])
    if declared != derived_impacted:
        blockers.append(f"impacted project declaration mismatch: expected {derived_impacted}, declared {declared}")

    evidence_projects = sorted(
        item["project"] for item in request["compatibility_evidence"]
        if _evidence_ok(item, candidate, control_commit, "compatibility", control_root)
    )
    if evidence_projects != derived_impacted:
        blockers.append("hash-verified compatibility evidence must cover every impacted project exactly")
    canary = request["canary_evidence"]
    if not _evidence_ok(canary, candidate, control_commit, "canary", control_root) or canary["project"] not in catalog_projects:
        blockers.append("hash-verified canary evidence must name a registered project")

    updates = {item["project"]: item["manifest"] for item in request["project_manifest_updates"]}
    if sorted(updates) != derived_impacted:
        blockers.append("project manifest updates must cover every impacted project exactly")
    for slug, manifest in updates.items():
        try:
            _reject_secret_keys(manifest)
            _validate(manifest, _load_schema(control_root, "project-definition.schema.json"), f"project manifest update {slug}")
        except ManagerError as exc:
            blockers.append(str(exc))
            continue
        if manifest.get("project", {}).get("slug") != slug:
            blockers.append(f"project manifest update slug mismatch: {slug}")
        if not _project_uses_version(manifest, candidate["layer"], candidate["name"], candidate["version"]):
            blockers.append(f"project manifest update does not pin candidate: {slug}")
        if candidate["layer"] in {"release", "pack"}:
            candidate_ref = f"{candidate['name']}@{candidate['version']}"
            for overlay in manifest.get("skill_layers", {}).get("project_overlays", []) or []:
                tested = overlay.get("tested_against") if isinstance(overlay, dict) else None
                if not isinstance(tested, list) or candidate_ref not in tested:
                    blockers.append(f"project overlay compatibility is not explicit for {slug}: {overlay.get('name', '<unknown>') if isinstance(overlay, dict) else '<unknown>'}")

    actions: list[dict[str, Any]] = []
    preconditions: list[dict[str, Any]] = [
        {"kind": "authority", "target": str(control_root.parent.resolve()), "expected": control_commit},
    ]
    action, precondition = _materialize_tree_action("a001", source, destination, control_root / layer_dir)
    actions.append(action)
    preconditions.append(precondition)
    preconditions.append({"kind": "tree", "target": str(source), "expected": _tree_observation(source)})

    updated_catalog = copy.deepcopy(catalog)
    entry = {
        "name": candidate["name"],
        "version": candidate["version"],
        "manifest": str((Path(layer_dir) / candidate["name"] / candidate["version"] / manifest_rel).as_posix()),
        "bundle_sha256": source_digest,
        "manifest_sha256": candidate["manifest_sha256"],
    }
    if not any(item.get("name") == entry["name"] and item.get("version") == entry["version"] for item in updated_catalog.get(collection_key, [])):
        updated_catalog.setdefault(collection_key, []).append(entry)
        updated_catalog[collection_key] = sorted(updated_catalog[collection_key], key=lambda item: (item["name"], _semver(item["version"])))
    catalog_bytes = yaml.safe_dump(updated_catalog, sort_keys=False, width=1000).encode("utf-8")
    action = _managed_file_action("a002", catalog_path, catalog_bytes, control_root)
    actions.append(action)
    preconditions.append({"kind": "file", "target": str(catalog_path), "expected": action["rollback"]["before"]})

    next_id = 3
    for slug in derived_impacted:
        project_path, _ = catalog_projects[slug]
        content = yaml.safe_dump(updates[slug], sort_keys=False, width=1000).encode("utf-8")
        action = _managed_file_action(f"a{next_id:03d}", project_path, content, control_root / "projects")
        actions.append(action)
        preconditions.append({"kind": "file", "target": str(project_path), "expected": action["rollback"]["before"]})
        next_id += 1

    seen_profile_targets: set[tuple[str, str, str]] = set()
    for target in sorted(request["profile_targets"], key=lambda item: (item["project"], item["profile"])):
        slug, profile = target["project"], target["profile"]
        if slug not in derived_impacted:
            blockers.append(f"profile target is outside impacted projects: {slug}/{profile}")
            continue
        manifest = updates.get(slug, {})
        declared_profiles = {
            str(value.get("name")) for value in (manifest.get("profiles") or {}).values()
            if isinstance(value, dict) and value.get("name")
        }
        if profile not in declared_profiles:
            blockers.append(f"profile target is not authoritative for project: {slug}/{profile}")
            continue
        observation = adapter.profile_observation(profile)
        exists = bool(observation.get("exists"))
        preconditions.append({"kind": "profile", "target": profile, "expected": observation})
        if not exists:
            blockers.append(f"profile target does not exist: {profile}")
            continue
        expected_owner = {"schema_version": 1, "owner": "skills-manager", "project": slug}
        if observation.get("ownership") != expected_owner:
            blockers.append(f"profile target is not manager-owned by project: {slug}/{profile}")
            continue
        authority = adapter.profile_skill_root(profile)
        for skill in sorted(target["skills"], key=lambda item: item["name"]):
            identity = (slug, profile, skill["name"])
            if identity in seen_profile_targets:
                blockers.append(f"duplicate profile skill target: {'/'.join(identity)}")
                continue
            seen_profile_targets.add(identity)
            skill_source = source / _safe_relative(skill["source_relative_path"], "candidate skill source")
            _assert_under(skill_source, source, "candidate skill source")
            action, precondition = _materialize_tree_action(
                f"a{next_id:03d}", skill_source, authority / skill["name"], authority
            )
            actions.append(action)
            preconditions.append(precondition)
            preconditions.append({"kind": "tree", "target": str(skill_source), "expected": _tree_observation(skill_source)})
            next_id += 1

    plan: dict[str, Any] = {
        "schema_version": 1,
        "kind": "skill-promotion",
        "project": None,
        "created_from": {"request_sha256": bytes_digest(request_path.read_bytes()), "control_commit": control_commit},
        "preconditions": sorted(preconditions, key=lambda item: (item["kind"], item["target"])),
        "actions": actions,
        "blockers": sorted(set(blockers)),
        "plan_sha256": "sha256:" + "0" * 64,
    }
    plan["plan_sha256"] = document_digest(plan, "plan_sha256")
    _validate(plan, _load_schema(control_root, "manager-plan.schema.json"), "skill promotion plan")
    _validate_plan_semantics(plan)
    return plan


def verify_manager(control_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    loaded_schemas: dict[str, dict[str, Any]] = {}
    for name in (
        "project-setup-request.schema.json",
        "project-definition.schema.json",
        "manager-plan.schema.json",
        "manager-journal.schema.json",
        "lifecycle-evidence.schema.json",
        "skill-candidate-request.schema.json",
        "skill-canary-request.schema.json",
        "skill-update-request.schema.json",
    ):
        try:
            loaded_schemas[name] = _load_schema(control_root, name)
        except ManagerError as exc:
            errors.append(str(exc))
    try:
        inventory = skill_inventory(control_root)
    except ManagerError as exc:
        inventory = None
        errors.append(str(exc))

    project_schema = loaded_schemas.get("project-definition.schema.json")
    if project_schema is not None:
        try:
            catalog = _load_document(control_root / "catalog.yaml", "skill catalog")
            _reject_secret_keys(catalog)
            for item in catalog.get("projects", []):
                if not isinstance(item, dict) or not item.get("manifest"):
                    continue
                manifest_path = control_root / _safe_relative(str(item["manifest"]), "catalog project manifest")
                manifest = _load_document(manifest_path, "project manifest")
                _reject_secret_keys(manifest)
                _validate(manifest, project_schema, f"project manifest {manifest_path}")
                if item.get("runtime"):
                    runtime_path = control_root / _safe_relative(str(item["runtime"]), "catalog project runtime")
                    runtime = _load_document(runtime_path, "runtime manifest")
                    _reject_secret_keys(runtime)
        except ManagerError as exc:
            errors.append(str(exc))

    generated = control_root / "generated"
    try:
        current_fleet = fleet_status(control_root)
        fleet_json = generated / "fleet-status.json"
        if fleet_json.exists():
            observed = json.loads(fleet_json.read_text(encoding="utf-8"))
            if observed != current_fleet:
                errors.append("generated fleet-status.json is stale")
        fleet_markdown = generated / "fleet-status.md"
        if fleet_markdown.exists():
            expected_markdown = render_fleet_markdown(current_fleet)
            if fleet_markdown.read_text(encoding="utf-8") != expected_markdown:
                errors.append("generated fleet-status.md is stale")
    except (OSError, UnicodeError, json.JSONDecodeError, ManagerError) as exc:
        errors.append(f"generated fleet projection validation failed: {type(exc).__name__}")

    plan_schema = loaded_schemas.get("manager-plan.schema.json")
    journal_schema = loaded_schemas.get("manager-journal.schema.json")
    for path in sorted(control_root.rglob("*.json"), key=lambda item: item.as_posix()):
        if ".git" in path.parts or path.parent == control_root / "schemas":
            continue
        try:
            document = _load_document(path, "manager JSON document")
            _reject_secret_keys(document)
        except ManagerError as exc:
            errors.append(str(exc))
            continue
        if "plan_sha256" in document:
            try:
                if plan_schema is not None:
                    _validate(document, plan_schema, f"manager plan {path}")
                if document.get("plan_sha256") != document_digest(document, "plan_sha256"):
                    errors.append(f"manager plan digest mismatch: {path}")
            except ManagerError as exc:
                errors.append(str(exc))
        if "journal_sha256" in document:
            try:
                _reject_secret_keys(document)
                if journal_schema is not None:
                    _validate(document, journal_schema, f"manager journal {path}")
                if document.get("journal_sha256") != document_digest(document, "journal_sha256"):
                    errors.append(f"manager journal digest mismatch: {path}")
            except ManagerError as exc:
                errors.append(str(exc))

    return {"ok": not errors, "errors": errors, "inventory": inventory}
