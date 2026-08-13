#!/usr/bin/env python3
"""Fail-closed Jellyberry-to-Jellybase Claude Code adapter."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shlex
import struct
import subprocess
import sys
import types
from typing import Any

import jsonschema
import yaml


def _code_fingerprint(code: types.CodeType) -> str:
    digest = hashlib.sha256()

    def add(value: Any) -> None:
        if isinstance(value, types.CodeType):
            digest.update(b"C")
            for number in (
                value.co_argcount,
                value.co_posonlyargcount,
                value.co_kwonlyargcount,
                value.co_nlocals,
                value.co_stacksize,
                value.co_flags,
            ):
                digest.update(struct.pack(">Q", number))
            for sequence in (value.co_code, value.co_names, value.co_varnames, value.co_freevars, value.co_cellvars, value.co_consts):
                add(sequence)
        elif isinstance(value, bytes):
            digest.update(b"B" + struct.pack(">Q", len(value)) + value)
        elif isinstance(value, str):
            encoded = value.encode("utf-8")
            digest.update(b"S" + struct.pack(">Q", len(encoded)) + encoded)
        elif isinstance(value, tuple):
            digest.update(b"T" + struct.pack(">Q", len(value)))
            for item in value:
                add(item)
        elif isinstance(value, frozenset):
            digest.update(b"R" + struct.pack(">Q", len(value)))
            for item in sorted(value, key=lambda member: (type(member).__name__, repr(member))):
                add(item)
        elif value is None:
            digest.update(b"N")
        elif value is Ellipsis:
            digest.update(b"E")
        elif isinstance(value, bool):
            digest.update(b"Y1" if value else b"Y0")
        elif isinstance(value, int):
            encoded = str(value).encode("ascii")
            digest.update(b"I" + struct.pack(">Q", len(encoded)) + encoded)
        elif isinstance(value, float):
            digest.update(b"F" + struct.pack(">d", value))
        elif isinstance(value, complex):
            digest.update(b"X" + struct.pack(">dd", value.real, value.imag))
        else:
            raise RuntimeError(f"unsupported code constant: {type(value).__name__}")

    add(code)
    return digest.hexdigest()


EXECUTING_ADAPTER_CODE_SHA256 = _code_fingerprint(sys._getframe().f_code)
ADAPTER_VERSION = "0.3.0"
CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = CONTROL_ROOT / "schemas/claude-worker-request.schema.json"
RESULT_SCHEMA_PATH = CONTROL_ROOT / "schemas/claude-worker-result.schema.json"
GOVERNED_HOOK_PATH = CONTROL_ROOT / "assets/claude-worker/block-dangerous-git.py"
SESSION_SETTINGS_PATH = CONTROL_ROOT / "assets/claude-worker/session-settings.json"
SSH_TARGET = "agent-claude"
REMOTE_USER = "jellyclaude"
REMOTE_HOST = "jellybase"
REMOTE_REPOSITORY = "/home/jellyclaude/dev_projects/jellyssh"
REMOTE_WORKTREE_ROOT = "/home/jellyclaude/dev_projects/jellyssh-worktrees"
REMOTE_ORIGIN = "git@github-jellyssh:dotalbot/jellyssh.git"
REMOTE_CLAUDE = "/home/jellyclaude/.local/bin/claude"
REMOTE_TOOLCHAIN = "/home/jellyclaude/.config/jellyssh/toolchain.env"
REMOTE_SESSION_SETTINGS = "/home/jellyclaude/.claude/adapter-session-settings.json"
ALLOWED_OUTPUT_ROOT = Path("/home/jellybot/projects/jellyssh-claude-adapter/evidence")
SECRET_KEY_RE = re.compile(r"(?i)(password|passwd|passphrase|secret|token|api[_-]?key|private[_-]?key|credential)")
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]{20,}|gh[opusr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|"
    r"(?:password|passwd|passphrase|secret|token|api[_-]?key)\s*[:=]\s*\S+)"
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CHECK_COMMANDS = {
    "format": "dart format --output=none --set-exit-if-changed lib/ test/",
    "analyze": "flutter analyze",
    "test": "flutter test",
}


class AdapterError(RuntimeError):
    """A blocking adapter contract failure."""


@dataclass(frozen=True)
class WorkerCommand:
    ssh_target: str
    argv: list[str]
    stdin_text: str


@dataclass(frozen=True)
class ControllerSnapshot:
    commit: str
    asset_bytes: dict[str, bytes]
    digests: dict[str, str]
    request_schema: dict[str, Any]
    result_schema: dict[str, Any]
    skill_digests: dict[str, str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def controller_asset_paths() -> dict[str, Path]:
    return {
        "adapter": Path(__file__).resolve(),
        "request_schema": SCHEMA_PATH,
        "result_schema": RESULT_SCHEMA_PATH,
        "hook": GOVERNED_HOOK_PATH,
        "session_settings": SESSION_SETTINGS_PATH,
    }


def controller_digests() -> dict[str, str]:
    paths = controller_asset_paths()
    return {name: sha256_bytes(path.read_bytes()) for name, path in paths.items()}


def _json_from_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"invalid committed {label}") from exc
    if not isinstance(value, dict):
        raise AdapterError(f"committed {label} root must be an object")
    return value


def _committed_skill_digests(commit: str) -> dict[str, str]:
    release_prefix = "skills-control-plane/releases/core-development/0.1.0"
    release_bytes = _controller_git("show", f"{commit}:{release_prefix}/release.yaml")
    try:
        release = yaml.safe_load(release_bytes)
    except yaml.YAMLError as exc:
        raise AdapterError("invalid committed skill release") from exc
    if not isinstance(release, dict) or not isinstance(release.get("skills"), list):
        raise AdapterError("invalid committed skill release structure")
    expected: dict[str, str] = {}
    for entry in release["skills"]:
        if not isinstance(entry, dict):
            raise AdapterError("invalid committed skill release entry")
        name = str(entry["name"])
        bundle = f"{release_prefix}/{entry['path']}"
        listing = _controller_git("ls-tree", "-r", "--name-only", commit, "--", bundle)
        files = sorted(path for path in listing.decode("utf-8").splitlines() if path)
        if not files:
            raise AdapterError(f"empty committed skill bundle: {name}")
        digest = hashlib.sha256()
        for repository_path in files:
            relative = repository_path.removeprefix(bundle + "/").encode("utf-8")
            content = _controller_git("show", f"{commit}:{repository_path}")
            digest.update(struct.pack(">Q", len(relative)))
            digest.update(relative)
            digest.update(struct.pack(">Q", len(content)))
            digest.update(content)
        observed = digest.hexdigest()
        declared = str(entry["bundle_sha256"]).removeprefix("sha256:")
        if observed != declared:
            raise AdapterError(f"committed skill release digest mismatch: {name}")
        expected[name] = observed
    return expected


def _controller_git(*args: str) -> bytes:
    try:
        environment = os.environ.copy()
        environment["GIT_NO_REPLACE_OBJECTS"] = "1"
        return subprocess.check_output(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(CONTROL_ROOT.parent),
                *args,
            ],
            stderr=subprocess.PIPE,
            env=environment,
        )
    except subprocess.CalledProcessError as exc:
        raise AdapterError("controller Git identity cannot be established") from exc


def verified_controller_commit() -> str:
    if _controller_git("status", "--porcelain", "--untracked-files=normal"):
        raise AdapterError("controller checkout is not clean")
    commit = _controller_git("rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise AdapterError("controller commit is malformed")
    for name, path in controller_asset_paths().items():
        relative = path.relative_to(CONTROL_ROOT.parent).as_posix()
        committed = _controller_git("show", f"{commit}:{relative}")
        if sha256_bytes(committed) != sha256_bytes(path.read_bytes()):
            raise AdapterError(f"controller asset differs from exact commit: {name}")
    return commit


def capture_controller_snapshot() -> ControllerSnapshot:
    if _controller_git("status", "--porcelain", "--untracked-files=normal"):
        raise AdapterError("controller checkout is not clean")
    commit = _controller_git("rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise AdapterError("controller commit is malformed")
    assets: dict[str, bytes] = {}
    for name, path in controller_asset_paths().items():
        relative = path.relative_to(CONTROL_ROOT.parent).as_posix()
        assets[name] = _controller_git("show", f"{commit}:{relative}")
    try:
        committed_code = compile(assets["adapter"].decode("utf-8"), str(Path(__file__).resolve()), "exec")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise AdapterError("exact committed adapter cannot be compiled") from exc
    if EXECUTING_ADAPTER_CODE_SHA256 != _code_fingerprint(committed_code):
        raise AdapterError("loaded controller does not match exact committed adapter")
    return ControllerSnapshot(
        commit=commit,
        asset_bytes=assets,
        digests={name: sha256_bytes(payload) for name, payload in assets.items()},
        request_schema=_json_from_bytes(assets["request_schema"], "request schema"),
        result_schema=_json_from_bytes(assets["result_schema"], "result schema"),
        skill_digests=_committed_skill_digests(commit),
    )


def bundle_digest(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise AdapterError(f"empty skill bundle: {path.name}")
    for item in files:
        if item.is_symlink():
            raise AdapterError(f"skill bundle contains symlink: {item}")
        relative = item.relative_to(path).as_posix().encode("utf-8")
        content = item.read_bytes()
        digest.update(struct.pack(">Q", len(relative)))
        digest.update(relative)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return digest.hexdigest()


def _open_directory_no_symlinks(path: Path) -> int:
    if not path.is_absolute():
        raise AdapterError("evidence directory must be absolute")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise AdapterError("evidence path must be an absolute file path")
    parent = _open_directory_no_symlinks(path.parent)
    temporary = f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    published = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            mode,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Hard-link publication is atomic and refuses to overwrite an immutable
        # attempt if another process won the same-path race after preflight.
        os.link(
            temporary,
            path.name,
            src_dir_fd=parent,
            dst_dir_fd=parent,
            follow_symlinks=False,
        )
        published = True
        # The link is the publication commit point. Everything after it is
        # best-effort housekeeping: never report failure after valid evidence
        # has become visible at the immutable destination.
        try:
            os.unlink(temporary, dir_fd=parent)
        except Exception:
            pass
        try:
            os.fsync(parent)
        except Exception:
            pass
    except Exception:
        if not published:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
        raise
    finally:
        try:
            os.close(parent)
        except OSError:
            pass


def atomic_write_json(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> None:
    atomic_write_bytes(path, canonical_json(value) + b"\n", mode=mode)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise AdapterError(f"{label} root must be an object")
    return value


def validate_request_content(value: Any, path: str = "<root>") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY_RE.search(str(key)):
                raise AdapterError(f"secret-shaped key rejected at {path}.{key}")
            validate_request_content(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_request_content(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if CONTROL_RE.search(value):
            raise AdapterError(f"control character rejected at {path}")
        if SECRET_VALUE_RE.search(value):
            raise AdapterError(f"secret-shaped value rejected at {path}")


def validate_output_text(value: str) -> None:
    if CONTROL_RE.search(value):
        raise AdapterError("worker output contains disallowed control characters")
    if SECRET_VALUE_RE.search(value):
        raise AdapterError("worker output contains secret-shaped content")


def _validate_output_path(path: str, *, allow_test_output: bool = False) -> Path:
    output = Path(path)
    if not output.is_absolute():
        raise AdapterError("output path must be absolute")
    if not allow_test_output:
        try:
            output.relative_to(ALLOWED_OUTPUT_ROOT)
        except ValueError as exc:
            raise AdapterError("output path is outside the adapter evidence root") from exc
    parent = _open_directory_no_symlinks(output.parent)
    try:
        try:
            os.stat(output.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AdapterError("evidence path already exists; attempts are immutable")
    finally:
        os.close(parent)
    return output


def load_and_validate_request(
    path: Path,
    *,
    allow_test_output: bool = False,
    snapshot: ControllerSnapshot | None = None,
) -> dict[str, Any]:
    request = _load_json(path, "Claude worker request")
    schema = snapshot.request_schema if snapshot else _load_json(SCHEMA_PATH, "Claude worker request schema")
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(request, schema)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise AdapterError(f"request schema validation failed at {location}: {exc.message}") from exc
    validate_request_content(request)
    _validate_output_path(str(request["output_path"]), allow_test_output=allow_test_output)
    specification = PurePosixPath(str(request["specification"]["path"]))
    if specification.is_absolute() or ".." in specification.parts:
        raise AdapterError("specification path escapes the repository")
    for allowed in request.get("allowed_paths", []):
        normalized = PurePosixPath(str(allowed).rstrip("/"))
        if normalized.is_absolute() or not normalized.parts or any(part in {".", "..", ".git"} for part in normalized.parts):
            raise AdapterError("allowed path is unsafe")
    return request


def build_prompt(request: dict[str, Any], review_files: list[str] | None = None) -> str:
    specification = request["specification"]
    common = f"""You are a bounded JellySSH {request['mode']} worker.
