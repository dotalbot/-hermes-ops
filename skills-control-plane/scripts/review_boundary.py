#!/usr/bin/env python3
"""Restricted, read-only repository operations for independent review.

The boundary reads tracked blobs from an exact commit. Worktree reads, arbitrary
commands, writes, Git helpers/hooks, credential-like paths, and pathspec magic
are deliberately unavailable. Optional SSH transport targets the separately
owned Jellybase review checkout.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Iterable


_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/^~+-]{0,199}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9._+@/-]{1,500}$")
_SSH_TARGET_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}@[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
_DENIED_NAMES = {
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "key.properties",
    "local.properties",
    "secrets.yaml",
    "secrets.yml",
}
_DENIED_SUFFIXES = {".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"}
_MAX_TEXT_BYTES = 512 * 1024
_MAX_GIT_BYTES = 1024 * 1024
_PINNED_KNOWN_HOSTS = "/home/jellybot/.hermes/profiles/jellybase_jellyssh_reviewer/jellybase_known_hosts"
_PROJECT_STATE_SHA256 = "sha256:85ea70abf69c056069a1b3dfb74ec5d52ef789db14f8c703e5e7c6d8bab135f9"
_TREE_HASH_CODE = r'''import hashlib,os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]); h=hashlib.sha256()
for p in sorted(root.rglob("*"),key=lambda x:x.relative_to(root).as_posix().encode()):
 r=p.relative_to(root).as_posix().encode(); mode=p.lstat().st_mode
 if stat.S_ISDIR(mode): kind=b"D"; data=b""
 elif stat.S_ISREG(mode): kind=b"F"; data=p.read_bytes()
 else: raise SystemExit("non-regular project-state entry")
 for part in (kind,r,data): h.update(len(part).to_bytes(8,"big")); h.update(part)
print("sha256:"+h.hexdigest())'''
_MATERIALIZE_COMMIT_CODE = r'''import os,subprocess,sys
from pathlib import Path,PurePosixPath
repo,commit,dest=sys.argv[1],sys.argv[2],Path(sys.argv[3]); dest.mkdir(mode=0o700)
git_env=dict(os.environ); git_env["GIT_NO_REPLACE_OBJECTS"]="1"
raw=subprocess.check_output(["git","-c","core.fsmonitor=false","-c","core.hooksPath=/dev/null","-C",repo,"ls-tree","-r","-z","--full-tree",commit],env=git_env)
records=[record for record in raw.split(b"\0") if record]
if len(records)>5000: raise SystemExit("too many tracked files")
total=0
for record in records:
 meta,sep,raw_path=record.partition(b"\t")
 if not sep: raise SystemExit("ambiguous tree record")
 mode,kind,oid=meta.split(b" "); path=raw_path.decode("utf-8","strict"); rel=PurePosixPath(path)
 parts=rel.parts; lower=[part.lower() for part in parts]; base=lower[-1] if lower else ""
 denied=(not parts or rel.is_absolute() or any(part in {"",".",".."} for part in parts) or mode not in {b"100644",b"100755"} or kind!=b"blob" or base==".env" or base.startswith(".env.") or base in {".npmrc",".pypirc",".netrc","credentials.json","key.properties","local.properties","secrets.yaml","secrets.yml"} or any(base.endswith(s) for s in (".jks",".key",".keystore",".p12",".pem",".pfx")))
 if denied: raise SystemExit("unsafe tracked sandbox path")
 data=subprocess.check_output(["git","-c","core.fsmonitor=false","-c","core.hooksPath=/dev/null","-C",repo,"cat-file","blob",oid.decode("ascii")],env=git_env); total+=len(data)
 if len(data)>8*1024*1024 or total>256*1024*1024: raise SystemExit("sandbox source size limit exceeded")
 target=dest.joinpath(*parts); target.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700 if mode==b"100755" else 0o600)
 try:
  view=memoryview(data)
  while view: view=view[os.write(fd,view):]
  os.fsync(fd)
 finally: os.close(fd)
'''
_FLUTTER_TEST_SUMMARY_CODE = r'''import json,re,sys
from pathlib import Path

MAX_DIAGNOSTICS=8
MAX_DIAGNOSTIC_CHARS=320
MAX_EVENTS=100000
MAX_LINE_BYTES=1048576

path=Path(sys.argv[1])
diagnostics=[]
passed=failed=skipped=0
protocol_version=None
terminal="missing"
done_success=None
start_seen=False
done_seen=False
structural_error=False
error_events=0
started={}
completed=set()
event_count=0

try:
 check_name=sys.argv[4]
except IndexError:
 check_name="invalid"
 structural_error=True
if check_name not in {"flutter-test","sftp-browser-test","terminal-behaviour-test"}:
 check_name="invalid"
 structural_error=True

try:
 exit_code=int(sys.argv[2])
except (IndexError,ValueError):
 exit_code=-1
 structural_error=True

def append_diagnostic(message):
 if len(diagnostics)>=MAX_DIAGNOSTICS:
  return
 clean=" ".join(str(message).split()).encode("ascii","backslashreplace").decode("ascii")
 diagnostics.append(clean[:MAX_DIAGNOSTIC_CHARS] or "unspecified reporter error")

def add_diagnostic(message):
 global structural_error
 structural_error=True
 append_diagnostic(message)

try:
 with path.open("r",encoding="utf-8",errors="strict") as stream:
  for line_number,line in enumerate(stream,1):
   if line_number>MAX_EVENTS:
    add_diagnostic("machine event limit exceeded")
    break
   if len(line.encode("utf-8"))>MAX_LINE_BYTES:
    add_diagnostic(f"line {line_number}: machine event exceeds byte limit")
    break
   if not line.strip():
    continue
   event_count+=1
   if done_seen:
    add_diagnostic(f"line {line_number}: event after terminal done")
    break
   try:
    event=json.loads(line)
   except (TypeError,ValueError,json.JSONDecodeError):
    add_diagnostic(f"line {line_number}: invalid machine JSON")
    break
   if isinstance(event,list):
    progress=event[0] if len(event)==1 and isinstance(event[0],dict) else None
    params=progress.get("params") if isinstance(progress,dict) else None
    service_uri=params.get("vmServiceUri") if isinstance(params,dict) else None
    if (
     not isinstance(progress,dict)
     or set(progress)!={"event","params"}
     or progress.get("event")!="test.startedProcess"
     or not isinstance(params,dict)
     or set(params)!={"vmServiceUri"}
     or (service_uri is not None and (not isinstance(service_uri,str) or len(service_uri)>2048))
    ):
     add_diagnostic(f"line {line_number}: invalid Flutter machine progress event")
     break
    continue
   if not isinstance(event,dict) or not isinstance(event.get("type"),str):
    add_diagnostic(f"line {line_number}: invalid machine event shape")
    break
   event_type=event["type"]
   if event_type=="start":
    protocol=event.get("protocolVersion")
    if start_seen or event_count!=1:
     add_diagnostic(f"line {line_number}: duplicate or noninitial start event")
     break
    if not isinstance(protocol,str) or len(protocol)>32 or not re.fullmatch(r"0\.1\.\d+",protocol):
     add_diagnostic(f"line {line_number}: unsupported protocol version")
     break
    start_seen=True
    protocol_version=protocol
    continue
   if not start_seen:
    add_diagnostic(f"line {line_number}: event before start")
    break
   if event_type=="testStart":
    test=event.get("test")
    test_id=test.get("id") if isinstance(test,dict) else None
    name=test.get("name") if isinstance(test,dict) else None
    if type(test_id) is not int or test_id in started or not isinstance(name,str):
     add_diagnostic(f"line {line_number}: invalid or duplicate testStart")
     break
    started[test_id]=" ".join(name.split())[:200]
   elif event_type=="testDone":
    test_id=event.get("testID")
    result=event.get("result")
    hidden=event.get("hidden")
    was_skipped=event.get("skipped",False)
    if (
     type(test_id) is not int
     or test_id not in started
     or test_id in completed
     or not isinstance(result,str)
     or type(hidden) is not bool
     or type(was_skipped) is not bool
    ):
     add_diagnostic(f"line {line_number}: invalid or duplicate testDone")
     break
    completed.add(test_id)
    if result in {"failure","error"}:
     failed+=1
     add_diagnostic(f"testID {test_id} {result}: {started[test_id]}")
    elif hidden:
     continue
    elif was_skipped or result=="skipped":
     skipped+=1
    elif result=="success":
     passed+=1
    else:
     add_diagnostic(f"line {line_number}: unknown test result")
     break
   elif event_type=="error":
    test_id=event.get("testID")
    message=event.get("error")
    stack_trace=event.get("stackTrace")
    if (
     type(test_id) is not int
     or test_id not in started
     or not isinstance(message,str)
     or (stack_trace is not None and not isinstance(stack_trace,str))
    ):
     add_diagnostic(f"line {line_number}: malformed error event")
     break
    error_events+=1
    add_diagnostic(f"testID {test_id} error: {message}")
   elif event_type=="done":
    success=event.get("success")
    if type(success) is not bool:
     add_diagnostic(f"line {line_number}: invalid terminal success value")
     break
    done_seen=True
    terminal="done"
    done_success=success
   elif event_type=="suite":
    suite=event.get("suite")
    if (
     not isinstance(suite,dict)
     or type(suite.get("id")) is not int
     or not isinstance(suite.get("platform"),str)
     or not isinstance(suite.get("path"),str)
    ):
     add_diagnostic(f"line {line_number}: malformed suite event")
     break
   elif event_type=="allSuites":
    if type(event.get("count")) is not int or event["count"]<0:
     add_diagnostic(f"line {line_number}: malformed allSuites event")
     break
   elif event_type=="group":
    group=event.get("group")
    if (
     not isinstance(group,dict)
     or type(group.get("id")) is not int
     or type(group.get("testCount")) is not int
     or group["testCount"]<0
    ):
     add_diagnostic(f"line {line_number}: malformed group event")
     break
   elif event_type=="print":
    if (
     type(event.get("testID")) is not int
     or event["testID"] not in started
     or not isinstance(event.get("messageType"),str)
     or not isinstance(event.get("message"),str)
    ):
     add_diagnostic(f"line {line_number}: malformed print event")
     break
   else:
    add_diagnostic(f"line {line_number}: unknown machine event type")
    break
except (OSError,UnicodeError) as exc:
 add_diagnostic(f"machine stream unavailable: {type(exc).__name__}")

total=passed+failed+skipped
if not start_seen:
 add_diagnostic("start event missing")
if not done_seen:
 add_diagnostic("terminal done event missing")
if exit_code!=0:
 add_diagnostic(f"flutter test exited {exit_code}")
if done_success is not True:
 add_diagnostic("terminal done did not report success")
if failed:
 add_diagnostic(f"failed test count is {failed}")
if error_events:
 add_diagnostic(f"error event count is {error_events}")
if set(started)!=completed:
 add_diagnostic(f"incomplete test count is {len(set(started)-completed)}")
if total<1:
 add_diagnostic("no visible tests completed")

try:
 with Path(sys.argv[3]).open("r",encoding="utf-8",errors="strict") as errors:
  for line_number,line in enumerate(errors,1):
   if line_number>MAX_DIAGNOSTICS:
    append_diagnostic("stderr diagnostics truncated")
    break
   if len(line.encode("utf-8"))>MAX_LINE_BYTES:
    append_diagnostic(f"stderr line {line_number} exceeds byte limit")
    continue
   if line.strip():
    append_diagnostic(f"stderr: {line}")
except (IndexError,OSError,UnicodeError) as exc:
 add_diagnostic(f"stderr diagnostics unavailable: {type(exc).__name__}")

success=(
 not structural_error
 and start_seen
 and done_seen
 and done_success is True
 and exit_code==0
 and failed==0
 and error_events==0
 and total>0
)
summary={
 "schema_version":1,
 "check":check_name,
 "reporter":"json",
 "protocol_version":protocol_version,
 "exit_code":exit_code,
 "success":success,
 "terminal":terminal,
 "passed":passed,
 "failed":failed,
 "skipped":skipped,
 "total":total,
 "diagnostics":diagnostics,
}
print(json.dumps(summary,sort_keys=True,separators=(",",":")))
raise SystemExit(0 if success else 1)'''
_ALLOWED_CHECKS = {
    "sandbox-self-check",
    "diff-check",
    "head-clean",
    "submodule-status",
    "flutter-analyze",
    "flutter-test",
    "sftp-browser-test",
    "terminal-behaviour-test",
    "dart-format-check",
}


class ReviewBoundaryError(RuntimeError):
    """A fail-closed reviewer boundary rejection."""


class ReviewRepository:
    def __init__(
        self,
        root: str | Path,
        expected_commit: str | None = None,
        ssh_target: str | None = None,
        allowed_refs: Iterable[str] | None = None,
        base_commit: str | None = None,
        specification_commit: str | None = None,
    ):
        raw_root = Path(str(root)).expanduser()
        if not raw_root.is_absolute() or ".." in raw_root.parts:
            raise ReviewBoundaryError("review root must be an absolute non-traversing path")
        self.ssh_target = (ssh_target or "").strip()
        if self.ssh_target and not _SSH_TARGET_RE.fullmatch(self.ssh_target):
            raise ReviewBoundaryError("invalid SSH review target")
        if self.ssh_target:
            self.root = raw_root
        else:
            candidate = raw_root.resolve(strict=True)
            if not candidate.is_dir():
                raise ReviewBoundaryError("review root is not a directory")
            self.root = candidate
        self.expected_commit = expected_commit or ""
        if not re.fullmatch(r"[0-9a-f]{40}", self.expected_commit):
            raise ReviewBoundaryError("expected commit must be a full lowercase SHA-1")
        self.allowed_refs = {item.strip() for item in (allowed_refs or []) if item.strip()}
        self.allowed_refs.add(self.expected_commit)
        if any(not re.fullmatch(r"[0-9a-f]{40}", item) for item in self.allowed_refs):
            raise ReviewBoundaryError("allowed refs must be full lowercase SHA-1 values")
        self.base_commit = (base_commit or "").strip()
        if self.base_commit and self.base_commit not in self.allowed_refs:
            raise ReviewBoundaryError("base commit must be one of the exact allowed refs")
        self.specification_commit = (specification_commit or "").strip()
        if self.specification_commit:
            if not re.fullmatch(r"[0-9a-f]{40}", self.specification_commit):
                raise ReviewBoundaryError("specification commit must be a full lowercase SHA-1")
            if not self.base_commit:
                raise ReviewBoundaryError("specification commit requires an exact base commit")
            exact_review_refs = {
                self.base_commit,
                self.specification_commit,
                self.expected_commit,
            }
            if self.allowed_refs != exact_review_refs:
                raise ReviewBoundaryError("review refs must be exactly base, specification, and target")
        top = self._git(["rev-parse", "--show-toplevel"]).strip()
        if top != str(self.root):
            raise ReviewBoundaryError("review root must be the Git repository root")
        if self.specification_commit:
            try:
                self._git(["merge-base", "--is-ancestor", self.base_commit, self.specification_commit])
                self._git(["merge-base", "--is-ancestor", self.specification_commit, self.expected_commit])
            except ReviewBoundaryError as exc:
                raise ReviewBoundaryError("review commit chain must be base <= specification <= target") from exc

    @staticmethod
    def _bounded(raw: bytes, limit: int) -> str:
        if len(raw) > limit:
            raise ReviewBoundaryError(f"approved operation output exceeds {limit} bytes")
        return raw.decode("utf-8", errors="strict")

    def _run(self, command: list[str], timeout: int = 60) -> bytes:
        local_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", str(Path.home())),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_PAGER": "cat",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
        }
        argv = command
        if self.ssh_target:
            remote_env = [
                "env",
                "-i",
                "HOME=/home/jellydev",
                "PATH=/usr/bin:/bin",
                "LANG=C.UTF-8",
                "LC_ALL=C.UTF-8",
                "GIT_CONFIG_NOSYSTEM=1",
                "GIT_CONFIG_SYSTEM=/dev/null",
                "GIT_CONFIG_GLOBAL=/dev/null",
                "GIT_ATTR_NOSYSTEM=1",
                "GIT_TERMINAL_PROMPT=0",
                "GIT_PAGER=cat",
                "GIT_OPTIONAL_LOCKS=0",
                "GIT_NO_REPLACE_OBJECTS=1",
                "XDG_RUNTIME_DIR=/run/user/1002",
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1002/bus",
                *command,
            ]
            argv = [
                "ssh",
                "-F",
                "/dev/null",
                "-o",
                "BatchMode=yes",
                "-o",
                "ClearAllForwardings=yes",
                "-o",
                "PermitLocalCommand=no",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                f"UserKnownHostsFile={_PINNED_KNOWN_HOSTS}",
                "-o",
                "GlobalKnownHostsFile=/dev/null",
                "-o",
                "HostKeyAlias=jellybase-lan-pinned",
                "-o",
                "HostKeyAlgorithms=ssh-ed25519",
                "-o",
                "HostName=192.168.1.2",
                "-o",
                "Port=22",
                "-o",
                "IdentityFile=/home/jellybot/.ssh/id_ed25519",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "ProxyCommand=none",
                "-o",
                "ProxyJump=none",
                "--",
                self.ssh_target,
                shlex.join(remote_env),
            ]
        try:
            proc = subprocess.run(
                argv,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env=local_env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReviewBoundaryError(f"approved operation failed: {type(exc).__name__}") from exc
        output = self._bounded(proc.stdout, _MAX_GIT_BYTES)
        if proc.returncode != 0:
            raise ReviewBoundaryError(
                f"approved operation failed with exit {proc.returncode}: {output}"
            )
        return proc.stdout

    def _git_bytes(self, args: list[str], timeout: int = 60) -> bytes:
        return self._run(
            [
                "git",
                "--no-optional-locks",
                "-c",
                "core.pager=cat",
                "-c",
                "diff.external=",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "credential.helper=",
                "-c",
                "protocol.file.allow=never",
                "-C",
                str(self.root),
                *args,
            ],
            timeout=timeout,
        )

    def _git(self, args: list[str], timeout: int = 60) -> str:
        return self._bounded(self._git_bytes(args, timeout), _MAX_GIT_BYTES)

    def _validate_ref(self, ref: str) -> str:
        if ref != "HEAD" and not re.fullmatch(r"[0-9a-f]{40}", ref):
            raise ReviewBoundaryError("Git ref must be HEAD or a full lowercase SHA-1")
        if ref == "HEAD":
            resolved = self._git(["rev-parse", "HEAD"]).strip()
            if resolved != self.expected_commit:
                raise ReviewBoundaryError("HEAD does not resolve to the exact review target")
        else:
            resolved = self._git(["rev-parse", "--verify", ref + "^{commit}"]).strip()
        if resolved not in self.allowed_refs:
            raise ReviewBoundaryError("ref is outside the exact review authority set")
        return resolved

    @staticmethod
    def _validate_relative_path(relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not _PATH_RE.fullmatch(relative_path):
            raise ReviewBoundaryError("path contains disallowed characters")
        raw = Path(relative_path)
        if raw.is_absolute() or not raw.parts or ".." in raw.parts or ".git" in raw.parts:
            raise ReviewBoundaryError("path is outside the review contract")
        lowered = [part.lower() for part in raw.parts]
        name = lowered[-1]
        if (
            any(part in {".git", ".gnupg", ".ssh"} for part in lowered)
            or name.startswith(".env")
            or name.startswith("id_")
            or name in _DENIED_NAMES
            or Path(name).suffix in _DENIED_SUFFIXES
            or "secret" in name
            or "credential" in name
        ):
            raise ReviewBoundaryError("credential-like path is denied")
        return raw

    @staticmethod
    def _literal_pathspec(path: str) -> str:
        return ":(literal)" + path

    def _tree_record(self, ref: str, relative_path: str) -> tuple[str, str]:
        safe_ref = self._validate_ref(ref)
        raw = self._validate_relative_path(relative_path).as_posix()
        output = self._git_bytes(
            ["ls-tree", "-z", safe_ref, "--", self._literal_pathspec(raw)]
        )
        records = [item for item in output.split(b"\0") if item]
        exact: list[tuple[str, str]] = []
        for record in records:
            meta, separator, path_bytes = record.partition(b"\t")
            if not separator:
                continue
            path = path_bytes.decode("utf-8", errors="strict")
            if path == raw:
                exact.append((meta.split(b" ", 1)[0].decode("ascii"), path))
        if len(exact) != 1:
            raise ReviewBoundaryError(f"review path is not one tracked object at target commit: {raw}")
        return exact[0]

    def _assert_regular_blob(self, ref: str, relative_path: str) -> str:
        mode, path = self._tree_record(ref, relative_path)
        if mode not in {"100644", "100755"}:
            raise ReviewBoundaryError("review path is not a tracked regular file")
        return path

    def metadata(self) -> dict[str, object]:
        head = self._git(["rev-parse", "HEAD"]).strip()
        head_tree = self._git(["rev-parse", "HEAD^{tree}"]).strip()
        branch = self._git(["branch", "--show-current"]).strip()
        status = self._git(["status", "--short", "--branch", "--untracked-files=all"])
        try:
            origin: str | None = self._git(["remote", "get-url", "origin"]).strip()
        except ReviewBoundaryError:
            origin = None
        if origin and "://" in origin and "@" in origin.split("://", 1)[1].split("/", 1)[0]:
            origin = "[credential-bearing URL redacted]"
        remote_hostname: str | None = None
        remote_machine_id_sha256: str | None = None
        if self.ssh_target:
            remote_hostname = self._bounded(self._run(["hostname"], timeout=15), 256).strip()
            machine_line = self._bounded(self._run(["sha256sum", "/etc/machine-id"], timeout=15), 512).strip()
            remote_machine_id_sha256 = machine_line.split(None, 1)[0] if machine_line else None
        return {
            "root": str(self.root),
            "transport": "ssh" if self.ssh_target else "local",
            "ssh_target": self.ssh_target or None,
            "head": head,
            "head_tree": head_tree,
            "branch": branch,
            "status": status,
            "origin": origin,
            "expected_commit": self.expected_commit,
            "expected_commit_matches": head == self.expected_commit,
            "remote_hostname": remote_hostname,
            "remote_machine_id_sha256": remote_machine_id_sha256,
            "write_tools_exposed": False,
        }

    def read_text(self, relative_path: str, start_line: int = 1, max_lines: int = 400) -> str:
        if start_line < 1 or not 1 <= max_lines <= 1000:
            raise ReviewBoundaryError("line bounds are invalid")
        text = self.git_show(self.expected_commit, relative_path)
        lines = text.splitlines()
        selected = lines[start_line - 1 : start_line - 1 + max_lines]
        return "\n".join(f"{start_line + i}|{line}" for i, line in enumerate(selected))

    def list_files(self, pattern: str = "*", limit: int = 200) -> list[str]:
        if not 1 <= limit <= 500:
            raise ReviewBoundaryError("file limit is invalid")
        if not isinstance(pattern, str) or len(pattern) > 500 or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ReviewBoundaryError("pattern is outside the review contract")
        output = self._git_bytes(["ls-tree", "-r", "-z", self.expected_commit])
        matches: list[str] = []
        for record in output.split(b"\0"):
            if not record:
                continue
            meta, separator, path_bytes = record.partition(b"\t")
            if not separator or meta.split(b" ", 1)[0] not in {b"100644", b"100755"}:
                continue
            rel = path_bytes.decode("utf-8", errors="strict")
            try:
                self._validate_relative_path(rel)
            except ReviewBoundaryError:
                continue
            if fnmatch.fnmatchcase(rel, pattern) or fnmatch.fnmatchcase(Path(rel).name, pattern):
                matches.append(rel)
                if len(matches) >= limit:
                    break
        return matches

    def git_diff(
        self,
        base: str,
        target: str = "HEAD",
        paths: Iterable[str] | None = None,
    ) -> str:
        base_ref = self._validate_ref(base)
        target_ref = self._validate_ref(target)
        requested_paths = list(paths or [])
        if not requested_paths or len(requested_paths) > 100:
            raise ReviewBoundaryError("diff requires 1 to 100 explicit contained paths")
        requested_specs = [
            self._literal_pathspec(self._validate_relative_path(item).as_posix())
            for item in requested_paths
        ]
        changed_raw = self._git_bytes(
            [
                "diff",
                "--no-renames",
                "--name-only",
                "-z",
                f"{base_ref}...{target_ref}",
                "--",
                *requested_specs,
            ]
        )
        changed_paths: list[str] = []
        for raw_path in changed_raw.split(b"\0"):
            if not raw_path:
                continue
            path = self._validate_relative_path(raw_path.decode("utf-8", errors="strict")).as_posix()
            for ref in (base_ref, target_ref):
                entry = self._git_bytes(["ls-tree", "-z", ref, "--", self._literal_pathspec(path)])
                if entry:
                    record = entry.rstrip(b"\0")
                    meta, separator, emitted_path = record.partition(b"\t")
                    if (
                        not separator
                        or emitted_path.decode("utf-8", errors="strict") != path
                        or meta.split(b" ", 1)[0] not in {b"100644", b"100755"}
                    ):
                        raise ReviewBoundaryError("diff includes a non-regular or ambiguous tracked path")
            changed_paths.append(self._literal_pathspec(path))
            if len(changed_paths) > 500:
                raise ReviewBoundaryError("diff expands to more than 500 tracked files")
        if not changed_paths:
            return ""
        return self._git(
            [
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--unified=80",
                f"{base_ref}...{target_ref}",
                "--",
                *changed_paths,
            ]
        )

    def git_show(self, ref: str, relative_path: str) -> str:
        safe_ref = self._validate_ref(ref)
        path = self._assert_regular_blob(safe_ref, relative_path)
        size_text = self._git(["cat-file", "-s", f"{safe_ref}:{path}"]).strip()
        try:
            size = int(size_text)
        except ValueError as exc:
            raise ReviewBoundaryError("tracked object size is invalid") from exc
        if size > _MAX_TEXT_BYTES:
            raise ReviewBoundaryError("file exceeds the reviewer read limit")
        raw = self._git_bytes(["show", "--no-ext-diff", "--no-textconv", "--format=", f"{safe_ref}:{path}"])
        if len(raw) > _MAX_TEXT_BYTES:
            raise ReviewBoundaryError("file exceeds the reviewer read limit")
        try:
            return raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ReviewBoundaryError("binary or non-UTF-8 files are not readable") from exc

    def validate_tracked_paths(self, ref: str, paths: Iterable[str]) -> list[str]:
        safe_ref = self._validate_ref(ref)
        safe_paths = [self._validate_relative_path(item).as_posix() for item in paths]
        if not safe_paths or len(safe_paths) > 100:
            raise ReviewBoundaryError("tracked-path validation requires 1 to 100 paths")
        for path in safe_paths:
            self._assert_regular_blob(safe_ref, path)
        return safe_paths

    def _run_sandboxed_flutter_check(self, name: str) -> str:
        if not self.ssh_target:
            raise ReviewBoundaryError("Flutter checks require the isolated Jellybase SSH review workspace")
        flutter_tool = [
            "/opt/flutter/bin/cache/dart-sdk/bin/dart",
            "/opt/flutter/bin/cache/flutter_tools.snapshot",
            "--no-version-check",
        ]
        check_command = {
            "flutter-analyze": [*flutter_tool, "analyze", "--no-pub"],
            "flutter-test": [*flutter_tool, "test", "--machine", "--no-pub"],
            "sftp-browser-test": [
                *flutter_tool,
                "test",
                "--machine",
                "--no-pub",
                "test/screens/sftp/sftp_browser_screen_test.dart",
            ],
            "terminal-behaviour-test": [
                *flutter_tool,
                "test",
                "--machine",
                "--no-pub",
                "test/screens/settings/terminal_behaviour_settings_screen_test.dart",
            ],
            "dart-format-check": [
                "/opt/flutter/bin/cache/dart-sdk/bin/dart",
                "format",
                "--output=none",
                "--set-exit-if-changed",
                ".",
            ],
        }[name]
        root = shlex.quote(str(self.root))
        commit = shlex.quote(self.expected_commit)
        inner = shlex.join(check_command)
        sandbox_prefix = (
            "set -eu; "
            "cp -a /review-input/repo /workspace/repo; "
            "cp -a /review-input/home /workspace/home; "
            "cp -a /review-input/tools /workspace/tools; "
            "cd /workspace/repo/app; "
        )
        if name in {"flutter-test", "sftp-browser-test", "terminal-behaviour-test"}:
            machine_output = "/workspace/flutter-test.machine.jsonl"
            diagnostic_output = "/workspace/flutter-test.stderr"
            sandbox_command = (
                sandbox_prefix
                + "set +e; "
                + f"{inner} >{shlex.quote(machine_output)} 2>{shlex.quote(diagnostic_output)}; "
                + "flutter_exit=$?; set -e; "
                + f"exec /usr/bin/python3 -c {shlex.quote(_FLUTTER_TEST_SUMMARY_CODE)} "
                + f"{shlex.quote(machine_output)} \"$flutter_exit\" "
                + f"{shlex.quote(diagnostic_output)} {shlex.quote(name)}"
            )
        else:
            sandbox_command = sandbox_prefix + f"exec {inner}"
        script = f"""set -euo pipefail
