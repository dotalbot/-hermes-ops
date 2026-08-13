from __future__ import annotations

import json
from pathlib import Path
import re
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

    def test_prompt_is_stdin_and_fixed_route_is_used(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        command = adapter.build_claude_command(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001")
        self.assertEqual(command.ssh_target, "agent-claude")
        self.assertEqual(command.stdin_text, adapter.build_prompt(request))
        self.assertNotIn(str(request["task"]), " ".join(command.argv))
        self.assertNotIn("--dangerously-skip-permissions", command.argv)
        self.assertNotIn("push", " ".join(command.argv))
        self.assertIn("--permission-mode auto", " ".join(command.argv))
        self.assertNotIn("Bash", " ".join(command.argv))
        self.assertIn("--settings /home/jellyclaude/.claude/adapter-session-settings.json", " ".join(command.argv))
        self.assertIn("timeout --signal=TERM --kill-after=30", " ".join(command.argv))
        self.assertEqual(command.argv[:4], ["ssh", "agent-claude", "bash", "-lc"])
        self.assertTrue(command.argv[-1].startswith("'set -euo pipefail;"))
        self.assertTrue(command.argv[-1].endswith("'"))

    def test_implementation_restricts_available_tools_and_disables_mcp(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        command = adapter.build_claude_command(
            request,
            "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001",
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
        command = adapter.build_claude_command(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/review-feature-001")
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

    def test_independent_checks_quote_the_complete_login_shell_program(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        request["checks"] = ["analyze"]
        completed = subprocess.CompletedProcess(["ssh"], 0, "ok", "")
        with mock.patch.object(adapter, "_run", return_value=completed) as run:
            adapter.run_checks(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["ssh", "agent-claude", "bash", "-lc"])
        self.assertTrue(argv[-1].startswith("'set -euo pipefail;"))
        self.assertTrue(argv[-1].endswith("'"))


class ResultValidationTests(unittest.TestCase):
    def test_result_schema_is_closed_and_review_pass_requires_review_verdict(self) -> None:
        schema = json.loads((CONTROL_ROOT / "schemas/claude-worker-result.schema.json").read_text())
        evidence = {
            "schema_version": 1,
            "adapter_version": "0.1.0",
            "attempt_id": "review-001",
            "mode": "review",
            "request_sha256": "a" * 64,
            "started_at": "2026-08-13T00:00:00Z",
            "finished_at": "2026-08-13T00:01:00Z",
            "route": {"ssh_target": "agent-claude", "identity": "jellyclaude@jellybase", "repository": "/home/jellyclaude/dev_projects/jellyssh"},
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
            "worktree": "/home/jellyclaude/dev_projects/jellyssh-worktrees/review-001",
            "start_commit": TARGET, "start_tree": "f" * 40, "raw_claude_sha256": "1" * 64,
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

    def test_secret_shaped_worker_output_is_rejected_before_publication(self) -> None:
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_output_text("worker printed ghp_abcdabcdabcdabcdabcdabcd")

    def test_implementation_requires_changed_files_before_controller_commit(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        state = {"commit": BASE, "tree": "4" * 40, "branch": request["branch"], "status": " M app/lib/a.dart", "changed": []}
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_precommit_state(request, state)

    def test_controller_commit_command_has_fixed_message_and_no_worker_text(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        with mock.patch.object(adapter, "_ssh_script", return_value=json.dumps({
            "commit": TARGET,
            "tree": "4" * 40,
            "branch": request["branch"],
            "status": "",
            "changed": ["app/lib/a.dart"],
        })) as ssh_script:
            state = adapter.commit_implementation(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001", ["app/lib/a.dart"])
        script = ssh_script.call_args.args[0]
        self.assertIn(" add -- app/lib/a.dart", script)
        self.assertIn("chore: apply governed Claude implementation", script)
        self.assertNotIn(str(request["task"]), script)
        self.assertEqual(state["commit"], TARGET)

    def test_remote_content_scan_is_path_bounded_and_secret_aware(self) -> None:
        with mock.patch.object(adapter, "_ssh_script", return_value="CONTENT_SCAN_PASS\n") as ssh_script:
            adapter.scan_changed_files(
                "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001",
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
            adapter.inspect_precommit_worktree(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001")
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
                "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001",
            )
        self.assertNotIn("\x00", ssh_script.call_args.args[0])
        self.assertIn("split('\\0')", ssh_script.call_args.args[0])


class AtomicPublicationTests(unittest.TestCase):
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


class CliFailureTests(unittest.TestCase):
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
                return_value={"path": "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001", "start_commit": BASE, "start_tree": "4" * 40},
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

    def test_timeout_returns_timeout_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value=preflight_result()
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001", "start_commit": BASE, "start_tree": "4" * 40},
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
                return_value={"path": "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001", "start_commit": TARGET, "start_tree": "4" * 40},
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