Repository instructions in CLAUDE.md and the approved personal skills apply.
Attempt: {request['attempt_id']}
Base commit: {request['base_commit']}
Specification: {specification['path']}
Specification SHA-256: {specification['sha256']}
Task:
{request['task']}
Requested checks: {', '.join(request['checks']) or 'none'}
Never push, merge, open a PR, deploy, sign, sideload, use sudo, access another user's home, or expand scope.
"""
    if request["mode"] == "implementation":
        allowed = "\n".join(f"- {path}" for path in request["allowed_paths"])
        return common + f"""Declared changed-path boundary:
{allowed}
Use /implement and /tdd where a pre-agreed public behavior seam exists. Work only in the current worktree using the file tools and change only the declared paths. Do not commit; the controller will run fixed checks and create the local commit mechanically. Finish with a concise summary of changed files, tests, and remaining risks. The controller will independently verify every claim and reject undeclared changed paths.\n"""
    files = "\n".join(f"- {path}" for path in (review_files or [])) or "- none"
    return common + f"""Target commit: {request['target_commit']}
Controller-observed files changed from base to target:
{files}
This is read-only advisory review. Use the two independent Standards and Specification axes from /code-review. Inspect the listed files and any directly relevant context with read-only file tools. Do not edit, commit, push, or run commands. End with exactly one machine-readable line: REVIEW_VERDICT=PASS or REVIEW_VERDICT=BLOCK. The controller will independently verify immutability.\n"""


def build_claude_command(
    request: dict[str, Any],
    worktree: str,
    review_files: list[str] | None = None,
) -> WorkerCommand:
    worktree_path = PurePosixPath(worktree)
    expected_root = PurePosixPath(REMOTE_WORKTREE_ROOT)
    if expected_root not in worktree_path.parents:
        raise AdapterError("worktree is outside the fixed remote root")
    if request["mode"] == "implementation":
        permission = "auto"
        tools = "Read,Glob,Grep,Edit,Write,Skill"
    else:
        permission = "plan"
        tools = "Read,Glob,Grep,Skill"
    remote_argv = [
        REMOTE_CLAUDE,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--settings",
        REMOTE_SESSION_SETTINGS,
        "--permission-mode",
        permission,
        "--model",
        str(request["model"]),
        "--effort",
        str(request["effort"]),
        "--tools",
        tools,
        "--allowedTools",
        tools,
        "--strict-mcp-config",
        "--disallowedTools",
        "mcp__*",
    ]
    command = (
        "set -euo pipefail; "
        f". {shlex.quote(REMOTE_TOOLCHAIN)}; "
        f"cd {shlex.quote(worktree)}; "
        f"exec timeout --signal=TERM --kill-after=30 {int(request['timeout_seconds'])} {shlex.join(remote_argv)}"
    )
    return WorkerCommand(
        ssh_target=SSH_TARGET,
        # OpenSSH concatenates remote arguments for a shell. Quote the complete
        # login-shell program so `bash -lc` receives one command, not `set` plus
        # outer-shell fragments that can contaminate structured stdout.
        argv=["ssh", SSH_TARGET, "bash", "-lc", shlex.quote(command)],
        stdin_text=build_prompt(request, review_files),
    )


def _run(
    argv: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        argv,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()[-1000:]
        raise AdapterError(f"command failed ({process.returncode}): {detail}")
    return process


def _ssh_script(script: str, *, timeout: int = 60) -> str:
    process = _run(["ssh", SSH_TARGET, "bash", "-s"], input_text=script, timeout=timeout)
    return process.stdout


def _expected_skill_digests() -> dict[str, str]:
    release_root = CONTROL_ROOT / "releases/core-development/0.1.0"
    release = yaml.safe_load((release_root / "release.yaml").read_text(encoding="utf-8"))
    expected: dict[str, str] = {}
    for entry in release["skills"]:
        name = str(entry["name"])
        expected[name] = str(entry["bundle_sha256"]).removeprefix("sha256:")
        observed = bundle_digest(release_root / str(entry["path"]))
        if observed != expected[name]:
            raise AdapterError(f"local approved skill bytes drifted: {name}")
    return expected


def validate_tool_versions(versions: dict[str, Any]) -> None:
    patterns = {
        "claude": r"^\d+\.\d+\.\d+ \(Claude Code\)$",
        "flutter": r"^Flutter \d+\.\d+\.\d+\b",
        "dart": r"^Dart SDK version: \d+\.\d+\.\d+\b",
    }
    if set(versions) != set(patterns):
        raise AdapterError("tool version evidence has unexpected keys")
    for name, pattern in patterns.items():
        value = versions[name]
        if not isinstance(value, str) or not re.search(pattern, value):
            raise AdapterError(f"invalid {name} version evidence")


def preflight(
    request: dict[str, Any] | None = None,
    *,
    snapshot: ControllerSnapshot | None = None,
) -> dict[str, Any]:
    expected = snapshot.skill_digests if snapshot else _expected_skill_digests()
    expected_hook_sha256 = (
        snapshot.digests["hook"] if snapshot else sha256_bytes(GOVERNED_HOOK_PATH.read_bytes())
    )
    expected_settings_sha256 = (
        snapshot.digests["session_settings"]
        if snapshot
        else sha256_bytes(SESSION_SETTINGS_PATH.read_bytes())
    )
    expected_json = shlex.quote(json.dumps(expected, sort_keys=True))
    base = str(request["base_commit"]) if request else ""
    branch = str(request.get("branch", "")) if request else ""
    attempt = str(request.get("attempt_id", "")) if request else ""
    script = f"""set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/dev/sdk/flutter/bin:$PATH"