umask 077
scratch=$(mktemp -d /var/tmp/jellyssh-review-check.XXXXXX)
container="jellyssh-review-${{scratch##*.}}"
cleanup() {{ docker rm -f "$container" >/dev/null 2>&1 || true; rm -rf -- "$scratch"; }}
trap cleanup EXIT HUP INT TERM
python3 -c {shlex.quote(_MATERIALIZE_COMMIT_CODE)} {root} {commit} "$scratch/repo"
test ! -e "$scratch/repo/app/.dart_tool"
cp -a --no-dereference /var/tmp/jellyssh-review-runtime/project-state "$scratch/repo/app/.dart_tool"
actual_project_state=$(python3 -c {shlex.quote(_TREE_HASH_CODE)} "$scratch/repo/app/.dart_tool")
test "$actual_project_state" = {shlex.quote(_PROJECT_STATE_SHA256)}
mkdir -p "$scratch/home"
mkdir -p "$scratch/tools"
cp /usr/bin/which.debianutils "$scratch/tools/which"
timeout --signal=TERM --kill-after=10 300 docker run --rm --pull=never --name "$container" \
  --network none --ipc none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --pids-limit 256 --memory 4g --memory-swap 4g --cpus 2 --ulimit fsize=268435456:268435456 --ulimit nproc=256:256 \
  --user 1002:1002 --tmpfs /tmp:rw,nosuid,nodev,size=512m \
  --tmpfs /workspace:rw,exec,nosuid,nodev,size=1073741824,mode=1777 \
  --mount type=bind,src=/usr,dst=/usr,readonly \
  --mount type=bind,src=/bin,dst=/bin,readonly \
  --mount type=bind,src=/lib,dst=/lib,readonly \
  --mount type=bind,src=/lib64,dst=/lib64,readonly \
  --mount type=bind,src=/var/tmp/jellyssh-review-runtime/flutter,dst=/opt/flutter,readonly \
  --mount type=bind,src=/var/tmp/jellyssh-review-runtime/flutter,dst=/home/jellydev/dev/sdk/flutter-3.44.9,readonly \
  --mount type=bind,src=/var/tmp/jellyssh-review-runtime/jdk-17,dst=/opt/jdk,readonly \
  --mount type=bind,src=/var/tmp/jellyssh-review-runtime/dart-pub,dst=/pub-cache,readonly \
  --mount type=bind,src=/var/tmp/jellyssh-review-runtime/dart-pub,dst=/home/jellydev/.cache/dart-pub,readonly \
  --mount type=bind,src="$scratch",dst=/review-input,readonly \
  --workdir /workspace \
  --env HOME=/workspace/home --env PUB_CACHE=/pub-cache --env JAVA_HOME=/opt/jdk \
  --env FLUTTER_ROOT=/opt/flutter --env FLUTTER_ALREADY_LOCKED=true \
  --env FLUTTER_SUPPRESS_ANALYTICS=true --env CI=true \
  --env PATH=/opt/flutter/bin:/opt/jdk/bin:/workspace/tools:/usr/bin:/bin \
  --entrypoint /bin/sh \
  sha256:a2d49ea686c2adfe3c992e47dc3b5e7fa6e6b5055609400dc2acaeb241c829f4 \
  -c {shlex.quote(sandbox_command)}
