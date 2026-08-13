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


def implementation_request(output: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "attempt_id": "feature-001",
        "mode": "implementation",
        "base_commit": BASE,
        "branch": "feat/example-change",
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
    def test_prompt_is_stdin_and_fixed_route_is_used(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/a.json")
        command = adapter.build_claude_command(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/feature-001")
        self.assertEqual(command.ssh_target, "agent-claude")
        self.assertEqual(command.stdin_text, adapter.build_prompt(request))
        self.assertNotIn(str(request["task"]), " ".join(command.argv))
        self.assertNotIn("--dangerously-skip-permissions", command.argv)
        self.assertNotIn("push", " ".join(command.argv))
        self.assertIn("--permission-mode auto", " ".join(command.argv))
        self.assertIn("timeout --signal=TERM --kill-after=30", " ".join(command.argv))
        self.assertEqual(command.argv[:4], ["ssh", "agent-claude", "bash", "-lc"])
        self.assertTrue(command.argv[-1].startswith("'set -euo pipefail;"))
        self.assertTrue(command.argv[-1].endswith("'"))

    def test_review_uses_plan_mode_and_no_edit_tool(self) -> None:
        request = implementation_request("/home/jellybot/projects/jellyssh-claude-adapter/evidence/r.json")
        request["mode"] = "review"
        request.pop("branch")
        request["target_commit"] = TARGET
        command = adapter.build_claude_command(request, "/home/jellyclaude/dev_projects/jellyssh-worktrees/review-feature-001")
        self.assertIn("--permission-mode plan", " ".join(command.argv))
        self.assertNotIn("Edit", " ".join(command.argv))
        self.assertNotIn("Write", " ".join(command.argv))

    def test_preflight_source_pins_the_governed_hook_and_settings_binding(self) -> None:
        source = (SCRIPTS / "claude_worker_adapter.py").read_text()
        self.assertIn("GOVERNED_HOOK_PATH", source)
        self.assertIn("expected_hook_sha256", source)
        self.assertIn("settings.json", source)
        self.assertIn("block-dangerous-git.py", source)
        self.assertIn("PUSH_UNEXPECTEDLY_ALLOWED", source)
        self.assertIn("write access unexpectedly available", source)


class ResultValidationTests(unittest.TestCase):
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
            ["adapter", "hook", "request_schema", "result_schema"],
        )
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in digests.values()))

    def test_review_requires_one_machine_verdict_line(self) -> None:
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_review_verdict("Review looks fine.")
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_review_verdict("REVIEW_VERDICT=PASS\nREVIEW_VERDICT=BLOCK")
        self.assertEqual(adapter.validate_review_verdict("Finding summary\nREVIEW_VERDICT=PASS"), "PASS")


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


class CliFailureTests(unittest.TestCase):
    def test_timeout_returns_timeout_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "evidence.json"
            request = implementation_request(str(output))
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value={"status": "PASS"}
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/tmp/work", "start_commit": BASE, "start_tree": "4" * 40},
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
            request["target_commit"] = TARGET
            request["checks"] = []
            claude = {
                "session_id": "s",
                "terminal_reason": "completed",
                "models": ["claude-sonnet-5"],
                "summary": "finding\nREVIEW_VERDICT=BLOCK",
            }
            with mock.patch.object(adapter, "load_and_validate_request", return_value=request), mock.patch.object(
                adapter, "preflight", return_value={"status": "PASS"}
            ), mock.patch.object(
                adapter,
                "prepare_worktree",
                return_value={"path": "/tmp/work", "start_commit": TARGET, "start_tree": "4" * 40},
            ), mock.patch.object(
                adapter, "invoke_claude", return_value=subprocess.CompletedProcess(["claude"], 0, "{}", "")
            ), mock.patch.object(adapter, "parse_claude_result", return_value=claude), mock.patch.object(
                adapter,
                "inspect_worktree",
                return_value={"commit": TARGET, "tree": "4" * 40, "branch": "", "changed": []},
            ) as inspect:
                result = adapter.execute(Path("request.json"), allow_test_output=True)
            inspect.assert_called_once()
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertEqual(result["review_verdict"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