test "$(id -un)" = {shlex.quote(REMOTE_USER)}
test "$(hostname -s)" = {shlex.quote(REMOTE_HOST)}
test "$(command -v claude)" = {shlex.quote(REMOTE_CLAUDE)}
claude auth status --text >/dev/null
test -x "$(command -v tmux)"
test -x "$(command -v git)"
test -x "$(command -v flutter)"
test -x "$(command -v dart)"
test -r {shlex.quote(REMOTE_TOOLCHAIN)}
test "$(git -C {shlex.quote(REMOTE_REPOSITORY)} remote get-url origin)" = {shlex.quote(REMOTE_ORIGIN)}
if git -C {shlex.quote(REMOTE_REPOSITORY)} config --get-regexp '^filter[.]' >/dev/null; then exit 2; fi
test -z "$(git -C {shlex.quote(REMOTE_REPOSITORY)} status --porcelain)"
git -C {shlex.quote(REMOTE_REPOSITORY)} fetch -q origin --prune
git -C {shlex.quote(REMOTE_REPOSITORY)} ls-remote origin HEAD >/dev/null
set +e
push_output=$(git -C {shlex.quote(REMOTE_REPOSITORY)} push --dry-run origin origin/main:refs/heads/__jellyclaude_capability_probe 2>&1)
push_rc=$?
set -e
if [ "$push_rc" -eq 0 ]; then printf 'PUSH_UNEXPECTEDLY_ALLOWED: write access unexpectedly available\\n' >&2; exit 2; fi
printf '%s' "$push_output" | grep -Eqi 'denied|permission|read.only|cannot access|could not read'
git -C {shlex.quote(REMOTE_REPOSITORY)} var GIT_AUTHOR_IDENT >/dev/null
git -C {shlex.quote(REMOTE_REPOSITORY)} var GIT_COMMITTER_IDENT >/dev/null
test "$(sha256sum "$HOME/.claude/hooks/block-dangerous-git.py" | cut -d' ' -f1)" = {shlex.quote(expected_hook_sha256)}
test "$(sha256sum {shlex.quote(REMOTE_SESSION_SETTINGS)} | cut -d' ' -f1)" = {shlex.quote(expected_settings_sha256)}
python3 - <<'PY'
import json,pathlib
home=pathlib.Path.home()
settings=json.loads((home/'.claude/settings.json').read_text())
expected=str(home/'.claude/hooks/block-dangerous-git.py')
entries=settings.get('hooks',{{}}).get('PreToolUse',[])
matches=[item for item in entries if item.get('matcher') == 'Bash' and any(h.get('command') == expected for h in item.get('hooks',[]))]
if len(matches) != 1: raise SystemExit(2)
PY
"""
    if base:
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} cat-file -e {shlex.quote(base + '^{commit}')}\n"
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} merge-base --is-ancestor {shlex.quote(base)} origin/main\n"
    if request and request["mode"] == "review":
        target = str(request["target_commit"])
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} cat-file -e {shlex.quote(target + '^{commit}')}\n"
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} merge-base --is-ancestor {shlex.quote(base)} {shlex.quote(target)}\n"

    if branch:
        script += f"! git -C {shlex.quote(REMOTE_REPOSITORY)} show-ref --verify --quiet refs/heads/{shlex.quote(branch)}\n"
    if attempt:
        worktree = f"{REMOTE_WORKTREE_ROOT}/{attempt}"
        script += f"test ! -e {shlex.quote(worktree)}\n"
    script += f"""python3 - <<'PY'