"""
        command = ["/bin/bash", "-c", script]
        output = self._run(command, timeout=330)
        limit = 4096 if name in {"flutter-test", "sftp-browser-test", "terminal-behaviour-test"} else _MAX_GIT_BYTES
        return self._bounded(output, limit) or "PASS"

    def _run_sandbox_self_check(self) -> str:
        if not self.ssh_target:
            raise ReviewBoundaryError("sandbox self-check requires Jellybase SSH")
        script = """set -euo pipefail
umask 077
scratch=$(mktemp -d /var/tmp/jellyssh-sandbox-self-check.XXXXXX)
container="jellyssh-sandbox-${scratch##*.}"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; rm -rf -- "$scratch"; }
trap cleanup EXIT HUP INT TERM
mkdir "$scratch/input"
touch "$scratch/input/marker"
timeout --signal=TERM --kill-after=5 30 docker run --rm --pull=never --name "$container" \
  --network none --ipc none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --pids-limit 32 --memory 128m --memory-swap 128m --cpus 1 --ulimit nproc=32:32 --user 1002:1002 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m \
  --tmpfs /workspace:rw,exec,nosuid,nodev,size=8388608,mode=1777 \
  --mount type=bind,src="$scratch/input",dst=/review-input,readonly \
  --workdir /workspace --entrypoint /bin/sh \
  sha256:a2d49ea686c2adfe3c992e47dc3b5e7fa6e6b5055609400dc2acaeb241c829f4 \
  -c 'test ! -e /home/jellydev/.ssh; test ! -S /run/docker.sock; test "$(cat /proc/1/comm)" = sh; test -f /review-input/marker; if touch /etc/forbidden 2>/dev/null; then exit 91; fi; if wget -q -T 1 -O /tmp/out http://1.1.1.1 2>/dev/null; then exit 92; fi; if touch /review-input/forbidden 2>/dev/null; then exit 93; fi; touch /workspace/pass; if dd if=/dev/zero of=/workspace/overflow bs=1048576 count=9 2>/dev/null; then exit 94; fi'
printf 'SANDBOX_SELF_CHECK=PASS\n'
"""
        return self._bounded(self._run(["/bin/bash", "-c", script], timeout=60), 4096)

    def run_check(self, name: str) -> str:
        if name not in _ALLOWED_CHECKS:
            raise ReviewBoundaryError("check is not allowlisted")
        if name == "sandbox-self-check":
            return self._run_sandbox_self_check()
        if name in {
            "flutter-analyze",
            "flutter-test",
            "sftp-browser-test",
            "terminal-behaviour-test",
            "dart-format-check",
        }:
            return self._run_sandboxed_flutter_check(name)
        if name == "diff-check" and not self.base_commit:
            raise ReviewBoundaryError("diff-check requires an exact base commit")
        checks = {
            "diff-check": ["diff", "--check", self.base_commit, self.expected_commit],
            "head-clean": ["status", "--porcelain=v1", "--untracked-files=all"],
            "submodule-status": ["submodule", "status", "--recursive"],
        }
        result = self._git(checks[name])
        if name == "head-clean":
            return "CLEAN" if not result.strip() else result
        return result or "PASS"
