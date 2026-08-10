from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "scripts"))

from review_boundary import ReviewRepository, _MATERIALIZE_COMMIT_CODE


class ReviewSandboxCommandTests(unittest.TestCase):
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
                "--no-version-check test --no-pub",
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
