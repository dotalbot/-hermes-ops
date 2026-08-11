from __future__ import annotations

import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from unittest import mock

import yaml


CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CONTROL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import projectctl  # noqa: E402


SPEC_COMMIT = "f6ba58ddeb204437e5a1ec392bb47d892839ef16"
BASE_COMMIT = "e5afc55d43d122c1e03f64667177c12d98c91412"
REMOTE = "git@github.com:dotalbot/jellyssh.git"


class LifecyclePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "skills-control-plane"
        shutil.copytree(CONTROL_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "generated"))
        self.project = self.root / "projects" / "jellyssh" / "project.yaml"
        self.contract_path = self.root / "projects" / "jellyssh" / "bug-008.json"
        self.output = self.root / "generated" / "evidence" / "bug-008.json"
        self.contract = {
            "schema_version": 1,
            "project": "jellyssh",
            "work_item": "BUG-008",
            "phase": "implementation-release",
            "repository": {
                "remote": REMOTE,
                "base_commit": BASE_COMMIT,
                "specification_commit": SPEC_COMMIT,
                "branch": "fix/bug-008-zero-byte-sftp-transfers",
            },
            "checkouts": [
                {
                    "role": "coordinator",
                    "runtime_path": "coordinator_checkout",
                    "path": "/home/jellybot/dev_projects/jellyssh",
                    "transport": "local",
                    "commit": SPEC_COMMIT,
                    "branch": "fix/bug-008-zero-byte-sftp-transfers",
                    "detached": False,
                    "clean": True,
                },
                {
                    "role": "coordinator-review",
                    "runtime_path": "coordinator_review_checkout",
                    "path": "/home/jellybot/dev_projects/jellyssh-review",
                    "transport": "local",
                    "commit": BASE_COMMIT,
                    "branch": "main",
                    "detached": False,
                    "clean": True,
                },
                {
                    "role": "implementation",
                    "runtime_path": "implementation_checkout",
                    "path": "/home/jellydev/dev_projects/jellyssh",
                    "transport": "ssh",
                    "commit": SPEC_COMMIT,
                    "branch": "fix/bug-008-zero-byte-sftp-transfers",
                    "detached": False,
                    "clean": True,
                },
                {
                    "role": "reviewer",
                    "runtime_path": "reviewer_checkout",
                    "path": "/home/jellydev/dev_projects/jellyssh-review",
                    "transport": "ssh",
                    "commit": BASE_COMMIT,
                    "branch": "main",
                    "detached": False,
                    "clean": True,
                },
            ],
            "board": {
                "slug": "jellyssh",
                "preflight_task_id": "t_11111111",
                "implementation_task_id": "t_22222222",
                "preflight": {
                    "assignee": None,
                    "workspace_kind": "dir",
                    "workspace_path": "/home/jellybot/dev_projects/hermes-ops",
                    "permitted_statuses": ["ready", "running"],
                },
                "implementation": {
                    "assignee": "jellybase_jellyssh",
                    "workspace_kind": "dir",
                    "workspace_path": "/var/tmp/hermes-jellyssh",
                    "permitted_statuses": ["blocked"],
                },
            },
            "concurrency": {"max_spawn": 1, "max_in_progress": 1},
        }
        self.contract_path.write_text(json.dumps(self.contract), encoding="utf-8")
        self.checkout_observations = {
            item["role"]: {
                "role": item["role"],
                "runtime_path": item["runtime_path"],
                "path": item["path"],
                "transport": item["transport"],
                "commit": item["commit"],
                "branch": item["branch"],
                "detached": item["detached"],
                "clean": item["clean"],
                "remote": REMOTE,
                "replacement_refs": [],
            }
            for item in self.contract["checkouts"]
        }
        self.board_observation = {
            "slug": "jellyssh",
            "default_workdir": "/var/tmp/hermes-jellyssh",
            "tasks": {
                "t_11111111": {
                    "id": "t_11111111",
                    "assignee": None,
                    "status": "running",
                    "workspace_kind": "dir",
                    "workspace_path": "/home/jellybot/dev_projects/hermes-ops",
                    "parents": [],
                    "events": [{"id": 1, "kind": "created"}],
                },
                "t_22222222": {
                    "id": "t_22222222",
                    "assignee": "jellybase_jellyssh",
                    "status": "blocked",
                    "workspace_kind": "dir",
                    "workspace_path": "/var/tmp/hermes-jellyssh",
                    "parents": ["t_11111111"],
                    "events": [
                        {"id": 2, "kind": "created", "initial_status": "blocked"},
                        {"id": 3, "kind": "blocked"},
                    ],
                },
            },
        }
        self.scan_result = {
            "ok": True,
            "project": "jellyssh",
            "project_state": "proposed",
            "errors": [],
            "warnings": [],
            "skills": {"implement": {}},
            "source_digests": {
                "project_manifest": "sha256:" + "1" * 64,
                "runtime_manifest": "sha256:" + "2" * 64,
                "catalog": "sha256:" + "3" * 64,
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_preflight(self) -> dict[str, Any]:
        self.contract_path.write_text(json.dumps(self.contract), encoding="utf-8")
        with mock.patch.object(projectctl, "scan", return_value=copy.deepcopy(self.scan_result)):
            return projectctl.preflight(
                self.project,
                self.contract_path,
                self.output,
                self.root,
                observed_at="2026-08-11T09:00:00Z",
                checkout_observer=lambda item: copy.deepcopy(self.checkout_observations[item["role"]]),
                board_observer=lambda slug, task_ids: copy.deepcopy(self.board_observation),
            )

    def test_valid_lifecycle_contract_writes_pass_evidence(self) -> None:
        result = self.run_preflight()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence_path"], str(self.output.resolve()))
        evidence = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(evidence["verdict"], "PASS")
        self.assertEqual(evidence["observed_at"], "2026-08-11T09:00:00Z")
        self.assertRegex(evidence["contract_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(result["evidence_sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_unknown_contract_field_fails_closed_without_pass_evidence(self) -> None:
        self.contract["unexpected"] = True

        result = self.run_preflight()

        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("Additional properties are not allowed", "\n".join(result["errors"]))
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["verdict"], "BLOCK")

    def test_malformed_runtime_authority_returns_structured_block(self) -> None:
        runtime_path = self.project.parent / "runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["board"] = []
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = self.run_preflight()

        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("lifecycle authority invalid", "\n".join(result["errors"]))
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["verdict"], "BLOCK")

    def test_checkout_ref_remote_cleanliness_and_replacement_drift_block(self) -> None:
        mutations = {
            "commit": "0" * 40,
            "branch": "main",
            "remote": "git@github.com:example/wrong.git",
            "clean": False,
            "replacement_refs": ["refs/replace/" + SPEC_COMMIT],
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                original = self.checkout_observations["coordinator"][field]
                self.checkout_observations["coordinator"][field] = value
                result = self.run_preflight()
                self.checkout_observations["coordinator"][field] = original
                self.assertFalse(result["ok"])
                self.assertIn("coordinator checkout", "\n".join(result["errors"]))
                self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["verdict"], "BLOCK")

    def test_local_checkout_observation_reports_replacement_refs_without_dereferencing_them(self) -> None:
        repository = Path(self.temp.name) / "repository"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(["git", "-C", str(repository), "remote", "add", "origin", REMOTE], check=True)
        payload = repository / "payload.txt"
        commits = []
        for content in ("original\n", "replacement\n"):
            payload.write_text(content, encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "payload.txt"], check=True)
            subprocess.run([
                "git", "-C", str(repository), "-c", "user.name=Preflight Test",
                "-c", "user.email=preflight@example.invalid", "commit", "-q", "-m", content.strip(),
            ], check=True)
            commits.append(subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip())
        subprocess.run(["git", "-C", str(repository), "replace", commits[0], commits[1]], check=True)
        subprocess.run(["git", "-C", str(repository), "checkout", "-q", "-b", "fix/test", commits[0]], check=True)

        observed = projectctl.observe_checkout({
            "role": "coordinator",
            "runtime_path": "coordinator_checkout",
            "path": str(repository),
            "transport": "local",
        })

        self.assertEqual(observed["commit"], commits[0])
        self.assertEqual(observed["branch"], "fix/test")
        self.assertEqual(observed["replacement_refs"], ["refs/replace/" + commits[0]])

    def test_local_checkout_observation_rejects_symlinked_path(self) -> None:
        repository = Path(self.temp.name) / "real-repository"
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        link = Path(self.temp.name) / "linked-repository"
        link.symlink_to(repository, target_is_directory=True)

        with self.assertRaisesRegex(projectctl.ControlPlaneError, "checkout path is not canonical"):
            projectctl.observe_checkout({
                "role": "coordinator",
                "runtime_path": "coordinator_checkout",
                "path": str(link),
                "transport": "local",
            })

    def test_board_observation_rejects_symlinked_boards_directory(self) -> None:
        home = Path(self.temp.name) / "home"
        kanban = home / ".hermes" / "kanban"
        kanban.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside-boards"
        board = outside / "jellyssh"
        board.mkdir(parents=True)
        (board / "board.json").write_text(
            json.dumps({"slug": "jellyssh", "default_workdir": "/var/tmp/hermes-jellyssh"}),
            encoding="utf-8",
        )
        sqlite3.connect(board / "kanban.db").close()
        (kanban / "boards").symlink_to(outside, target_is_directory=True)

        with mock.patch.object(Path, "home", return_value=home):
            with self.assertRaisesRegex(projectctl.ControlPlaneError, "board authority parent cannot be a symlink"):
                projectctl.observe_board("jellyssh", [])

    def test_board_parent_status_assignee_workspace_and_slug_drift_block(self) -> None:
        mutations = [
            ("parent", lambda board: board["tasks"]["t_22222222"].update(parents=[])),
            ("status", lambda board: board["tasks"]["t_22222222"].update(status="ready")),
            ("assignee", lambda board: board["tasks"]["t_22222222"].update(assignee="default")),
            ("workspace", lambda board: board["tasks"]["t_22222222"].update(workspace_path="/tmp/wrong")),
            ("slug", lambda board: board.update(slug="wrong")),
        ]
        original = copy.deepcopy(self.board_observation)
        for label, mutate in mutations:
            with self.subTest(label=label):
                self.board_observation = copy.deepcopy(original)
                mutate(self.board_observation)
                result = self.run_preflight()
                self.assertFalse(result["ok"])
                self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["verdict"], "BLOCK")
        self.board_observation = original

    def test_initial_blocked_status_without_explicit_block_event_is_not_sticky(self) -> None:
        self.board_observation["tasks"]["t_22222222"]["events"] = [
            {"id": 2, "kind": "created", "initial_status": "blocked"}
        ]

        result = self.run_preflight()

        self.assertFalse(result["ok"])
        self.assertIn("explicit sticky blocked event", "\n".join(result["errors"]))

    def test_explicit_block_does_not_replace_required_initial_blocked_state(self) -> None:
        self.board_observation["tasks"]["t_22222222"]["events"][0]["initial_status"] = "running"

        result = self.run_preflight()

        self.assertFalse(result["ok"])
        self.assertIn("was not created blocked", "\n".join(result["errors"]))

    def test_unblock_after_block_invalidates_sticky_hold(self) -> None:
        self.board_observation["tasks"]["t_22222222"]["events"].append({"id": 4, "kind": "unblocked"})

        result = self.run_preflight()

        self.assertFalse(result["ok"])
        self.assertIn("explicit sticky blocked event", "\n".join(result["errors"]))

    def test_output_cannot_escape_evidence_directory(self) -> None:
        outside = Path(self.temp.name) / "outside.json"

        with mock.patch.object(projectctl, "scan", return_value=copy.deepcopy(self.scan_result)):
            result = projectctl.preflight(
                self.project,
                self.contract_path,
                outside,
                self.root,
                observed_at="2026-08-11T09:00:00Z",
                checkout_observer=lambda item: copy.deepcopy(self.checkout_observations[item["role"]]),
                board_observer=lambda slug, task_ids: copy.deepcopy(self.board_observation),
            )

        self.assertFalse(result["ok"])
        self.assertIsNone(result["evidence_path"])
        self.assertFalse(outside.exists())

    def test_atomic_evidence_write_cleans_temp_file_on_replace_failure(self) -> None:
        evidence_root = self.root / "generated" / "evidence"
        with mock.patch.object(Path, "replace", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                projectctl.write_lifecycle_evidence(self.root, self.output, "{}\n")
        self.assertEqual(list(evidence_root.iterdir()), [])

    def test_evidence_parent_symlink_cannot_escape_control_root(self) -> None:
        outside = Path(self.temp.name) / "outside-generated"
        outside.mkdir()
        (self.root / "generated").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(projectctl.ControlPlaneError):
            projectctl.write_lifecycle_evidence(self.root, self.output, "{}\n")
        self.assertEqual(list(outside.iterdir()), [])

    def test_evidence_and_cli_json_are_deterministic(self) -> None:
        first = self.run_preflight()
        first_content = self.output.read_bytes()
        second = self.run_preflight()
        self.assertEqual(first, second)
        self.assertEqual(first_content, self.output.read_bytes())

        cli_result = {
            "ok": False,
            "verdict": "BLOCK",
            "errors": ["fixture"],
            "contract_sha256": "sha256:" + "0" * 64,
            "evidence_path": "/tmp/evidence.json",
            "evidence_sha256": "sha256:" + "1" * 64,
        }
        stdout = io.StringIO()
        with mock.patch.object(projectctl, "preflight", return_value=cli_result), redirect_stdout(stdout):
            exit_code = projectctl.main([
                "--project", str(self.project), "--json", "preflight",
                "--contract", str(self.contract_path), "--output", str(self.output),
            ])
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), cli_result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
