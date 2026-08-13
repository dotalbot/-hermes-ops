#!/usr/bin/env python3
"""Fail-closed Jellyberry-to-Jellybase Claude Code adapter."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import struct
import subprocess
import sys
import tempfile
from typing import Any

import jsonschema
import yaml


ADAPTER_VERSION = "0.1.0"
CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = CONTROL_ROOT / "schemas/claude-worker-request.schema.json"
RESULT_SCHEMA_PATH = CONTROL_ROOT / "schemas/claude-worker-result.schema.json"
GOVERNED_HOOK_PATH = CONTROL_ROOT / "assets/claude-worker/block-dangerous-git.py"
SSH_TARGET = "agent-claude"
REMOTE_USER = "jellyclaude"
REMOTE_HOST = "jellybase"
REMOTE_REPOSITORY = "/home/jellyclaude/dev_projects/jellyssh"
REMOTE_WORKTREE_ROOT = "/home/jellyclaude/dev_projects/jellyssh-worktrees"
REMOTE_ORIGIN = "git@github-jellyssh:dotalbot/jellyssh.git"
REMOTE_CLAUDE = "/home/jellyclaude/.local/bin/claude"
REMOTE_TOOLCHAIN = "/home/jellyclaude/.config/jellyssh/toolchain.env"
ALLOWED_OUTPUT_ROOT = Path("/home/jellybot/projects/jellyssh-claude-adapter/evidence")
SECRET_KEY_RE = re.compile(r"(?i)(password|passwd|passphrase|secret|token|api[_-]?key|private[_-]?key|credential)")
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:gh[opusr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|"
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def controller_digests() -> dict[str, str]:
    paths = {
        "adapter": Path(__file__).resolve(),
        "request_schema": SCHEMA_PATH,
        "result_schema": RESULT_SCHEMA_PATH,
        "hook": GOVERNED_HOOK_PATH,
    }
    return {name: sha256_bytes(path.read_bytes()) for name, path in paths.items()}


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


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Hard-link publication is atomic and refuses to overwrite an immutable
        # attempt if another process won the same-path race after preflight.
        os.link(temporary, path)
        os.unlink(temporary)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


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


def _validate_output_path(path: str, *, allow_test_output: bool = False) -> Path:
    output = Path(path)
    if not output.is_absolute():
        raise AdapterError("output path must be absolute")
    if not allow_test_output:
        try:
            output.relative_to(ALLOWED_OUTPUT_ROOT)
        except ValueError as exc:
            raise AdapterError("output path is outside the adapter evidence root") from exc
    if output.is_symlink() or output.parent.is_symlink():
        raise AdapterError("output path must not use symlinks")
    if output.exists() or output.with_suffix(".claude.raw.json").exists():
        raise AdapterError("evidence path already exists; attempts are immutable")
    return output


def load_and_validate_request(path: Path, *, allow_test_output: bool = False) -> dict[str, Any]:
    request = _load_json(path, "Claude worker request")
    schema = _load_json(SCHEMA_PATH, "Claude worker request schema")
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
    return request


def build_prompt(request: dict[str, Any]) -> str:
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
        return common + """Use /implement and /tdd where a pre-agreed public behavior seam exists. Work only in the current worktree. Commit only intended files to the current branch. Finish with a concise summary of commit, changed files, tests, and remaining risks. The controller will independently verify every claim.\n"""
    return common + f"""Target commit: {request['target_commit']}
This is read-only advisory review. Use the two independent Standards and Specification axes from /code-review. Do not edit, commit, push, or run commands that mutate tracked files. End with exactly one machine-readable line: REVIEW_VERDICT=PASS or REVIEW_VERDICT=BLOCK. The controller will independently verify immutability.\n"""


def build_claude_command(request: dict[str, Any], worktree: str) -> WorkerCommand:
    worktree_path = PurePosixPath(worktree)
    expected_root = PurePosixPath(REMOTE_WORKTREE_ROOT)
    if expected_root not in worktree_path.parents:
        raise AdapterError("worktree is outside the fixed remote root")
    if request["mode"] == "implementation":
        permission = "auto"
        tools = "Read,Glob,Grep,Edit,Write,Bash,Skill"
    else:
        permission = "plan"
        tools = "Read,Glob,Grep,Bash,Skill"
    remote_argv = [
        REMOTE_CLAUDE,
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        permission,
        "--model",
        str(request["model"]),
        "--effort",
        str(request["effort"]),
        "--allowedTools",
        tools,
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
        stdin_text=build_prompt(request),
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


def preflight(request: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = _expected_skill_digests()
    expected_hook_sha256 = sha256_bytes(GOVERNED_HOOK_PATH.read_bytes())
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
        script += f"git -C {shlex.quote(REMOTE_REPOSITORY)} merge-base --is-ancestor {shlex.quote(target)} origin/main\n"
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
python3 - <<'PY'
import json,subprocess
def run(*argv): return subprocess.run(argv,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.strip().splitlines()[0]
print(json.dumps({'claude':run('claude','--version'),'flutter':run('flutter','--version'),'dart':run('dart','--version')},sort_keys=True))
PY
"""
    try:
        versions = json.loads(_ssh_script(versions_script, timeout=60))
    except (json.JSONDecodeError, AdapterError) as exc:
        raise AdapterError("tool version evidence is malformed") from exc
    return {
        "status": "PASS",
        "ssh_target": SSH_TARGET,
        "identity": f"{REMOTE_USER}@{REMOTE_HOST}",
        "repository": REMOTE_REPOSITORY,
        "origin": REMOTE_ORIGIN,
        "github_access": "read-only",
        "skill_digests": expected,
        "hook_sha256": expected_hook_sha256,
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
actual=$(sha256sum {shlex.quote(worktree + '/' + spec_path)} | cut -d' ' -f1)
test "$actual" = {shlex.quote(expected_spec)}
printf '{{"path":"%s","branch":"%s","start_commit":"%s","start_tree":"%s"}}\\n' \\
 {shlex.quote(worktree)} {shlex.quote(branch)} \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD)" \\
 "$(git -C {shlex.quote(worktree)} rev-parse HEAD^{{tree}})"