import hashlib,json,pathlib,struct
expected=json.loads({expected_json})
root=pathlib.Path.home()/'.claude/skills'
def digest(path):
    h=hashlib.sha256()
    files=sorted(x for x in path.rglob('*') if x.is_file())
    if not files: raise SystemExit(2)
    for item in files:
        if item.is_symlink(): raise SystemExit(2)
        rel=item.relative_to(path).as_posix().encode()
        data=item.read_bytes()
        h.update(struct.pack('>Q',len(rel))); h.update(rel)
        h.update(struct.pack('>Q',len(data))); h.update(data)
    return h.hexdigest()
observed={{name:digest(root/name) for name in expected}}
if observed != expected: raise SystemExit(2)
PY
printf 'PREFLIGHT_PASS\\n'
"""
    output = _ssh_script(script, timeout=180)
    if output.strip() != "PREFLIGHT_PASS":
        raise AdapterError("unexpected preflight response")
    versions_script = """set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/dev/sdk/flutter/bin:$PATH"
mkdir -p "$HOME/.cache"
python3 - <<'PY'
import json,pathlib,subprocess
def run(*argv):
    lines=subprocess.run(argv,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.strip().splitlines()
    if not lines: raise SystemExit(2)
    return lines[0]
lock=str(pathlib.Path.home()/'.cache/jellyssh-flutter-version.lock')
print(json.dumps({'claude':run('claude','--version'),'flutter':run('flock','-w','120',lock,'flutter','--version'),'dart':run('dart','--version')},sort_keys=True))
PY
"""
    try:
        versions = json.loads(_ssh_script(versions_script, timeout=150))
    except (json.JSONDecodeError, AdapterError) as exc:
        raise AdapterError("tool version evidence is malformed") from exc
    validate_tool_versions(versions)
    return {
        "status": "PASS",
        "ssh_target": SSH_TARGET,
        "identity": f"{REMOTE_USER}@{REMOTE_HOST}",
        "repository": REMOTE_REPOSITORY,
        "origin": REMOTE_ORIGIN,
        "github_access": "read-only",
        "skill_digests": expected,
        "hook_sha256": expected_hook_sha256,
        "session_settings_sha256": expected_settings_sha256,
        "versions": versions,
    }


def prepare_worktree(request: dict[str, Any]) -> dict[str, str]:
    attempt = str(request["attempt_id"])
    worktree = f"{REMOTE_WORKTREE_ROOT}/{attempt}"
    base = str(request["base_commit"])
    if request["mode"] == "implementation":
        branch = str(request["branch"])
        add = f"git -C {shlex.quote(REMOTE_REPOSITORY)} worktree add -q -b {shlex.quote(branch)} {shlex.quote(worktree)} {shlex.quote(base)}"
    else:
        branch = "DETACHED"
        target = str(request["target_commit"])
        add = f"git -C {shlex.quote(REMOTE_REPOSITORY)} worktree add -q --detach {shlex.quote(worktree)} {shlex.quote(target)}"
    spec_path = str(request["specification"]["path"])
    expected_spec = str(request["specification"]["sha256"])
    script = f"""set -euo pipefail
mkdir -p {shlex.quote(REMOTE_WORKTREE_ROOT)}
test ! -e {shlex.quote(worktree)}
{add}
python3 - {shlex.quote(worktree)} {shlex.quote(spec_path)} {shlex.quote(expected_spec)} <<'PY'
import hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve(strict=True)
relative=pathlib.PurePosixPath(sys.argv[2])
path=root.joinpath(*relative.parts)
current=root
for part in relative.parts:
    current=current/part
    if current.is_symlink(): raise SystemExit(2)
resolved=path.resolve(strict=True)
try: resolved.relative_to(root)
except ValueError: raise SystemExit(2)
if not resolved.is_file(): raise SystemExit(2)
if hashlib.sha256(resolved.read_bytes()).hexdigest() != sys.argv[3]: raise SystemExit(2)
PY
printf '{{"path":"%s","branch":"%s","start_commit":"%s","start_tree":"%s"}}\\n' \\
 {shlex.quote(worktree)} {shlex.quote(branch)} \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD)" \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD^{{tree}})"
