from __future__ import annotations

import json
import base64
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import shlex
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import jsonschema


CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CONTROL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import claude_worker_adapter as adapter


BASE = "1" * 40
TARGET = "2" * 40
SPEC_SHA = "3" * 64


def preflight_result() -> dict[str, object]:
    return {
        "status": "PASS",
        "ssh_target": "agent-claude",
        "identity": "jellyclaude@jellybase",
        "repository": "/home/jellyclaude/dev_projects/jellyssh",
        "origin": "git@github-jellyssh:dotalbot/jellyssh.git",
        "github_access": "read-only",
        "skill_digests": {"code-review": "a" * 64},
        "hook_sha256": "b" * 64,
        "session_settings_sha256": "c" * 64,
        "versions": {
            "claude": "2.1.228 (Claude Code)",
            "flutter": "Flutter 3.44.9 stable",
            "dart": "Dart SDK version: 3.12.2 stable",
        },
    }


def implementation_request(output: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "attempt_id": "feature-001",
        "mode": "implementation",
        "base_commit": BASE,
        "branch": "feat/example-change",
        "allowed_paths": ["app/lib/example.dart", "app/test/example_test.dart"],
        "specification": {"path": "docs/specifications/SPEC-001-example.md", "sha256": SPEC_SHA},
        "task": "Implement the accepted specification using TDD.",
        "checks": ["format", "analyze", "test"],
        "model": "sonnet",
        "effort": "high",
        "timeout_seconds": 600,
        "output_path": output,
    }


class RequestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads((CONTROL_ROOT / "schemas/claude-worker-request.schema.json").read_text())

    def test_valid_implementation_request(self) -> None:
        jsonschema.validate(implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json"), self.schema)

    def test_valid_review_request(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request.pop("allowed_paths")
        request["target_commit"] = TARGET
        jsonschema.validate(request, self.schema)

    def test_unknown_field_is_rejected(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["ssh_target"] = "attacker"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request, self.schema)

    def test_bad_commit_branch_check_and_specification_path_are_rejected(self) -> None:
        mutations = [
            ("base_commit", "HEAD"),
            ("branch", "main"),
            ("checks", ["arbitrary-shell"]),
            ("specification", {"path": "../secret.md", "sha256": SPEC_SHA}),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
                request[field] = value
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(request, self.schema)

    def test_review_cannot_supply_branch(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("allowed_paths")
        request["target_commit"] = TARGET
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request, self.schema)

    def test_implementation_requires_declared_changed_paths(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request.pop("allowed_paths")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request, self.schema)

    def test_review_cannot_supply_declared_changed_paths(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request["target_commit"] = TARGET
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(request, self.schema)

    def test_secret_shaped_task_is_rejected(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["task"] = "Use token=ghp_abcdefghijklmnopqrstuvwxyz123456"
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_request_content(request)

    def test_existing_evidence_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            output.write_text("{}\n")
            with self.assertRaises(adapter.AdapterError):
                adapter._validate_output_path(str(output), allow_test_output=True)


class CommandConstructionTests(unittest.TestCase):
    def test_landlock_launcher_denies_undeclared_sibling_and_git_writes(self) -> None:
        libc = ctypes.CDLL(None, use_errno=True)
        abi = libc.syscall(444, 0, 0, 1)
        if abi < 0 and ctypes.get_errno() in {errno.ENOSYS, errno.EOPNOTSUPP}:
            self.skipTest("local runtime cannot exercise Landlock; live Jellybase probe covers it")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "sandbox/source"
            home = root / "sandbox/home"
            gitdir = root / "sandbox/git"
            declared = workspace / "app/lib/declared.dart"
            sibling = workspace / "app/lib/sibling.dart"
            shared = root / "shared-repository"
            account = root / "account-secret"
            declared.parent.mkdir(parents=True)
            home.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            shared.mkdir()
            declared.write_text("before\n")
            sibling.write_text("sibling\n")
            account.write_text("account\n")
            (gitdir / "config").write_text("git\n")
            request = implementation_request(str(root / "result.json"))
            request["allowed_paths"] = ["app/lib/declared.dart"]
            with mock.patch.object(adapter, "REMOTE_SANDBOX_ROOT", str(root / "sandbox")), mock.patch.object(
                adapter, "REMOTE_CLAUDE", "/usr/bin/python3"
            ):
                command = adapter.build_claude_command(request, str(workspace))
            rendered = shlex.split(command.argv[-1])[0]
            launcher = rendered.split("; exec ", 1)[1]
            marker = "-- /usr/bin/timeout"
            launcher = launcher[: launcher.index(marker)]
            probe = (
                "import pathlib,sys; "
                "pathlib.Path(sys.argv[1]).write_text('changed\\n'); "
                "fail=[]; "
                "\nfor p in map(pathlib.Path,sys.argv[2:]):\n"
                " try: p.write_text('bad\\n'); fail.append(str(p))\n"
                " except OSError: pass\n"
                "raise SystemExit(1 if fail else 0)"
            )
            launcher += " -- /usr/bin/python3 -c " + shlex.quote(probe) + " " + " ".join(
                shlex.quote(str(path)) for path in [declared, sibling, gitdir / "config", account]
            )
            process = subprocess.run(
                ["bash", "-lc", f"export HOME={shlex.quote(str(home))} WORKSPACE={shlex.quote(str(workspace))}; exec {launcher}"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(declared.read_text(), "changed\n")
            self.assertEqual(sibling.read_text(), "sibling\n")
            self.assertEqual((gitdir / "config").read_text(), "git\n")
            self.assertEqual(account.read_text(), "account\n")

    def test_worker_runs_in_landlock_materialization_without_git_or_toolchain_source(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        workspace = "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source"
        command = adapter.build_claude_command(request, workspace)
        rendered = " ".join(command.argv)
        self.assertIn("landlock_create_ruleset", rendered)
        self.assertIn("WRITE_FILE", rendered)
        self.assertIn(workspace, rendered)
        self.assertIn("/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/home", rendered)
        self.assertNotIn("toolchain.env", rendered)
        self.assertIn(adapter.REMOTE_CLAUDE, rendered)
        self.assertIn("exec env -i", rendered)
        self.assertIn("--read-dir /proc", rendered)
        self.assertIn("--read-dir /sys", rendered)
        self.assertNotIn("SSH_AUTH_SOCK", rendered)
        self.assertNotIn("OPENAI_API_KEY", rendered)

    def test_materialization_uses_disposable_no_hardlink_clone(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("stop")) as ssh_script, mock.patch.object(
            adapter, "cleanup_worktree"
        ):
            with self.assertRaises(adapter.AdapterError):
                adapter.prepare_worktree(request)
        script = ssh_script.call_args.args[0]
        self.assertIn("clone --no-hardlinks", script)
        self.assertIn("test -f \"$source/.git\"", script)
        self.assertIn('mv -- "$source/.git" "$sandbox/gitlink"', script)
        self.assertIn('test ! -e "$source/.git"', script)
        self.assertIn("refs/replace", script)
        self.assertNotIn("worktree add", script)

    def test_worktree_preparation_rejects_symlinked_specification(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("command failed")) as ssh_script, mock.patch.object(
            adapter, "cleanup_worktree"
        ):
            with self.assertRaises(adapter.AdapterError):
                adapter.prepare_worktree(request)
        script = ssh_script.call_args.args[0]
        self.assertIn("is_symlink()", script)
        self.assertIn("relative_to(root)", script)
        self.assertNotIn("actual=$(sha256sum", script)

    def test_wrong_target_or_specification_digest_blocks_worktree_preparation(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request.pop("allowed_paths")
        request["target_commit"] = TARGET
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("command failed")) as ssh_script, mock.patch.object(
            adapter, "cleanup_worktree"
        ) as cleanup:
            with self.assertRaises(adapter.AdapterError):
                adapter.prepare_worktree(request)
        script = ssh_script.call_args.args[0]
        self.assertIn(TARGET, script)
        self.assertIn(SPEC_SHA, script)
        self.assertIn("hexdigest() != sys.argv[3]", script)
        cleanup.assert_called_once()

    def test_git_link_restore_is_controller_owned_and_fail_closed(self) -> None:
        worktree = "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source"
        with mock.patch.object(adapter, "_ssh_script", return_value="") as ssh_script:
            adapter.restore_worktree_git_link(worktree)
        script = ssh_script.call_args.args[0]
        self.assertIn('test ! -e "$source/.git"', script)
        self.assertIn('test -f "$sandbox/gitlink"', script)
        self.assertIn('mv -- "$sandbox/gitlink" "$source/.git"', script)

    def test_prompt_is_stdin_and_fixed_route_is_used(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        command = adapter.build_claude_command(request, "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source")
        self.assertEqual(command.ssh_target, "agent-claude")
        self.assertEqual(command.stdin_text, adapter.build_prompt(request))
        self.assertNotIn(str(request["task"]), " ".join(command.argv))
        self.assertNotIn("--dangerously-skip-permissions", command.argv)
        self.assertNotIn("push", " ".join(command.argv))
        self.assertIn("--permission-mode auto", " ".join(command.argv))
        self.assertNotIn("Bash", " ".join(command.argv))
        self.assertIn("--settings /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/home/.claude/adapter-session-settings.json", " ".join(command.argv))
        rendered = shlex.split(command.argv[-1])[0]
        self.assertIn("--setting-sources user", rendered)
        self.assertIn("--read-file /run/systemd/resolve/stub-resolv.conf", rendered)
        self.assertNotIn("--read-dir /run", rendered)
        self.assertNotIn("--read-dir /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/git", rendered)
        self.assertIn("timeout --signal=TERM --kill-after=30", " ".join(command.argv))
        self.assertEqual(command.argv[:4], ["ssh", "agent-claude", "bash", "-lc"])
        self.assertTrue(command.argv[-1].startswith("'set -euo pipefail;"))
        self.assertTrue(command.argv[-1].endswith("'"))

    def test_implementation_restricts_available_tools_and_disables_mcp(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        command = adapter.build_claude_command(
            request,
            "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
        )
        rendered = " ".join(command.argv)
        self.assertIn("--tools Read,Glob,Grep,Edit,Write,Skill", rendered)
        self.assertIn("--allowedTools Read,Glob,Grep,Edit,Write,Skill", rendered)
        self.assertIn("--strict-mcp-config", rendered)
        self.assertIn("--disallowedTools", rendered)
        self.assertIn("mcp__*", rendered)
        self.assertNotIn("Bash", rendered)

    def test_review_uses_plan_mode_and_no_edit_tool(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request.pop("allowed_paths")
        request["target_commit"] = TARGET
        command = adapter.build_claude_command(request, "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/review-feature-001/source")
        self.assertIn("--permission-mode plan", " ".join(command.argv))
        self.assertNotIn("Edit", " ".join(command.argv))
        self.assertNotIn("Write", " ".join(command.argv))
        self.assertIn("--tools Read,Glob,Grep,Skill", " ".join(command.argv))
        self.assertIn("--allowedTools Read,Glob,Grep,Skill", " ".join(command.argv))
        self.assertIn("--strict-mcp-config", " ".join(command.argv))
        self.assertIn("--disallowedTools", " ".join(command.argv))
        self.assertIn("mcp__*", " ".join(command.argv))

    def test_preflight_source_pins_the_governed_hook_and_settings_binding(self) -> None:
        source = (SCRIPTS / "claude_worker_adapter.py").read_text()
        self.assertIn("GOVERNED_HOOK_PATH", source)
        self.assertIn("expected_hook_sha256", source)
        self.assertIn("settings.json", source)
        self.assertIn("block-dangerous-git.py", source)
        self.assertIn("PUSH_UNEXPECTEDLY_ALLOWED", source)
        self.assertIn("write access unexpectedly available", source)
        self.assertIn("readlink -f /etc/resolv.conf", source)
        self.assertIn("REMOTE_RESOLVER_CONFIG", source)

    def test_independent_checks_quote_the_complete_login_shell_program(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        completed = subprocess.CompletedProcess(["ssh"], 0, "ok", "")
        with mock.patch.object(adapter, "_run", return_value=completed) as run:
            adapter.run_checks(request, "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source")
        execution_calls = [call for call in run.call_args_list if call.args[0][:4] == ["ssh", "agent-claude", "bash", "-lc"]]
        self.assertEqual(len(execution_calls), 1)
        argv = execution_calls[0].args[0]
        self.assertEqual(argv[:4], ["ssh", "agent-claude", "bash", "-lc"])
        self.assertTrue(argv[-1].startswith("'set -euo pipefail;"))
        self.assertTrue(argv[-1].endswith("'"))
        self.assertNotIn("toolchain.env", argv[-1])
        self.assertIn(adapter.REMOTE_DART, argv[-1])
        self.assertIn(adapter.REMOTE_FLUTTER_SNAPSHOT, argv[-1])
        self.assertNotIn(adapter.REMOTE_FLUTTER + " analyze", argv[-1])
        self.assertIn("landlock_create_ruleset", argv[-1])
        self.assertIn("exec env -i", argv[-1])
        self.assertIn("--read-dir /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/check-source", argv[-1])
        self.assertNotIn("--read-dir /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", argv[-1])
        self.assertNotIn("--write-dir /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", argv[-1])
        self.assertIn("--write-dir /home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/check-home", argv[-1])

    def test_format_check_targets_only_scope_validated_allowed_paths(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["format"]
        passed = subprocess.CompletedProcess(["ssh"], 0, "Formatted 2 files (0 changed).\n", "")
        cleanup = subprocess.CompletedProcess(["ssh"], 0, "", "")
        with mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
            adapter, "_run", side_effect=[passed, cleanup]
        ) as run:
            adapter.run_checks(
                request,
                "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
            )
        execution = next(
            call.args[0][-1]
            for call in run.call_args_list
            if call.args[0][:4] == ["ssh", "agent-claude", "bash", "-lc"]
        )
        self.assertIn(
            "format --output=none --set-exit-if-changed -- lib/example.dart test/example_test.dart",
            execution,
        )
        self.assertNotIn("--set-exit-if-changed lib/ test/", execution)
        self.assertNotIn("--set-exit-if-changed lib/example.dart", execution)

    def test_preflight_requires_oauth_validity_beyond_attempt_timeout(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("stop")) as ssh_script:
            with self.assertRaises(adapter.AdapterError):
                adapter.preflight(request)
        script = ssh_script.call_args.args[0]
        self.assertIn(".claude/.credentials.json", script)
        self.assertIn("expiresAt", script)
        self.assertIn("refreshTokenExpiresAt", script)
        self.assertIn("minimum_validity_seconds=900", script)
        self.assertNotIn("accessToken", script)
        self.assertNotIn("refreshToken]", script)

    def test_oauth_expiry_gate_executes_without_exposing_token_values(self) -> None:
        gate = adapter.oauth_expiry_check_script(900)
        with tempfile.TemporaryDirectory() as temp:
            credentials = Path(temp) / ".claude/.credentials.json"
            credentials.parent.mkdir()
            for expiry, expected_exit in [(0, 2), (9_000_000_000_000_000, 0)]:
                with self.subTest(expiry=expiry):
                    credentials.write_text(json.dumps({
                        "claudeAiOauth": {
                            "expiresAt": expiry,
                            "refreshTokenExpiresAt": expiry,
                        }
                    }))
                    process = subprocess.run(
                        ["bash", "-c", gate],
                        env={**os.environ, "HOME": temp},
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertEqual(process.returncode, expected_exit)
                    self.assertEqual(process.stdout, "")
                    self.assertEqual(process.stderr, "")

    def test_oauth_expiry_gate_rejects_non_finite_malformed_and_boolean_values(self) -> None:
        gate = adapter.oauth_expiry_check_script(900)
        future = 9_000_000_000_000_000
        cases = (
            ("expired", "0", 2),
            ("future", str(future), 0),
            ("nan", "NaN", 2),
            ("pos_inf", "Infinity", 2),
            ("neg_inf", "-Infinity", 2),
            ("string", '"soon"', 2),
            ("null", "null", 2),
            ("bool_true", "true", 2),
            ("bool_false", "false", 2),
        )
        with tempfile.TemporaryDirectory() as temp:
            credentials = Path(temp) / ".claude/.credentials.json"
            credentials.parent.mkdir()
            for name, literal, expected_exit in cases:
                for field in ("expiresAt", "refreshTokenExpiresAt"):
                    other = "refreshTokenExpiresAt" if field == "expiresAt" else "expiresAt"
                    with self.subTest(name=name, field=field):
                        credentials.write_text(
                            '{"claudeAiOauth":{"%s":%s,"%s":%s}}' % (field, literal, other, future)
                        )
                        process = subprocess.run(
                            ["bash", "-c", gate],
                            env={**os.environ, "HOME": temp},
                            text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False,
                        )
                        self.assertEqual(process.returncode, expected_exit)
                        self.assertEqual(process.stdout, "")
                        self.assertEqual(process.stderr, "")
                        self.assertNotIn("accessToken", process.stdout + process.stderr)
                        self.assertNotIn("refreshToken", process.stdout + process.stderr)

    def test_format_check_rejects_paths_outside_fixed_app_workspace(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["allowed_paths"] = ["docs/adapter.md"]
        with self.assertRaisesRegex(adapter.AdapterError, "outside the fixed app workspace"):
            adapter.check_command(request, "format")

    def test_format_check_inserts_end_of_options_before_option_like_paths(self) -> None:
        schema = json.loads((CONTROL_ROOT / "schemas/claude-worker-request.schema.json").read_text())
        for declared, operand in (("app/--help", "--help"), ("app/-x", "-x")):
            with self.subTest(declared=declared):
                request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
                request["allowed_paths"] = [declared]
                jsonschema.validate(request, schema)
                adapter.validate_request_content(request)
                command = adapter.check_command(request, "format")
                argv = shlex.split(command)
                self.assertEqual(argv[0], adapter.REMOTE_DART)
                self.assertEqual(argv[1:4], ["format", "--output=none", "--set-exit-if-changed"])
                self.assertIn("--", argv)
                terminator = argv.index("--")
                self.assertEqual(argv[terminator + 1 :], [operand])
                self.assertNotIn(operand, argv[1:terminator])

    def test_review_format_check_keeps_full_tree_command(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request.pop("allowed_paths")
        request["target_commit"] = TARGET
        command = adapter.check_command(request, "format")
        self.assertEqual(
            command,
            f"{adapter.REMOTE_DART} format --output=none --set-exit-if-changed lib/ test/",
        )

    def test_failed_independent_check_retains_bounded_diagnostics_and_stops(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze", "test"]
        failed = subprocess.CompletedProcess(["ssh"], 1, "analyzer stdout\n", "analyzer stderr\n")
        cleanup = subprocess.CompletedProcess(["ssh"], 0, "", "")
        with mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
            adapter, "_run", side_effect=[failed, cleanup]
        ) as run:
            with self.assertRaises(adapter.CheckFailure) as caught:
                adapter.run_checks(
                    request,
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                )
        self.assertEqual(
            caught.exception.checks,
            [{
                "name": "analyze",
                "exit_code": 1,
                "passed": False,
                "output": "analyzer stdout\nanalyzer stderr\n",
            }],
        )
        execution_calls = [
            call for call in run.call_args_list
            if call.args[0][:4] == ["ssh", "agent-claude", "bash", "-lc"]
        ]
        self.assertEqual(len(execution_calls), 1)

    def test_secret_before_bounded_check_tail_is_rejected(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        synthetic = "github_pat_" + "A" * 64
        cleanup = subprocess.CompletedProcess(["ssh"], 0, "", "")
        for returncode in [0, 1]:
            process = subprocess.CompletedProcess(
                ["ssh"], returncode, synthetic + "\n" + "x" * 4000, ""
            )
            with self.subTest(returncode=returncode), mock.patch.object(
                adapter, "_ssh_script", return_value=""
            ), mock.patch.object(adapter, "_run", side_effect=[process, cleanup]):
                with self.assertRaisesRegex(adapter.AdapterError, "secret-shaped"):
                    adapter.run_checks(
                        request,
                        "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                    )

    def test_cleanup_nonzero_is_preserved_or_fails_closed(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        cleanup = subprocess.CompletedProcess(["ssh"], 23, "", "rm: cleanup failed\n")
        failed = subprocess.CompletedProcess(["ssh"], 1, "analyzer failed\n", "")
        with mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
            adapter, "_run", side_effect=[failed, cleanup]
        ):
            with self.assertRaises(adapter.CheckFailure) as caught:
                adapter.run_checks(
                    request,
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                )
        self.assertEqual(caught.exception.checks[0]["output"], "analyzer failed\n")
        self.assertEqual(
            caught.exception.cleanup_blockers,
            ["independent check cleanup failed: 23"],
        )

        passed = subprocess.CompletedProcess(["ssh"], 0, "analyzer clean\n", "")
        with mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
            adapter, "_run", side_effect=[passed, cleanup]
        ):
            with self.assertRaisesRegex(adapter.AdapterError, "cleanup failed: 23"):
                adapter.run_checks(
                    request,
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                )

    def test_secret_shaped_cleanup_output_is_rejected(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        passed = subprocess.CompletedProcess(["ssh"], 0, "analyzer clean\n", "")
        synthetic = "github_pat_" + "A" * 64
        cleanup = subprocess.CompletedProcess(["ssh"], 0, "", synthetic)
        with mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
            adapter, "_run", side_effect=[passed, cleanup]
        ):
            with self.assertRaisesRegex(adapter.AdapterError, "secret-shaped"):
                adapter.run_checks(
                    request,
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                )

    def test_cleanup_failure_does_not_mask_failed_check_diagnostics(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze", "test"]
        failed = subprocess.CompletedProcess(["ssh"], 1, "analyzer stdout\n", "analyzer stderr\n")
        cleanup_failures = [
            subprocess.TimeoutExpired(["ssh"], 60),
            RuntimeError("cleanup failed"),
        ]
        for cleanup_failure in cleanup_failures:
            with self.subTest(cleanup_failure=type(cleanup_failure).__name__), mock.patch.object(
                adapter, "_ssh_script", return_value=""
            ), mock.patch.object(adapter, "_run", side_effect=[failed, cleanup_failure]) as run:
                with self.assertRaises(adapter.CheckFailure) as caught:
                    adapter.run_checks(
                        request,
                        "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                    )
                self.assertEqual(str(caught.exception), "independent check failed: analyze")
                self.assertEqual(
                    caught.exception.checks,
                    [{
                        "name": "analyze",
                        "exit_code": 1,
                        "passed": False,
                        "output": "analyzer stdout\nanalyzer stderr\n",
                    }],
                )
                self.assertEqual(run.call_count, 2)

    def test_cleanup_failure_without_prior_failure_still_fails_closed(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        passed = subprocess.CompletedProcess(["ssh"], 0, "analyzer clean\n", "")
        cleanup_failures = [
            subprocess.TimeoutExpired(["ssh"], 60),
            RuntimeError("cleanup failed"),
        ]
        for cleanup_failure in cleanup_failures:
            with self.subTest(cleanup_failure=type(cleanup_failure).__name__), mock.patch.object(
                adapter, "_ssh_script", return_value=""
            ), mock.patch.object(adapter, "_run", side_effect=[passed, cleanup_failure]):
                with self.assertRaises(type(cleanup_failure)):
                    adapter.run_checks(
                        request,
                        "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                    )

    def test_check_failure_is_recorded_in_block_result(self) -> None:
        result = {"verdict": "PASS", "blockers": [], "checks": []}
        check = {
            "name": "analyze",
            "exit_code": 1,
            "passed": False,
            "output": "bounded analyzer diagnostic",
        }
        adapter.record_adapter_failure(
            result,
            adapter.CheckFailure("analyze", [check]),
        )
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertEqual(result["blockers"], ["independent check failed: analyze"])
        self.assertEqual(result["checks"], [check])

    def test_preflight_authenticates_fixed_claude_flutter_and_dart_executables(self) -> None:
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("stop")) as ssh_script:
            with self.assertRaises(adapter.AdapterError):
                adapter.preflight()
        script = ssh_script.call_args.args[0]
        self.assertIn(adapter.REMOTE_CLAUDE, script)
        self.assertIn(adapter.REMOTE_FLUTTER, script)
        self.assertIn(adapter.REMOTE_DART, script)
        self.assertIn(adapter.REMOTE_FLUTTER_SNAPSHOT, script)
        for path, digest in adapter.EXPECTED_EXECUTABLE_SHA256.items():
            self.assertIn(path, script)
            self.assertIn(digest, script)
        self.assertNotIn("toolchain.env", script)


class ResultValidationTests(unittest.TestCase):
    def test_protected_state_rejects_untrusted_executable_baseline(self) -> None:
        value = {"status": "", "replace_refs": [], "executables": [{"path": path, "sha256": "0" * 64} for path in adapter.EXPECTED_EXECUTABLE_SHA256]}
        with mock.patch.object(adapter, "_ssh_script", return_value=json.dumps(value)):
            with self.assertRaisesRegex(adapter.AdapterError, "trusted manifest"):
                adapter.capture_remote_protected_state()

    def test_protected_repository_and_executable_drift_blocks(self) -> None:
        expected = {"refs": ["refs/heads/main a"], "executables": [{"sha256": "1" * 64}]}
        with mock.patch.object(adapter, "capture_remote_protected_state", return_value=dict(expected)):
            adapter.verify_remote_protected_state(expected)
        changed = {"refs": ["refs/heads/main b"], "executables": [{"sha256": "1" * 64}]}
        with mock.patch.object(adapter, "capture_remote_protected_state", return_value=changed):
            with self.assertRaisesRegex(adapter.AdapterError, "protected repository/toolchain state changed"):
                adapter.verify_remote_protected_state(expected)

    def test_result_schema_is_closed_and_review_pass_requires_review_verdict(self) -> None:
        schema = json.loads((CONTROL_ROOT / "schemas/claude-worker-result.schema.json").read_text())
        evidence = {
            "schema_version": 2,
            "adapter_version": "0.4.5",
            "attempt_id": "review-001",
            "mode": "review",
            "request_sha256": "a" * 64,
            "started_at": "2026-08-13T00:00:00Z",
            "finished_at": "2026-08-13T00:01:00Z",
            "route": {"ssh_target": "agent-claude", "identity": "jellyclaude@jellybase", "repository": "/home/jellyclaude/dev_projects/jellyssh"},
            "controller_commit": "9" * 40,
            "controller_digests": {name: "b" * 64 for name in ["adapter", "hook", "request_schema", "result_schema", "session_settings"]},
            "verdict": "PASS",
            "blockers": [],
            "checks": [],
            "preflight": {
                "status": "PASS", "ssh_target": "agent-claude", "identity": "jellyclaude@jellybase",
                "repository": "/home/jellyclaude/dev_projects/jellyssh", "origin": "git@github-jellyssh:dotalbot/jellyssh.git",
                "github_access": "read-only", "skill_digests": {"code-review": "c" * 64},
                "hook_sha256": "d" * 64, "session_settings_sha256": "e" * 64,
                "versions": {"claude": "2.1.228 (Claude Code)", "flutter": "Flutter 3.44.9 stable", "dart": "Dart SDK version: 3.12.2 stable"},
            },
            "worktree": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/review-001/source",
            "start_commit": TARGET, "start_tree": "f" * 40, "raw_claude_sha256": "1" * 64, "raw_claude_b64": "e30=",
            "claude": {"session_id": "s", "terminal_reason": "completed", "models": ["claude-sonnet-5"], "summary": "ok"},
            "final_commit": TARGET, "final_tree": "f" * 40, "branch": None, "changed_files": ["app/lib/a.dart"],
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(evidence, schema)
        evidence["review_verdict"] = "PASS"
        jsonschema.validate(evidence, schema)
        evidence["forged"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(evidence, schema)

    def test_implementation_changed_files_must_stay_in_declared_paths(self) -> None:
        request = implementation_request("/tmp/result.json")
        adapter.validate_changed_paths(request, ["app/lib/example.dart"])
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_changed_paths(request, ["app/lib/unexpected.dart"])

    def test_declared_directory_prefix_is_segment_bounded(self) -> None:
        request = implementation_request("/tmp/result.json")
        request["allowed_paths"] = ["docs/adapter/"]
        adapter.validate_changed_paths(request, ["docs/adapter/result.md"])
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_changed_paths(request, ["docs/adapter-escape/result.md"])

    def test_tool_versions_reject_flutter_lock_chatter(self) -> None:
        valid = {
            "claude": "2.1.228 (Claude Code)",
            "flutter": "Flutter 3.44.9 • channel stable",
            "dart": "Dart SDK version: 3.12.2 (stable)",
        }
        adapter.validate_tool_versions(valid)
        invalid = dict(valid)
        invalid["flutter"] = "Waiting for another flutter command to release the startup lock..."
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_tool_versions(invalid)

    def test_malformed_claude_json_blocks(self) -> None:
        process = subprocess.CompletedProcess(["claude"], 0, "not json", "")
        with self.assertRaises(adapter.AdapterError):
            adapter.parse_claude_result(process)

    def test_claude_error_blocks(self) -> None:
        process = subprocess.CompletedProcess(["claude"], 0, json.dumps({"is_error": True, "result": "no"}), "")
        with self.assertRaises(adapter.AdapterError):
            adapter.parse_claude_result(process)

    def test_nonzero_claude_exit_blocks(self) -> None:
        process = subprocess.CompletedProcess(["claude"], 7, "{}", "failed")
        with self.assertRaisesRegex(adapter.AdapterError, "nonzero"):
            adapter.parse_claude_result(process)

    def test_git_state_negative_invariants(self) -> None:
        implementation = implementation_request("/tmp/result.json")
        start = {"start_tree": "a" * 40}
        valid = {"commit": TARGET, "tree": "b" * 40, "branch": implementation["branch"], "status": "", "changed": ["app/lib/example.dart"]}
        for field, value in [("status", " M dirty"), ("branch", "fix/wrong"), ("tree", start["start_tree"]), ("changed", [])]:
            with self.subTest(field=field):
                state = dict(valid)
                state[field] = value
                with self.assertRaises(adapter.AdapterError):
                    adapter.validate_git_state(implementation, state, start)

        review = dict(implementation)
        review["mode"] = "review"
        review["target_commit"] = TARGET
        review.pop("branch")
        review.pop("allowed_paths")
        review_start = {"start_tree": "c" * 40}
        valid_review = {"commit": TARGET, "tree": "c" * 40, "branch": "", "status": "", "changed": ["app/lib/example.dart"]}
        for field, value in [("commit", BASE), ("tree", "d" * 40), ("branch", "feat/not-detached"), ("status", " M dirty")]:
            with self.subTest(review_field=field):
                state = dict(valid_review)
                state[field] = value
                with self.assertRaises(adapter.AdapterError):
                    adapter.validate_git_state(review, state, review_start)

    def test_success_result_requires_session_and_model(self) -> None:
        payload = {
            "is_error": False,
            "session_id": "session-1",
            "terminal_reason": "completed",
            "result": "done",
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 1}},
        }
        parsed = adapter.parse_claude_result(subprocess.CompletedProcess(["claude"], 0, json.dumps(payload), ""))
        self.assertEqual(parsed["session_id"], "session-1")
        self.assertEqual(parsed["models"], ["claude-sonnet-5"])

    def test_requested_primary_model_family_must_appear(self) -> None:
        parsed = {"models": ["claude-haiku-4-5-20251001", "claude-sonnet-5"]}
        adapter.validate_requested_model("sonnet", parsed)
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_requested_model("opus", parsed)

    def test_controller_digests_cover_adapter_schemas_and_hook(self) -> None:
        digests = adapter.controller_digests()
        self.assertEqual(
            sorted(digests),
            ["adapter", "hook", "request_schema", "result_schema", "session_settings"],
        )
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in digests.values()))

    def test_controller_commit_requires_clean_checkout_and_matching_blobs(self) -> None:
        paths = adapter.controller_asset_paths()
        commit = "a" * 40

        def clean_git(*args: str) -> bytes:
            if args == ("status", "--porcelain", "--untracked-files=normal"):
                return b""
            if args == ("rev-parse", "HEAD"):
                return (commit + "\n").encode()
            if args[:2] == ("show", f"{commit}:"):
                raise AssertionError("unexpected split show arguments")
            if args[0] == "show":
                relative = args[1].split(":", 1)[1]
                for path in paths.values():
                    if path.relative_to(adapter.CONTROL_ROOT.parent).as_posix() == relative:
                        return path.read_bytes()
            raise AssertionError(args)

        with mock.patch.object(adapter, "_controller_git", side_effect=clean_git):
            self.assertEqual(adapter.verified_controller_commit(), commit)

        def drifted_git(*args: str) -> bytes:
            value = clean_git(*args)
            if args[0] == "show" and args[1].endswith("claude_worker_adapter.py"):
                return value + b"drift"
            return value

        with mock.patch.object(adapter, "_controller_git", side_effect=drifted_git):
            with self.assertRaises(adapter.AdapterError):
                adapter.verified_controller_commit()

        with mock.patch.object(adapter, "_controller_git", return_value=b"?? unexpected"):
            with self.assertRaisesRegex(adapter.AdapterError, "not clean"):
                adapter.verified_controller_commit()

    def test_controller_snapshot_rejects_loaded_adapter_aba_and_owns_schema_bytes(self) -> None:
        paths = adapter.controller_asset_paths()
        commit = "a" * 40

        def committed_git(*args: str) -> bytes:
            if args == ("status", "--porcelain", "--untracked-files=normal"):
                return b""
            if args == ("rev-parse", "HEAD"):
                return (commit + "\n").encode()
            if args[0] == "show":
                relative = args[1].split(":", 1)[1]
                for path in paths.values():
                    if path.relative_to(adapter.CONTROL_ROOT.parent).as_posix() == relative:
                        return path.read_bytes()
            raise AssertionError(args)

        with mock.patch.object(adapter, "_controller_git", side_effect=committed_git), mock.patch.object(
            adapter, "_committed_skill_digests", return_value={"code-review": "f" * 64}
        ):
            snapshot = adapter.capture_controller_snapshot()
        self.assertEqual(snapshot.commit, commit)
        self.assertEqual(snapshot.request_schema["title"], "Governed Claude worker request")

        with mock.patch.object(adapter, "EXECUTING_ADAPTER_CODE_SHA256", "0" * 64):
            with mock.patch.object(adapter, "_controller_git", side_effect=committed_git), mock.patch.object(
                adapter, "_committed_skill_digests", return_value={"code-review": "f" * 64}
            ):
                with self.assertRaisesRegex(adapter.AdapterError, "loaded controller"):
                    adapter.capture_controller_snapshot()

        with tempfile.TemporaryDirectory() as temp:
            request_path = Path(temp) / "request.json"
            output = "/home/jellybot/projects/jellyssh-claude-adapter/evidence/snapshot-test.json"
            request_path.write_text(json.dumps(implementation_request(output)))
            with mock.patch.object(adapter, "_load_json", wraps=adapter._load_json) as load_json, mock.patch.object(
                adapter, "_validate_output_path", return_value=Path(output)
            ):
                adapter.load_and_validate_request(request_path, snapshot=snapshot)
            self.assertEqual(load_json.call_count, 1)

    def test_controller_git_disables_replacement_objects(self) -> None:
        with mock.patch.object(adapter.subprocess, "check_output", return_value=b"") as check_output:
            adapter._controller_git("status", "--porcelain")
        self.assertEqual(check_output.call_args.kwargs["env"]["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertIn("core.fsmonitor=false", " ".join(check_output.call_args.args[0]))

    def test_secret_shaped_worker_output_is_rejected_before_publication(self) -> None:
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_output_text("worker printed ghp_abcdabcdabcdabcdabcdabcd")

    def test_github_fine_grained_pat_shape_is_rejected_everywhere(self) -> None:
        synthetic = "github_pat_" + "A" * 64
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_output_text(f"worker printed {synthetic}")
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_request_content({"task": f"use {synthetic}"})

        with mock.patch.object(adapter, "_ssh_script", return_value="CONTENT_SCAN_PASS\n") as ssh_script:
            adapter.scan_changed_files(
                "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                ["app/lib/a.dart"],
            )
        self.assertIn("github_pat_", ssh_script.call_args.args[0])
        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("command failed")):
            with self.assertRaises(adapter.AdapterError):
                adapter.scan_changed_files(
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                    ["app/lib/a.dart"],
                )

    def test_implementation_requires_changed_files_before_controller_commit(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {"commit": BASE, "tree": "4" * 40, "branch": request["branch"], "status": " M app/lib/a.dart", "changed": []}
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_precommit_state(request, state)

    def test_controller_commit_uses_digest_bound_immutable_tree_without_hooks(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        expected = {
            "changed": ["app/lib/a.dart"],
            "state_sha256": "5" * 64,
            "content_sha256": "6" * 64,
        }
        with mock.patch.object(adapter, "_ssh_script", return_value=json.dumps({
            "commit": TARGET,
            "tree": "4" * 40,
            "branch": request["branch"],
            "status": "",
            "changed": ["app/lib/a.dart"],
        })) as ssh_script:
            state = adapter.commit_implementation(
                request,
                "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                expected,
            )
        script = ssh_script.call_args.args[0]
        self.assertIn("GIT_INDEX_FILE", script)
        self.assertIn("commit-tree", script)
        self.assertIn("core.hooksPath=/dev/null", script)
        self.assertIn("hash-object','-w','--stdin','--no-filters", script)
        self.assertIn(expected["content_sha256"], script)
        self.assertNotIn("update-ref", script)
        self.assertNotIn("reset --hard", script)
        self.assertNotIn(" commit -q ", script)
        self.assertNotIn(" add -- ", script)
        self.assertIn("chore: apply governed Claude implementation", script)
        self.assertNotIn(str(request["task"]), script)
        self.assertEqual(state["commit"], TARGET)

        with mock.patch.object(adapter, "_ssh_script", side_effect=adapter.AdapterError("validated content changed")):
            with self.assertRaises(adapter.AdapterError):
                adapter.commit_implementation(
                    request,
                    "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                    expected,
                )

    def test_controller_commit_transaction_bypasses_hooks_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = root / "repository"
            home = root / "home"
            (home / ".cache").mkdir(parents=True)
            repository.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.name", "Governed Test"], check=True)
            subprocess.run(["git", "-C", str(repository), "config", "user.email", "governed@example.invalid"], check=True)
            source = repository / "app/lib/example.dart"
            source.parent.mkdir(parents=True)
            source.write_text("before\n")
            subprocess.run(["git", "-C", str(repository), "add", "--", "app/lib/example.dart"], check=True)
            subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", "base"], check=True)
            base = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
            branch = "feat/example-change"
            subprocess.run(["git", "-C", str(repository), "switch", "-q", "-c", branch], check=True)
            source.write_text("validated bytes\n")

            marker = root / "hook-ran"
            filter_marker = root / "filter-ran"
            hook = repository / ".git/hooks/pre-commit"
            hook.write_text(f"#!/bin/sh\ntouch {marker}\nexit 2\n")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            attributes = repository / ".git/info/attributes"
            attributes.write_text("app/lib/example.dart filter=hostile\n")
            filter_script = root / "hostile-filter"
            filter_script.write_text(f"#!/bin/sh\ntouch {filter_marker}\ncat\n")
            filter_script.chmod(filter_script.stat().st_mode | stat.S_IXUSR)
            subprocess.run(["git", "-C", str(repository), "config", "filter.hostile.clean", str(filter_script)], check=True)

            metadata = os.lstat(source)
            raw = b"app/lib/example.dart"
            state = hashlib.sha256()
            state.update(struct.pack(">Q", len(raw))); state.update(raw)
            state.update(struct.pack(">Q", metadata.st_mode)); state.update(source.read_bytes())
            content = hashlib.sha256()
            content.update(struct.pack(">Q", len(raw))); content.update(raw)
            content.update(b"100644"); content.update(struct.pack(">Q", len(source.read_bytes()))); content.update(source.read_bytes())
            request = implementation_request(str(root / "result.json"))
            request["base_commit"] = base
            request["branch"] = branch
            request["checks"] = []
            expected = {"changed": ["app/lib/example.dart"], "state_sha256": state.hexdigest(), "content_sha256": content.hexdigest()}
            def run_script(script: str, *, timeout: int = 120) -> str:
                process = subprocess.run(
                    ["bash"], input=script, text=True, capture_output=True,
                    env={**os.environ, "HOME": str(home)}, timeout=timeout, check=False,
                )
                if process.returncode != 0:
                    raise adapter.AdapterError(process.stderr[-1000:])
                return process.stdout

            with mock.patch.object(adapter, "_ssh_script", side_effect=run_script):
                with self.assertRaises(adapter.AdapterError):
                    adapter.commit_implementation(request, str(repository), expected)
            self.assertFalse(filter_marker.exists())
            self.assertFalse(marker.exists())

            subprocess.run(["git", "-C", str(repository), "config", "--unset", "filter.hostile.clean"], check=True)
            attributes.unlink()
            source.write_text("raced bytes\n")
            with mock.patch.object(adapter, "_ssh_script", side_effect=run_script):
                with self.assertRaises(adapter.AdapterError):
                    adapter.commit_implementation(request, str(repository), expected)
            self.assertEqual(
                subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip(),
                base,
            )
            self.assertFalse(marker.exists())

            source.write_text("validated bytes\n")
            with mock.patch.object(adapter, "_ssh_script", side_effect=run_script):
                result = adapter.commit_implementation(request, str(repository), expected)
            self.assertFalse(marker.exists())
            committed = subprocess.check_output(["git", "-C", str(repository), "show", f"{result['commit']}:app/lib/example.dart"])
            self.assertEqual(committed, b"validated bytes\n")
            self.assertEqual(result["branch"], branch)
            self.assertEqual(
                subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip(),
                base,
            )
            self.assertTrue(subprocess.check_output(["git", "-C", str(repository), "status", "--porcelain"], text=True))

    def test_remote_content_scan_is_path_bounded_and_secret_aware(self) -> None:
        with mock.patch.object(adapter, "_ssh_script", return_value="CONTENT_SCAN_PASS\n") as ssh_script:
            adapter.scan_changed_files(
                "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
                ["app/lib/a.dart"],
            )
        script = ssh_script.call_args.args[0]
        self.assertIn("is_symlink", script)
        self.assertIn("PRIVATE KEY", script)
        self.assertIn("CONTENT_SCAN_PASS", script)

    def test_checks_must_not_change_precommit_state(self) -> None:
        before = {"status": " M app/lib/a.dart", "changed": ["app/lib/a.dart"], "state_sha256": "a" * 64}
        adapter.validate_checks_preserved_state(before, dict(before))
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_checks_preserved_state(before, {"status": " M app/lib/a.dart", "changed": ["app/lib/a.dart", "generated.txt"], "state_sha256": "b" * 64})
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_checks_preserved_state(before, {"status": " M app/lib/a.dart", "changed": ["app/lib/a.dart"], "state_sha256": "b" * 64})

    def test_precommit_state_digest_hashes_changed_file_bytes(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {
            "commit": BASE,
            "tree": "4" * 40,
            "branch": request["branch"],
            "status": " M app/lib/example.dart",
            "changed": ["app/lib/example.dart"],
            "state_sha256": "a" * 64,
        }
        with mock.patch.object(adapter, "_ssh_script", return_value=json.dumps(state)) as ssh_script:
            adapter.inspect_precommit_worktree(request, "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source")
        script = ssh_script.call_args.args[0]
        self.assertIn("state_sha256", script)
        self.assertIn("readlink", script)
        self.assertIn("handle.read", script)

    def test_review_requires_one_machine_verdict_line(self) -> None:
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_review_verdict("Review looks fine.")
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_review_verdict("REVIEW_VERDICT=PASS\nREVIEW_VERDICT=BLOCK")
        self.assertEqual(adapter.validate_review_verdict("Finding summary\nREVIEW_VERDICT=PASS"), "PASS")

    def test_review_verdict_is_validated_from_full_text_not_truncated_summary(self) -> None:
        full = "x" * 3000 + "\nREVIEW_VERDICT=PASS"
        payload = {
            "is_error": False,
            "session_id": "session-1",
            "terminal_reason": "completed",
            "result": full,
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 1}},
        }
        parsed = adapter.parse_claude_result(
            subprocess.CompletedProcess(["claude"], 0, json.dumps(payload), "")
        )
        self.assertEqual(len(parsed["summary"]), 2000)
        self.assertEqual(adapter.validate_review_verdict(parsed["_full_text"]), "PASS")

    def test_precommit_script_contains_no_literal_nul_bytes(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {
            "commit": BASE,
            "tree": "4" * 40,
            "branch": request["branch"],
            "status": "?? docs/new.md\\u0000",
            "changed": ["docs/new.md"],
        }
        with mock.patch.object(adapter, "_ssh_script", return_value=json.dumps(state)) as ssh_script:
            adapter.inspect_precommit_worktree(
                request,
                "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source",
            )
        self.assertNotIn("\x00", ssh_script.call_args.args[0])
        self.assertIn("split('\\0')", ssh_script.call_args.args[0])


class AtomicPublicationTests(unittest.TestCase):
    def _snapshot(self) -> adapter.ControllerSnapshot:
        paths = adapter.controller_asset_paths()
        return adapter.ControllerSnapshot(
            commit="a" * 40,
            asset_bytes={name: path.read_bytes() for name, path in paths.items()},
            digests={name: adapter.sha256_bytes(path.read_bytes()) for name, path in paths.items()},
            request_schema=json.loads(paths["request_schema"].read_text()),
            result_schema=json.loads(paths["result_schema"].read_text()),
            skill_digests={"code-review": "f" * 64},
        )

    def test_post_publication_cleanup_faults_are_best_effort(self) -> None:
        worktree = "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source"
        faults = [PermissionError("cleanup failed"), subprocess.TimeoutExpired(["ssh"], 60)]
        for fault in faults:
            with self.subTest(fault=type(fault).__name__), mock.patch.object(adapter, "_run", side_effect=fault):
                adapter.cleanup_worktree(worktree)

    def test_success_publication_stages_before_ref_then_links_evidence(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {"commit": TARGET, "tree": "4" * 40, "branch": request["branch"], "changed": ["app/lib/example.dart"]}
        result = {"verdict": "PASS"}
        staged = adapter.StagedEvidence(10, ".tmp", "a.json")
        calls: list[str] = []
        with mock.patch.object(adapter, "stage_evidence_bytes", side_effect=lambda *a, **k: calls.append("stage") or staged), mock.patch.object(
            adapter, "publish_implementation_ref", side_effect=lambda *a, **k: calls.append("ref")
        ), mock.patch.object(adapter, "publish_staged_evidence", side_effect=lambda *a, **k: calls.append("evidence")):
            observed = adapter.finalize_implementation_publication(
                request, "/sandbox/source", state, Path(request["output_path"]), result, self._snapshot()
            )
        self.assertIs(observed, result)
        self.assertEqual(calls, ["stage", "ref", "evidence"])

    def test_evidence_failure_rolls_back_exact_ref_then_publishes_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            request = implementation_request(str(output))
            state = {"commit": TARGET, "tree": "4" * 40, "branch": request["branch"], "changed": ["app/lib/example.dart"]}
            result = {"verdict": "PASS", "blockers": []}
            link_calls = 0
            real_publish = adapter.publish_staged_evidence

            def fail_first_link(staged: adapter.StagedEvidence) -> None:
                nonlocal link_calls
                link_calls += 1
                if link_calls == 1:
                    raise OSError("link failed")
                real_publish(staged)

            with mock.patch.object(adapter, "publish_implementation_ref"), mock.patch.object(
                adapter, "publish_staged_evidence", side_effect=fail_first_link
            ), mock.patch.object(adapter, "rollback_implementation_ref") as rollback, mock.patch.object(
                adapter, "_validate_result"
            ):
                observed = adapter.finalize_implementation_publication(
                    request, "/sandbox/source", state, output, result, self._snapshot()
                )
            rollback.assert_called_once_with(request, state)
            self.assertEqual(observed["verdict"], "BLOCK")
            self.assertEqual(json.loads(output.read_text())["verdict"], "BLOCK")
            self.assertFalse(list(output.parent.glob(".*.tmp")))

    def test_evidence_abort_failure_cannot_skip_exact_ref_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            request = implementation_request(str(output))
            state = {"commit": TARGET, "tree": "4" * 40, "branch": request["branch"], "changed": ["app/lib/example.dart"]}
            result = {"verdict": "PASS", "blockers": []}
            calls: list[str] = []
            link_calls = 0
            real_publish = adapter.publish_staged_evidence

            def fail_first_link(staged: adapter.StagedEvidence) -> None:
                nonlocal link_calls
                link_calls += 1
                if link_calls == 1:
                    raise OSError("link failed")
                real_publish(staged)

            def fail_abort(*args: object) -> None:
                calls.append("abort")
                raise PermissionError("unlink failed")

            with mock.patch.object(adapter, "publish_implementation_ref", side_effect=lambda *a: calls.append("ref")), mock.patch.object(
                adapter, "publish_staged_evidence", side_effect=fail_first_link
            ), mock.patch.object(
                adapter, "rollback_implementation_ref", side_effect=lambda *a: calls.append("rollback")
            ), mock.patch.object(
                adapter, "abort_staged_evidence", side_effect=fail_abort
            ), mock.patch.object(adapter, "_validate_result"):
                observed = adapter.finalize_implementation_publication(
                    request, "/sandbox/source", state, output, result, self._snapshot()
                )
            self.assertEqual(calls, ["ref", "rollback", "abort"])
            self.assertEqual(observed["verdict"], "BLOCK")
            self.assertEqual(json.loads(output.read_text())["verdict"], "BLOCK")

    def test_abort_staged_evidence_suppresses_unlink_failure_and_closes_descriptor(self) -> None:
        staged = adapter.StagedEvidence(10, ".tmp", "result.json")
        with mock.patch.object(adapter.os, "unlink", side_effect=PermissionError("unlink failed")), mock.patch.object(
            adapter.os, "close"
        ) as close:
            adapter.abort_staged_evidence(staged)
        close.assert_called_once_with(10)

    def test_uncertain_ref_failure_also_runs_idempotent_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            request = implementation_request(str(output))
            state = {"commit": TARGET, "tree": "4" * 40, "branch": request["branch"], "changed": ["app/lib/example.dart"]}
            result = {"verdict": "PASS", "blockers": []}
            with mock.patch.object(adapter, "publish_implementation_ref", side_effect=adapter.AdapterError("uncertain SSH result")), mock.patch.object(
                adapter, "rollback_implementation_ref"
            ) as rollback, mock.patch.object(adapter, "_validate_result"):
                observed = adapter.finalize_implementation_publication(
                    request, "/sandbox/source", state, output, result, self._snapshot()
                )
            rollback.assert_called_once_with(request, state)
            self.assertEqual(observed["verdict"], "BLOCK")

    def test_rollback_failure_never_publishes_block_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            request = implementation_request(str(output))
            state = {"commit": TARGET, "tree": "4" * 40, "branch": request["branch"], "changed": ["app/lib/example.dart"]}
            with mock.patch.object(adapter, "publish_implementation_ref", side_effect=adapter.AdapterError("uncertain SSH result")), mock.patch.object(
                adapter, "rollback_implementation_ref", side_effect=adapter.AdapterError("rollback uncertain")
            ):
                with self.assertRaisesRegex(adapter.AdapterError, "rollback could not be verified"):
                    adapter.finalize_implementation_publication(
                        request, "/sandbox/source", state, output, {"verdict": "PASS"}, self._snapshot()
                    )
            self.assertFalse(output.exists())
            self.assertFalse(list(output.parent.glob(".*.tmp")))

    def test_ref_scripts_use_create_cas_and_exact_value_delete(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {"commit": TARGET, "tree": "4" * 40}
        with mock.patch.object(adapter, "_ssh_script", return_value="") as ssh_script:
            adapter.publish_implementation_ref(request, "/sandbox/source", state)
        publish_script = ssh_script.call_args.args[0]
        self.assertIn("0000000000000000000000000000000000000000", publish_script)
        self.assertIn("pack-objects --stdout --revs", publish_script)
        with mock.patch.object(adapter, "_ssh_script", return_value="") as ssh_script:
            adapter.rollback_implementation_ref(request, state)
        rollback_script = ssh_script.call_args.args[0]
        self.assertIn('update-ref -d "refs/heads/$branch" "$commit"', rollback_script)
        self.assertIn('test "$(git -C "$shared" rev-parse "refs/heads/$branch")" = "$commit"', rollback_script)

    def test_atomic_write_leaves_valid_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "result.json"
            adapter.atomic_write_json(target, {"z": 1, "a": 2})
            self.assertEqual(target.read_text(), '{"a":2,"z":1}\n')
            self.assertFalse(list(target.parent.glob(".*.tmp")))

    def test_atomic_write_never_overwrites_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "result.json"
            target.write_text("original\n")
            with self.assertRaises(FileExistsError):
                adapter.atomic_write_json(target, {"new": True})
            self.assertEqual(target.read_text(), "original\n")

    def test_atomic_write_does_not_report_failure_after_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "result.json"
            real_fsync = adapter.os.fsync
            calls = 0

            def fail_directory_sync(descriptor: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("simulated post-publication failure")
                real_fsync(descriptor)

            with mock.patch.object(adapter.os, "fsync", side_effect=fail_directory_sync):
                adapter.atomic_write_json(target, {"verdict": "PASS"})
            self.assertEqual(target.read_text(), '{"verdict":"PASS"}\n')

    def test_atomic_write_rejects_symlinked_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            (root / "redirect").symlink_to(outside, target_is_directory=True)
            with self.assertRaises((adapter.AdapterError, OSError)):
                adapter.atomic_write_json(root / "redirect" / "result.json", {"verdict": "PASS"})
            self.assertFalse((outside / "result.json").exists())

    def test_atomic_write_path_swap_cannot_redirect_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            original = root / "evidence-original"
            outside = root / "outside"
            evidence.mkdir()
            outside.mkdir()
            real_link = os.link
            swapped = False

            def swap_then_link(src: str, dst: str, **kwargs: object) -> None:
                nonlocal swapped
                if not swapped:
                    evidence.rename(original)
                    evidence.symlink_to(outside, target_is_directory=True)
                    swapped = True
                real_link(src, dst, **kwargs)

            with mock.patch.object(adapter.os, "link", side_effect=swap_then_link):
                adapter.atomic_write_json(evidence / "result.json", {"verdict": "PASS"})
            self.assertFalse((outside / "result.json").exists())
            self.assertEqual((original / "result.json").read_text(), '{"verdict":"PASS"}\n')

    def test_orphaned_legacy_raw_sidecar_does_not_block_canonical_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            output.with_suffix(".claude.raw.json").write_text("legacy orphan\n")
            self.assertEqual(
                adapter._validate_output_path(str(output), allow_test_output=True),
                output,
            )


class CliFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        paths = adapter.controller_asset_paths()
        self.snapshot = adapter.ControllerSnapshot(
            commit="a" * 40,
            asset_bytes={name: path.read_bytes() for name, path in paths.items()},
            digests={name: adapter.sha256_bytes(path.read_bytes()) for name, path in paths.items()},
            request_schema=json.loads(paths["request_schema"].read_text()),
            result_schema=json.loads(paths["result_schema"].read_text()),
            skill_digests={"code-review": "f" * 64},
        )
        patcher = mock.patch.object(adapter, "capture_controller_snapshot", return_value=self.snapshot)
        patcher.start()
        self.addCleanup(patcher.stop)
        state_patcher = mock.patch.object(adapter, "capture_remote_protected_state", return_value={"sealed": True})
        verify_patcher = mock.patch.object(adapter, "verify_remote_protected_state")
        purge_patcher = mock.patch.object(adapter, "purge_sandbox_sensitive_state")
        restore_patcher = mock.patch.object(adapter, "restore_worktree_git_link")
        state_patcher.start()
        verify_patcher.start()
        purge_patcher.start()
        restore_patcher.start()
        self.addCleanup(state_patcher.stop)
        self.addCleanup(verify_patcher.stop)
        self.addCleanup(purge_patcher.stop)
        self.addCleanup(restore_patcher.stop)

    def test_malformed_worker_json_is_retained_only_inside_canonical_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            process = subprocess.CompletedProcess(["claude"], 0, "not-json", "")
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", "start_commit": BASE, "start_tree": "4" * 40},
            ), mock.patch.object(adapter, "invoke_claude", return_value=process):
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertEqual(base64.b64decode(result["raw_claude_b64"]), b"not-json")
            self.assertFalse(output.with_suffix(".claude.raw.json").exists())
            self.assertEqual(json.loads(output.read_text())["raw_claude_b64"], result["raw_claude_b64"])

    def test_undeclared_changed_path_blocks_before_checks_or_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            claude = {
                "session_id": "s",
                "terminal_reason": "completed",
                "models": ["claude-sonnet-5"],
                "summary": "done",
                "_full_text": "done",
            }
            unexpected = {
                "commit": BASE,
                "tree": "4" * 40,
                "branch": request["branch"],
                "status": "?? app/lib/unexpected.dart",
                "changed": ["app/lib/unexpected.dart"],
            }
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", "start_commit": BASE, "start_tree": "4" * 40},
            ), mock.patch.object(
                adapter, "invoke_claude", return_value=subprocess.CompletedProcess(["claude"], 0, "{}", "")
            ), mock.patch.object(adapter, "parse_claude_result", return_value=claude), mock.patch.object(
                adapter, "inspect_precommit_worktree", return_value=unexpected
            ), mock.patch.object(adapter, "run_checks") as run_checks, mock.patch.object(
                adapter, "commit_implementation"
            ) as commit:
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertIn("undeclared paths", result["blockers"][0])
            run_checks.assert_not_called()
            commit.assert_not_called()

    def test_failed_check_diagnostics_survive_canonical_block_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            request["checks"] = ["analyze", "test"]
            claude = {
                "session_id": "s",
                "terminal_reason": "completed",
                "models": ["claude-sonnet-5"],
                "summary": "done",
                "_full_text": "done",
            }
            precommit = {
                "commit": BASE,
                "tree": "4" * 40,
                "branch": request["branch"],
                "status": " M app/lib/example.dart",
                "changed": ["app/lib/example.dart"],
                "state_sha256": "5" * 64,
            }
            failed_check = subprocess.CompletedProcess(
                ["ssh"], 1, "bounded analyzer diagnostic", ""
            )
            cleanup_timeout = subprocess.TimeoutExpired(["ssh"], 60)
            final_cleanup = subprocess.CompletedProcess(["ssh"], 0, "", "")
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", "start_commit": BASE, "start_tree": "4" * 40},
            ), mock.patch.object(
                adapter, "invoke_claude", return_value=subprocess.CompletedProcess(["claude"], 0, "{}", "")
            ), mock.patch.object(adapter, "parse_claude_result", return_value=claude), mock.patch.object(
                adapter, "inspect_precommit_worktree", return_value=precommit
            ), mock.patch.object(adapter, "_ssh_script", return_value=""), mock.patch.object(
                adapter, "_run", side_effect=[failed_check, cleanup_timeout, final_cleanup]
            ), mock.patch.object(adapter, "commit_implementation") as commit:
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            expected = {
                "name": "analyze",
                "exit_code": 1,
                "passed": False,
                "output": "bounded analyzer diagnostic",
            }
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertEqual(
                result["blockers"],
                [
                    "independent check failed: analyze",
                    "independent check cleanup timed out",
                ],
            )
            self.assertEqual(result["checks"], [expected])
            self.assertEqual(json.loads(output.read_text())["checks"], [expected])
            commit.assert_not_called()

    def test_timeout_returns_timeout_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", "start_commit": BASE, "start_tree": "4" * 40},
            ), mock.patch.object(
                adapter, "invoke_claude", side_effect=subprocess.TimeoutExpired(["claude"], 600)
            ):
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            self.assertEqual(result["verdict"], "TIMEOUT")
            self.assertTrue(result["blockers"])

    def test_review_block_still_inspects_immutable_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            request["mode"] = "review"
            request.pop("branch")
            request.pop("allowed_paths")
            request["target_commit"] = TARGET
            request["checks"] = []
            claude = {
                "session_id": "s",
                "terminal_reason": "completed",
                "models": ["claude-sonnet-5"],
                "summary": "finding\nREVIEW_VERDICT=BLOCK",
                "_full_text": "finding\nREVIEW_VERDICT=BLOCK",
            }
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/.cache/jellyssh-claude-sandboxes/feature-001/source", "start_commit": TARGET, "start_tree": "4" * 40},
            ), mock.patch.object(
                adapter, "invoke_claude", return_value=subprocess.CompletedProcess(["claude"], 0, "{}", "")
            ), mock.patch.object(adapter, "parse_claude_result", return_value=claude), mock.patch.object(
                adapter,
                "inspect_worktree",
                return_value={"commit": TARGET, "tree": "4" * 40, "branch": "", "changed": []},
            ) as inspect:
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            self.assertEqual(inspect.call_count, 2)
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertEqual(result["review_verdict"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
