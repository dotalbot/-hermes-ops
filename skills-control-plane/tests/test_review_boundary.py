from __future__ import annotations

from pathlib import Path
import sys
import unittest


CONTROL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "scripts"))

from review_boundary import ReviewRepository


class ReviewSandboxCommandTests(unittest.TestCase):
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
        ):
            with self.subTest(check=check):
                captured.clear()
                self.assertEqual(repository._run_sandboxed_flutter_check(check), "PASS\n")
                self.assertEqual(len(captured), 1)
                script = captured[0][2]
                self.assertIn('"$scratch/repo"', script)
                self.assertIn('"$scratch/repo/app/.dart_tool"', script)
                self.assertIn("--workdir /workspace/repo/app", script)
                self.assertIn(expected_command, script)
                self.assertIn(
                    "dst=/home/jellydev/dev/sdk/flutter-3.44.9,readonly",
                    script,
                )
                self.assertIn("dst=/home/jellydev/.cache/dart-pub,readonly", script)
                self.assertIn("--ulimit fsize=268435456:268435456", script)
                self.assertNotIn("--ulimit fsize=1048576:1048576", script)
                self.assertNotIn("--workdir /workspace/app", script)


if __name__ == "__main__":
    unittest.main()