"""
    try:
        result = json.loads(_ssh_script(script, timeout=120))
        if request["mode"] == "review":
            result["review_files"] = list_changed_files(base, str(request["target_commit"]))
        return result
    except Exception as exc:
        cleanup_worktree(worktree, branch if request["mode"] == "implementation" else None)
        if isinstance(exc, AdapterError):
            raise
        raise AdapterError("worktree preparation returned malformed JSON") from exc


def cleanup_worktree(worktree: str, branch: str | None = None) -> None:
    script = f"git -C {shlex.quote(REMOTE_REPOSITORY)} worktree remove --force {shlex.quote(worktree)} >/dev/null 2>&1 || true\n"
    if branch:
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} branch -D {shlex.quote(branch)} >/dev/null 2>&1 || true\n"
    _run(["ssh", SSH_TARGET, "bash", "-s"], input_text=script, timeout=60, check=False)


def list_changed_files(base: str, target: str) -> list[str]:
    script = (
        f"git -C {shlex.quote(REMOTE_REPOSITORY)} diff --name-only -z "
        f"{shlex.quote(base)}...{shlex.quote(target)} --"
    )
    output = _ssh_script(script, timeout=60)
    paths = sorted(path for path in output.split("\0") if path)
    if not paths:
        raise AdapterError("review target has no changed files from base")
    return paths


def invoke_claude(
    request: dict[str, Any],
    worktree: str,
    review_files: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = build_claude_command(request, worktree, review_files)
    return _run(
        command.argv,
        input_text=command.stdin_text,
        timeout=int(request["timeout_seconds"]) + 45,
        check=False,
    )


def parse_claude_result(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    validate_output_text(process.stdout or "")
    validate_output_text(process.stderr or "")
    if process.returncode != 0:
        raise AdapterError(f"Claude exited nonzero ({process.returncode})")
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError("Claude returned malformed JSON") from exc
    if not isinstance(payload, dict) or payload.get("is_error") is not False:
        raise AdapterError("Claude returned an error result")
    session = payload.get("session_id")
    terminal_reason = payload.get("terminal_reason")
    models = sorted(str(item) for item in (payload.get("modelUsage") or {}).keys())
    if not isinstance(session, str) or not session or terminal_reason != "completed" or not models:
        raise AdapterError("Claude result lacks required session/model/completion identity")
    result = payload.get("result")
    if not isinstance(result, str):
        raise AdapterError("Claude result text is missing")
    return {
        "session_id": session,
        "terminal_reason": terminal_reason,
        "models": models,
        "summary": result[:2000],
        "_full_text": result,
    }


def validate_review_verdict(summary: str) -> str:
    verdicts = re.findall(r"(?m)^REVIEW_VERDICT=(PASS|BLOCK)$", summary)
    if len(verdicts) != 1:
        raise AdapterError("review must return exactly one valid REVIEW_VERDICT line")
    return verdicts[0]


def validate_requested_model(requested: str, claude: dict[str, Any]) -> None:
    expected = {"sonnet": "sonnet", "opus": "opus"}[requested]
    if not any(expected in model.lower() for model in claude["models"]):
        raise AdapterError(f"requested primary model family absent from Claude result: {requested}")


def validate_git_state(
    request: dict[str, Any],
    state: dict[str, Any],
    start: dict[str, str],
) -> None:
    if state["status"]:
        raise AdapterError("worktree is dirty after Claude run")
    if request["mode"] == "implementation":
        if state["commit"] == request["base_commit"]:
            raise AdapterError("implementation produced no new commit")
        if state["branch"] != request["branch"]:
            raise AdapterError("implementation branch drifted")
        if not state["changed"] or state["tree"] == start["start_tree"]:
            raise AdapterError("implementation produced no net changed files")
    else:
        if state["commit"] != request["target_commit"] or state["tree"] != start["start_tree"]:
            raise AdapterError("review changed the exact target")
        if state["branch"]:
            raise AdapterError("review worktree is not detached")


def validate_precommit_state(request: dict[str, Any], state: dict[str, Any]) -> None:
    if state["commit"] != request["base_commit"]:
        raise AdapterError("worker created or moved a commit before controller commit")
    if state["branch"] != request["branch"]:
        raise AdapterError("implementation branch drifted")
    if not state["status"] or not state["changed"]:
        raise AdapterError("implementation produced no changed files")


def validate_changed_paths(request: dict[str, Any], changed_files: list[str]) -> None:
    allowed = [str(item) for item in request["allowed_paths"]]
    unexpected: list[str] = []
    for changed in changed_files:
        candidate = PurePosixPath(changed)
        if candidate.is_absolute() or any(part in {".", "..", ".git"} for part in candidate.parts):
            unexpected.append(changed)
            continue
        matched = False
        for declared in allowed:
            if declared.endswith("/"):
                prefix = declared.rstrip("/")
                if changed.startswith(prefix + "/"):
                    matched = True
                    break
            elif changed == declared:
                matched = True
                break
        if not matched:
            unexpected.append(changed)
    if unexpected:
        raise AdapterError(f"implementation changed undeclared paths: {', '.join(sorted(unexpected))}")


def validate_checks_preserved_state(before: dict[str, Any], after: dict[str, Any]) -> None:
    if (
        before["status"] != after["status"]
        or before["changed"] != after["changed"]
        or before["state_sha256"] != after["state_sha256"]
    ):
        raise AdapterError("independent checks changed the implementation worktree")


def scan_changed_files(worktree: str, changed_files: list[str]) -> None:
    encoded_paths = shlex.quote(json.dumps(changed_files))
    secret_pattern = shlex.quote(SECRET_VALUE_RE.pattern)
    script = f"""set -euo pipefail
