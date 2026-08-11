from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "scripts"))

import review_boundary
from review_boundary import ReviewRepository, _MATERIALIZE_COMMIT_CODE


class ReviewSandboxCommandTests(unittest.TestCase):
    def _run_flutter_reporter(
        self,
        events: Sequence[dict[str, object] | list[dict[str, object]] | str],
        exit_code: int,
        diagnostic_text: str = "",
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as temp:
            stream = Path(temp) / "flutter-test.machine.jsonl"
            diagnostics = Path(temp) / "flutter-test.stderr"
            stream.write_text(
                "\n".join(
                    event if isinstance(event, str) else json.dumps(event, sort_keys=True)
                    for event in events
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostics.write_text(diagnostic_text, encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    review_boundary._FLUTTER_TEST_SUMMARY_CODE,
                    str(stream),
                    str(exit_code),
                    str(diagnostics),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
        return process, json.loads(process.stdout)

    @staticmethod
    def _successful_flutter_events() -> list[dict[str, object]]:
        events: list[dict[str, object]] = [
            {
                "protocolVersion": "0.1.1",
                "runnerVersion": "1.0.0",
                "type": "start",
                "time": 0,
            },
            {
                "test": {"id": 1, "name": "loading suite.dart"},
                "type": "testStart",
                "time": 1,
            },
            {
                "testID": 1,
                "result": "success",
                "skipped": False,
                "hidden": True,
                "type": "testDone",
                "time": 2,
            },
        ]
        for test_id in range(2, 5):
            events.extend(
                [
                    {
                        "test": {"id": test_id, "name": f"visible test {test_id}"},
                        "type": "testStart",
                        "time": test_id,
                    },
                    {
                        "testID": test_id,
                        "messageType": "print",
                        "message": "x" * 200,
                        "type": "print",
                        "time": test_id,
                    },
                    {
                        "testID": test_id,
                        "result": "success",
                        "skipped": False,
                        "hidden": False,
                        "type": "testDone",
                        "time": test_id + 1,
                    },
                ]
            )
        events.extend(
            {"testID": 2, "messageType": "print", "message": "y" * 200, "type": "print", "time": 8}
            for _ in range(5000)
        )
        events.extend(
            [
                {
                    "test": {"id": 5, "name": "skipped test"},
                    "type": "testStart",
                    "time": 9,
                },
                {
                    "testID": 5,
                    "result": "success",
                    "skipped": True,
                    "hidden": False,
                    "type": "testDone",
                    "time": 10,
                },
                {"success": True, "type": "done", "time": 11},
            ]
        )
        return events

    def test_long_flutter_machine_stream_becomes_compact_terminal_summary(self) -> None:
        events: list[dict[str, object] | list[dict[str, object]] | str] = []
        events.extend(self._successful_flutter_events())
        events.insert(10, "")
        events.insert(11, [{"event": "test.startedProcess", "params": {"vmServiceUri": None}}])
        process, summary = self._run_flutter_reporter(events, 0)

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertLessEqual(len(process.stdout.encode("utf-8")), 4096)
        self.assertEqual(
            summary,
            {
                "check": "flutter-test",
                "diagnostics": [],
                "exit_code": 0,
                "failed": 0,
                "passed": 3,
                "protocol_version": "0.1.1",
                "reporter": "json",
                "schema_version": 1,
                "skipped": 1,
                "success": True,
                "terminal": "done",
                "total": 4,
            },
        )

    def test_flutter_machine_stream_requires_complete_protocol_version(self) -> None:
        valid_process, valid_summary = self._run_flutter_reporter(
            self._successful_flutter_events(),
            0,
        )
        incomplete_protocol = self._successful_flutter_events()
        incomplete_protocol[0] = {
            **incomplete_protocol[0],
            "protocolVersion": "0.1.",
        }
        invalid_process, invalid_summary = self._run_flutter_reporter(incomplete_protocol, 0)

        self.assertEqual(valid_process.returncode, 0, valid_process.stderr)
        self.assertTrue(valid_summary["success"])
        self.assertEqual(valid_summary["protocol_version"], "0.1.1")
        self.assertNotEqual(invalid_process.returncode, 0)
        self.assertFalse(invalid_summary["success"])

    def test_flutter_summary_stays_byte_bounded_with_unicode_diagnostics(self) -> None:
        process, summary = self._run_flutter_reporter(
            self._successful_flutter_events(),
            0,
            ("\U0010ffff" * 10000) + "\n",
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(summary["success"])
        diagnostics = summary["diagnostics"]
        self.assertIsInstance(diagnostics, list)
        assert isinstance(diagnostics, list)
        self.assertEqual(len(diagnostics), 1)
        self.assertLessEqual(len(process.stdout.encode("utf-8")), 4096)

    def test_flutter_machine_stream_fails_closed_without_consistent_terminal_success(self) -> None:
        base = self._successful_flutter_events()
        failed_test = [dict(event) if isinstance(event, dict) else event for event in base]
        failed_test[-2] = {
            "testID": 5,
            "result": "failure",
            "skipped": False,
            "hidden": False,
            "type": "testDone",
            "time": 10,
        }
        failed_test[-1] = {"success": False, "type": "done", "time": 11}
        hidden_failure = [dict(event) if isinstance(event, dict) else event for event in base]
        hidden_failure[2] = {
            "testID": 1,
            "result": "failure",
            "skipped": False,
            "hidden": True,
            "type": "testDone",
            "time": 2,
        }
        hidden_failure[-1] = {"success": False, "type": "done", "time": 11}
        failure_marked_skipped = [dict(event) if isinstance(event, dict) else event for event in base]
        failure_marked_skipped[-2] = {
            "testID": 5,
            "result": "failure",
            "skipped": True,
            "hidden": False,
            "type": "testDone",
            "time": 10,
        }
        failure_marked_skipped[-1] = {"success": False, "type": "done", "time": 11}
        cases = {
            "malformed": [*base[:-1], "not-json", base[-1]],
            "malformed-progress": [
                *base[:-1],
                [{"event": "unexpected", "params": {"vmServiceUri": None}}],
                base[-1],
            ],
            "missing-done": base[:-1],
            "duplicate-done": [*base, base[-1]],
            "contradictory-done": [*base[:-1], {"success": False, "type": "done", "time": 11}],
            "nonzero-exit": base,
            "failed-test": failed_test,
            "hidden-failure": hidden_failure,
            "failure-marked-skipped": failure_marked_skipped,
            "incomplete-test": [*base[:-2], base[-1]],
            "unknown-event": [*base[:-1], {"type": "futureEvent", "time": 11}, base[-1]],
        }
        for name, events in cases.items():
            with self.subTest(name=name):
                process, summary = self._run_flutter_reporter(
                    events,
                    1
                    if name in {"nonzero-exit", "failed-test", "hidden-failure", "failure-marked-skipped"}
                    else 0,
                )
                self.assertNotEqual(process.returncode, 0)
                self.assertLessEqual(len(process.stdout.encode("utf-8")), 4096)
                self.assertEqual(summary["schema_version"], 1)
                self.assertEqual(summary["check"], "flutter-test")
                self.assertFalse(summary["success"])
                self.assertLessEqual(len(summary["diagnostics"]), 8)
                self.assertTrue(all(len(item) <= 320 for item in summary["diagnostics"]))

    def test_sandbox_self_check_exercises_readonly_input_and_aggregate_limit(self) -> None:
        repository = object.__new__(ReviewRepository)
        repository.ssh_target = "jellydev@jellybase"
        captured: list[list[str]] = []

        def fake_run(command: list[str], timeout: int = 60) -> bytes:
            captured.append(command)
            return b"SANDBOX_SELF_CHECK=PASS\n"

        repository._run = fake_run  # type: ignore[method-assign]
        self.assertEqual(repository._run_sandbox_self_check(), "SANDBOX_SELF_CHECK=PASS\n")
        script = captured[0][2]
        self.assertIn("--memory 128m --memory-swap 128m", script)
        self.assertIn(
            "--tmpfs /workspace:rw,exec,nosuid,nodev,size=8388608,mode=1777",
            script,
        )
        self.assertIn('src="$scratch/input",dst=/review-input,readonly', script)
        self.assertIn("touch /review-input/forbidden", script)
        self.assertIn("of=/workspace/overflow bs=1048576 count=9", script)
        self.assertNotIn('src="$scratch",dst=/workspace', script)

    def test_flutter_checks_run_from_nested_app_with_matching_project_state(self) -> None:
        repository = object.__new__(ReviewRepository)
        repository.ssh_target = "jellydev@jellybase"
        repository.root = Path("/home/jellydev/dev_projects/jellyssh-review")
        repository.expected_commit = "a" * 40
        captured: list[list[str]] = []

        def fake_run(command: list[str], timeout: int = 60) -> bytes:
            captured.append(command)
            return b"PASS\n"

        repository._run = fake_run  # type: ignore[method-assign]

        for check, expected_command in (
            (
                "flutter-analyze",
                "/opt/flutter/bin/cache/dart-sdk/bin/dart "
                "/opt/flutter/bin/cache/flutter_tools.snapshot "
                "--no-version-check analyze --no-pub",
            ),
            (
                "flutter-test",
                "/opt/flutter/bin/cache/dart-sdk/bin/dart "
                "/opt/flutter/bin/cache/flutter_tools.snapshot "
                "--no-version-check test --machine --no-pub",
            ),
            (
                "dart-format-check",
                "/opt/flutter/bin/cache/dart-sdk/bin/dart "
                "format --output=none --set-exit-if-changed .",
            ),
        ):
            with self.subTest(check=check):
                captured.clear()
                self.assertEqual(repository._run_sandboxed_flutter_check(check), "PASS\n")
                self.assertEqual(len(captured), 1)
                script = captured[0][2]
                self.assertIn('"$scratch/repo"', script)
                self.assertIn('"$scratch/repo/app/.dart_tool"', script)
                self.assertIn("cd /workspace/repo/app", script)
                self.assertIn("--workdir /workspace", script)
                self.assertIn(expected_command, script)
                self.assertIn(
                    "src=/var/tmp/jellyssh-review-runtime/flutter,"
                    "dst=/home/jellydev/dev/sdk/flutter-3.44.9,readonly",
                    script,
                )
                self.assertIn(
                    "src=/var/tmp/jellyssh-review-runtime/dart-pub,"
                    "dst=/home/jellydev/.cache/dart-pub,readonly",
                    script,
                )
                self.assertIn("--memory 4g --memory-swap 4g", script)
                self.assertIn("--env FLUTTER_ALREADY_LOCKED=true", script)
                self.assertIn(
                    "--tmpfs /workspace:rw,exec,nosuid,nodev,size=1073741824,mode=1777",
                    script,
                )
                self.assertIn('src="$scratch",dst=/review-input,readonly', script)
                self.assertIn("--ulimit fsize=268435456:268435456", script)
                if check == "flutter-test":
                    self.assertIn("flutter-test.machine.jsonl", script)
                    self.assertIn("protocol_version", script)
                self.assertNotIn("--ulimit fsize=1048576:1048576", script)
                self.assertNotIn("--workdir /workspace/app", script)
                self.assertNotIn('src="$scratch",dst=/workspace', script)
                self.assertNotIn('src="$scratch/flutter-cache"', script)

    def test_materialization_ignores_git_replacement_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = root / "repository"
            destination = root / "materialized"
            subprocess.run(["git", "init", "-q", str(repository)], check=True)

            payload = repository / "payload.txt"
            payload.write_text("original\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "payload.txt"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Reviewer Test",
                    "-c",
                    "user.email=reviewer@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "original",
                ],
                check=True,
            )
            original = subprocess.check_output(
                ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
            ).strip()

            payload.write_text("replacement\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "payload.txt"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Reviewer Test",
                    "-c",
                    "user.email=reviewer@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "replacement",
                ],
                check=True,
            )
            replacement = subprocess.check_output(
                ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
            ).strip()
            subprocess.run(
                ["git", "-C", str(repository), "replace", original, replacement],
                check=True,
            )
            environment = os.environ.copy()
            environment.pop("GIT_NO_REPLACE_OBJECTS", None)
            self.assertEqual(
                subprocess.check_output(
                    ["git", "-C", str(repository), "show", f"{original}:payload.txt"],
                    text=True,
                    env=environment,
                ),
                "replacement\n",
            )

            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    _MATERIALIZE_COMMIT_CODE,
                    str(repository),
                    original,
                    str(destination),
                ],
                check=True,
                env=environment,
            )
            self.assertEqual(
                (destination / "payload.txt").read_text(encoding="utf-8"),
                "original\n",
            )

            boundary = ReviewRepository(
                repository,
                expected_commit=original,
                allowed_refs=[original],
            )
            self.assertEqual(boundary.git_show(original, "payload.txt"), "original\n")

    def test_integrity_manifest_matches_controller_sources(self) -> None:
        runtime_path = CONTROL_ROOT / "projects/jellyssh/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        expected = runtime["review_boundary"]["implementation_sha256"]
        for name, expected_digest in expected.items():
            source = CONTROL_ROOT / "scripts" / name
            self.assertTrue(source.is_file(), name)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(expected_digest, f"sha256:{digest}")

        project_path = CONTROL_ROOT / "projects/jellyssh/project.yaml"
        project_digest = hashlib.sha256(project_path.read_bytes()).hexdigest()
        self.assertEqual(
            runtime["review_boundary"]["project_manifest_sha256"],
            f"sha256:{project_digest}",
        )


if __name__ == "__main__":
    unittest.main()