"""
    try:
        return json.loads(_ssh_script(script, timeout=120))
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


def invoke_claude(request: dict[str, Any], worktree: str) -> subprocess.CompletedProcess[str]:
    command = build_claude_command(request, worktree)
    return _run(
        command.argv,
        input_text=command.stdin_text,
        timeout=int(request["timeout_seconds"]) + 45,
        check=False,
    )


def parse_claude_result(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()[-1000:]
        raise AdapterError(f"Claude exited nonzero ({process.returncode}): {detail}")
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
    if state["status"]:
        raise AdapterError("worktree is dirty after Claude run")
    if request["mode"] == "implementation":
        if state["commit"] == base:
            raise AdapterError("implementation produced no new commit")
        if state["branch"] != request["branch"]:
            raise AdapterError("implementation branch drifted")
        _ssh_script(
            f"git -C {shlex.quote(worktree)} merge-base --is-ancestor {shlex.quote(base)} {shlex.quote(state['commit'])}\n",
            timeout=30,
        )
    else:
        if state["commit"] != request["target_commit"] or state["tree"] != start["start_tree"]:
            raise AdapterError("review changed the exact target")
        if state["branch"]:
            raise AdapterError("review worktree is not detached")
    return state


def run_checks(request: dict[str, Any], worktree: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in request["checks"]:
        command = CHECK_COMMANDS[str(name)]
        remote = (
            f"set -euo pipefail; . {shlex.quote(REMOTE_TOOLCHAIN)}; "
            f"cd {shlex.quote(worktree + '/app')}; {command}"
        )
        process = _run(
            ["ssh", SSH_TARGET, "bash", "-lc", remote],
            timeout=min(int(request["timeout_seconds"]), 1200),
            check=False,
        )
        combined = ((process.stdout or "") + (process.stderr or ""))[-4000:]
        results.append({"name": name, "exit_code": process.returncode, "passed": process.returncode == 0, "output": combined})
        if process.returncode != 0:
            raise AdapterError(f"independent check failed: {name}")
    return results


def _result_base(request: dict[str, Any], request_digest: str, started: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
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
        "controller_digests": controller_digests(),
        "verdict": "BLOCK",
        "blockers": [],
        "checks": [],
    }


def _validate_result(result: dict[str, Any]) -> None:
    schema = _load_json(RESULT_SCHEMA_PATH, "Claude worker result schema")
    try:
        jsonschema.validate(result, schema)
    except jsonschema.ValidationError as exc:
        raise AdapterError(f"internal result schema failure: {exc.message}") from exc


def execute(request_path: Path, *, allow_test_output: bool = False) -> dict[str, Any]:
    started = utc_now()
    request = load_and_validate_request(request_path, allow_test_output=allow_test_output)
    output_path = _validate_output_path(str(request["output_path"]), allow_test_output=allow_test_output)
    request_digest = sha256_bytes(canonical_json(request))
    result = _result_base(request, request_digest, started)
    worktree: str | None = None
    try:
        result["preflight"] = preflight(request)
        start = prepare_worktree(request)
        worktree = start["path"]
        result["worktree"] = worktree
        result["start_commit"] = start["start_commit"]
        result["start_tree"] = start["start_tree"]
        process = invoke_claude(request, worktree)
        raw_payload = process.stdout.encode("utf-8")
        raw_path = output_path.with_suffix(".claude.raw.json")
        atomic_write_bytes(raw_path, raw_payload)
        result["raw_claude_sha256"] = sha256_bytes(raw_payload)
        result["claude"] = parse_claude_result(process)
        validate_requested_model(str(request["model"]), result["claude"])
        state = inspect_worktree(request, worktree, start)
        result["final_commit"] = state["commit"]
        result["final_tree"] = state["tree"]
        result["branch"] = state["branch"] or None
        result["changed_files"] = state["changed"]
        result["checks"] = run_checks(request, worktree)
        if request["mode"] == "review":
            result["review_verdict"] = validate_review_verdict(result["claude"]["summary"])
            if result["review_verdict"] != "PASS":
                raise AdapterError("Claude advisory review returned BLOCK")
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
    _validate_result(result)
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
            result = preflight()
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