git -C {shlex.quote(worktree)} diff --check
python3 - {shlex.quote(worktree)} {encoded_paths} {secret_pattern} <<'PY'
import json,pathlib,re,sys
root=pathlib.Path(sys.argv[1]).resolve()
paths=json.loads(sys.argv[2])
secret=re.compile(sys.argv[3])
for relative in paths:
    path=root/relative
    try:
        path.relative_to(root)
    except ValueError:
        raise SystemExit(2)
    if path.is_symlink(): raise SystemExit(2)
    if not path.exists(): continue
    if not path.is_file() or path.stat().st_size > 10_000_000: raise SystemExit(2)
    text=path.read_bytes().decode('utf-8','ignore')
    if secret.search(text): raise SystemExit(2)
print('CONTENT_SCAN_PASS')
PY
"""
    output = _ssh_script(script, timeout=60)
    if output.strip() != "CONTENT_SCAN_PASS":
        raise AdapterError("changed-file content scan returned an unexpected result")


def inspect_precommit_worktree(request: dict[str, Any], worktree: str) -> dict[str, Any]:
    base = str(request["base_commit"])
    script = f"""set -euo pipefail
python3 - {shlex.quote(worktree)} {shlex.quote(base)} <<'PY'
import hashlib,json,os,pathlib,struct,subprocess,sys
worktree,base=sys.argv[1:]
def git(*args): return subprocess.check_output(['git','-C',worktree,*args])
status=git('status','--porcelain=v1','-z').decode('utf-8')
tracked=git('diff','--name-only','-z',base,'--').decode('utf-8').split('\\0')
untracked=git('ls-files','--others','--exclude-standard','-z').decode('utf-8').split('\\0')
changed=sorted(set(x for x in tracked+untracked if x))
h=hashlib.sha256(); content=hashlib.sha256(); root=pathlib.Path(worktree).resolve(strict=True)
for relative in changed:
    raw=relative.encode('utf-8'); h.update(struct.pack('>Q',len(raw))); h.update(raw)
    content.update(struct.pack('>Q',len(raw))); content.update(raw)
    path=root/relative
    if not path.exists() and not path.is_symlink():
        h.update(b'DELETED'); content.update(b'DELETED'); continue
    metadata=os.lstat(path); h.update(struct.pack('>Q',metadata.st_mode))
    if path.is_symlink():
        mode=b'120000'; target=os.readlink(path).encode('utf-8'); h.update(struct.pack('>Q',len(target))); h.update(target); data=target
    elif path.is_file():
        mode=b'100755' if metadata.st_mode & 0o111 else b'100644'; data=b''
        with path.open('rb') as handle:
            while chunk:=handle.read(1024*1024): h.update(chunk); data+=chunk
    else: h.update(b'NON_REGULAR'); content.update(b'NON_REGULAR'); continue
    content.update(mode); content.update(struct.pack('>Q',len(data))); content.update(data)
print(json.dumps({{
 'commit':git('rev-parse','HEAD').decode().strip(),
 'tree':git('rev-parse','HEAD^{{tree}}').decode().strip(),
 'branch':git('branch','--show-current').decode().strip(),
 'status':status,
 'changed':changed,
 'state_sha256':h.hexdigest(),
 'content_sha256':content.hexdigest(),
}},sort_keys=True))
PY
"""
    try:
        state = json.loads(_ssh_script(script, timeout=60))
    except (json.JSONDecodeError, AdapterError) as exc:
        raise AdapterError("malformed pre-commit Git state") from exc
    validate_precommit_state(request, state)
    return state


def commit_implementation(
    request: dict[str, Any],
    worktree: str,
    expected_state: dict[str, Any],
) -> dict[str, Any]:
    changed_files = [str(path) for path in expected_state["changed"]]
    paths_json = shlex.quote(json.dumps(changed_files))
    allowed_json = shlex.quote(json.dumps(request["allowed_paths"]))
    secret_pattern = shlex.quote(SECRET_VALUE_RE.pattern)
    script = f"""set -euo pipefail
worktree={shlex.quote(worktree)}
base={shlex.quote(str(request['base_commit']))}
branch={shlex.quote(str(request['branch']))}
expected_state={shlex.quote(str(expected_state['state_sha256']))}
expected_content={shlex.quote(str(expected_state['content_sha256']))}
test "$(git -C "$worktree" rev-parse HEAD)" = "$base"
test "$(git -C "$worktree" branch --show-current)" = "$branch"
if git -C "$worktree" config --get-regexp '^filter[.]' >/dev/null; then exit 2; fi
index=$(mktemp "$HOME/.cache/jellyssh-claude-index.XXXXXX")
trap 'rm -f "$index"' EXIT
rm -f "$index"
export GIT_INDEX_FILE="$index"
git -c core.hooksPath=/dev/null -c commit.gpgSign=false -C "$worktree" read-tree "$base"
tree=$(python3 - "$worktree" "$base" {paths_json} {allowed_json} {secret_pattern} "$expected_state" "$expected_content" <<'PY'
import hashlib,json,os,pathlib,re,struct,subprocess,sys
worktree,base,paths_json,allowed_json,secret_pattern,expected_state,expected_content=sys.argv[1:]
paths=json.loads(paths_json); allowed=json.loads(allowed_json); secret=re.compile(secret_pattern)
root=pathlib.Path(worktree).resolve(strict=True)
def git(*args,input=None): return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgSign=false','-C',worktree,*args],input=input)
status=git('status','--porcelain=v1','-z').decode()
tracked=git('diff','--name-only','-z',base,'--').decode().split('\\0')
untracked=git('ls-files','--others','--exclude-standard','-z').decode().split('\\0')
changed=sorted(set(x for x in tracked+untracked if x))
if changed != paths or not status: raise SystemExit(2)
def permitted(path): return any(path == item.rstrip('/') or (item.endswith('/') and path.startswith(item)) for item in allowed)
if any(not permitted(path) for path in changed): raise SystemExit(2)
state=hashlib.sha256(); content=hashlib.sha256(); entries=[]
for relative in changed:
 raw=relative.encode(); state.update(struct.pack('>Q',len(raw))); state.update(raw); content.update(struct.pack('>Q',len(raw))); content.update(raw)
 path=root/relative
 if not path.exists() and not path.is_symlink():
  state.update(b'DELETED'); content.update(b'DELETED'); entries.append((relative,None,None)); continue
 metadata=os.lstat(path); state.update(struct.pack('>Q',metadata.st_mode))
 if path.is_symlink():
  mode=b'120000'; data=os.readlink(path).encode(); state.update(struct.pack('>Q',len(data))); state.update(data)
 elif path.is_file():
  mode=b'100755' if metadata.st_mode & 0o111 else b'100644'; data=path.read_bytes(); state.update(data)
 else: raise SystemExit(2)
 if secret.search(data.decode('utf-8','ignore')): raise SystemExit(2)
 content.update(mode); content.update(struct.pack('>Q',len(data))); content.update(data); entries.append((relative,mode,data))
if state.hexdigest() != expected_state or content.hexdigest() != expected_content: raise SystemExit(2)
for relative,mode,data in entries:
 if mode is None: git('update-index','--force-remove','--',relative)
 else:
  blob=git('hash-object','-w','--stdin','--no-filters',input=data).decode().strip()
  git('update-index','--add','--cacheinfo',mode.decode(),blob,relative)
tree=git('write-tree').decode().strip()
immutable=hashlib.sha256()
for relative in changed:
 raw=relative.encode(); immutable.update(struct.pack('>Q',len(raw))); immutable.update(raw)
 entry=git('ls-tree',tree,'--',relative).decode().strip()
 if not entry: immutable.update(b'DELETED'); continue
 mode=entry.split()[0].encode(); data=git('show',tree+':'+relative)
 if secret.search(data.decode('utf-8','ignore')): raise SystemExit(2)
 immutable.update(mode); immutable.update(struct.pack('>Q',len(data))); immutable.update(data)
if immutable.hexdigest() != expected_content: raise SystemExit(2)
print(tree)
PY
)
commit=$(printf '%s\n' 'chore: apply governed Claude implementation' | git -c core.hooksPath=/dev/null -c commit.gpgSign=false -C "$worktree" commit-tree "$tree" -p "$base")
unset GIT_INDEX_FILE
rm -f "$index"
git -c core.hooksPath=/dev/null -c commit.gpgSign=false -C "$worktree" update-ref "refs/heads/$branch" "$commit" "$base"
git -c core.hooksPath=/dev/null -c commit.gpgSign=false -C "$worktree" reset --hard -q "$commit"
python3 - "$worktree" "$base" <<'PY'
import json,subprocess,sys
worktree,base=sys.argv[1:]
def git(*args): return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgSign=false','-C',worktree,*args])
changed=[x for x in git('diff','--name-only','-z',base+'...HEAD','--').decode().split('\\0') if x]
print(json.dumps({{
 'commit':git('rev-parse','HEAD').decode().strip(),
 'tree':git('rev-parse','HEAD^{{tree}}').decode().strip(),
 'branch':git('branch','--show-current').decode().strip(),
 'status':git('status','--porcelain=v1','-z').decode(),
 'changed':sorted(changed),
}},sort_keys=True))
PY
"""
    try:
        return json.loads(_ssh_script(script, timeout=120))
    except (json.JSONDecodeError, AdapterError) as exc:
        raise AdapterError("controller commit returned malformed Git state") from exc


def inspect_worktree(request: dict[str, Any], worktree: str, start: dict[str, str]) -> dict[str, Any]:
    base = str(request["base_commit"])
    script = f"""set -euo pipefail
printf '{{"commit":"%s","tree":"%s","branch":"%s","status":%s,"changed":%s}}\\n' \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD)" \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD^{{tree}})" \\
 "$(git -C {shlex.quote(worktree)} branch --show-current)" \\
 "$(git -C {shlex.quote(worktree)} status --porcelain=v1 -z | python3 -c 'import json,sys; print(json.dumps(sys.stdin.buffer.read().decode()))')" \\
 "$(git -C {shlex.quote(worktree)} diff --name-only {shlex.quote(base)}...HEAD -z | python3 -c 'import json,sys; print(json.dumps([x for x in sys.stdin.buffer.read().decode().split("\\0") if x]))')"
"""
    try:
        state = json.loads(_ssh_script(script, timeout=60))
    except (json.JSONDecodeError, AdapterError) as exc:
        raise AdapterError("malformed post-run Git state") from exc
    validate_git_state(request, state, start)
    if request["mode"] == "implementation":
        _ssh_script(
            f"git -C {shlex.quote(worktree)} merge-base --is-ancestor {shlex.quote(base)} {shlex.quote(state['commit'])}\n",
            timeout=30,
        )
    return state


def run_checks(request: dict[str, Any], worktree: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in request["checks"]:
        command = CHECK_COMMANDS[str(name)]
        remote = (
            f"set -euo pipefail; . {shlex.quote(REMOTE_TOOLCHAIN)}; "
            f"cd {shlex.quote(worktree + '/app')}; "
            f"exec timeout --signal=TERM --kill-after=30 {min(int(request['timeout_seconds']), 1200)} {command}"
        )
        process = _run(
            ["ssh", SSH_TARGET, "bash", "-lc", shlex.quote(remote)],
            timeout=min(int(request["timeout_seconds"]), 1200) + 45,
            check=False,
        )
        combined = ((process.stdout or "") + (process.stderr or ""))[-4000:]
        validate_output_text(combined)
        results.append({"name": name, "exit_code": process.returncode, "passed": process.returncode == 0, "output": combined})
        if process.returncode != 0:
            raise AdapterError(f"independent check failed: {name}")
    return results


def _result_base(
    request: dict[str, Any],
    request_digest: str,
    started: str,
    snapshot: ControllerSnapshot,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "adapter_version": ADAPTER_VERSION,
        "attempt_id": request["attempt_id"],
        "mode": request["mode"],
        "request_sha256": request_digest,
        "started_at": started,
        "finished_at": utc_now(),
        "route": {
            "ssh_target": SSH_TARGET,
            "identity": f"{REMOTE_USER}@{REMOTE_HOST}",
            "repository": REMOTE_REPOSITORY,
        },
        "controller_commit": snapshot.commit,
        "controller_digests": snapshot.digests,
        "verdict": "BLOCK",
        "blockers": [],
        "checks": [],
    }


def _validate_result(result: dict[str, Any], *, snapshot: ControllerSnapshot | None = None) -> None:
    schema = snapshot.result_schema if snapshot else _load_json(RESULT_SCHEMA_PATH, "Claude worker result schema")
    try:
        jsonschema.validate(result, schema)
    except jsonschema.ValidationError as exc:
        raise AdapterError(f"internal result schema failure: {exc.message}") from exc


def execute(request_path: Path, *, allow_test_output: bool = False) -> dict[str, Any]:
    started = utc_now()
    snapshot = capture_controller_snapshot()
    request = load_and_validate_request(
        request_path,
        allow_test_output=allow_test_output,
        snapshot=snapshot,
    )
    output_path = _validate_output_path(str(request["output_path"]), allow_test_output=allow_test_output)
    request_digest = sha256_bytes(canonical_json(request))
    result = _result_base(request, request_digest, started, snapshot)
    worktree: str | None = None
    try:
        result["preflight"] = preflight(request, snapshot=snapshot)
        start = prepare_worktree(request)
        worktree = start["path"]
        result["worktree"] = worktree
        result["start_commit"] = start["start_commit"]
        result["start_tree"] = start["start_tree"]
        process = invoke_claude(request, worktree, start.get("review_files"))
        validate_output_text(process.stdout or "")
        validate_output_text(process.stderr or "")
        raw_payload = process.stdout.encode("utf-8")
        if len(raw_payload) > 4_000_000:
            raise AdapterError("Claude raw output exceeds evidence size limit")
        result["raw_claude_sha256"] = sha256_bytes(raw_payload)
        result["raw_claude_b64"] = base64.b64encode(raw_payload).decode("ascii")
        result["claude"] = parse_claude_result(process)
        full_worker_text = result["claude"].pop("_full_text")
        validate_requested_model(str(request["model"]), result["claude"])
        if request["mode"] == "implementation":
            precommit = inspect_precommit_worktree(request, worktree)
            validate_changed_paths(request, precommit["changed"])
            result["checks"] = run_checks(request, worktree)
            after_checks = inspect_precommit_worktree(request, worktree)
            validate_checks_preserved_state(precommit, after_checks)
            scan_changed_files(worktree, after_checks["changed"])
            state = commit_implementation(request, worktree, after_checks)
            validate_git_state(request, state, start)
        else:
            state = inspect_worktree(request, worktree, start)
            result["checks"] = run_checks(request, worktree)
            state = inspect_worktree(request, worktree, start)
            result["review_verdict"] = validate_review_verdict(full_worker_text)
            if result["review_verdict"] != "PASS":
                raise AdapterError("Claude advisory review returned BLOCK")
        result["final_commit"] = state["commit"]
        result["final_tree"] = state["tree"]
        result["branch"] = state["branch"] or None
        result["changed_files"] = state["changed"]
        result["verdict"] = "PASS"
    except subprocess.TimeoutExpired as exc:
        result["verdict"] = "TIMEOUT"
        result["blockers"].append(f"Claude timeout after {exc.timeout} seconds")
    except AdapterError as exc:
        result["verdict"] = "BLOCK"
        result["blockers"].append(str(exc))
    except Exception as exc:  # defensive fail-closed boundary
        result["verdict"] = "BLOCK"
        result["blockers"].append(f"unexpected adapter failure: {type(exc).__name__}")
    result["finished_at"] = utc_now()
    _validate_result(result, snapshot=snapshot)
    atomic_write_json(output_path, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subcommands.add_parser("preflight", help="run live read-only capability preflight")
    preflight_parser.add_argument("--output", type=Path)
    run_parser = subcommands.add_parser("run", help="execute one schema-bound request")
    run_parser.add_argument("--request", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preflight":
            snapshot = capture_controller_snapshot()
            result = preflight(snapshot=snapshot)
            if args.output:
                atomic_write_json(args.output, result)
            print(canonical_json(result).decode("utf-8"))
            return 0
        result = execute(args.request)
        print(canonical_json(result).decode("utf-8"))
        return 0 if result["verdict"] == "PASS" else 2
    except (AdapterError, OSError, subprocess.SubprocessError) as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
