from __future__ import annotations

import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
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
        self.controller_repo_root = Path(self.temp.name) / "controller-repo-authority"
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
                    "workspace_path": str(self.controller_repo_root),
                    "permitted_statuses": ["ready", "running"],
                },
                "implementation": {
                    "assignee": None,
                    "workspace_kind": "dir",
                    "workspace_path": "/var/tmp/hermes-jellyssh",
                    "permitted_statuses": ["todo"],
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
                    "workspace_path": str(self.controller_repo_root),
                    "parents": [],
                    "events": [{"id": 1, "kind": "created"}],
                },
                "t_22222222": {
                    "id": "t_22222222",
                    "assignee": None,
                    "status": "todo",
                    "workspace_kind": "dir",
                    "workspace_path": "/var/tmp/hermes-jellyssh",
                    "parents": ["t_11111111"],
                    "events": [{"id": 2, "kind": "created", "initial_status": "todo"}],
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
                controller_repo_root=self.controller_repo_root,
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

    def test_contract_validation_is_portable_with_injected_controller_authority(self) -> None:
        alternate_repo = Path(self.temp.name) / "alternate-review-checkout"
        alternate_control = alternate_repo / "skills-control-plane"
        shutil.copytree(
            CONTROL_ROOT,
            alternate_control,
            ignore=shutil.ignore_patterns("__pycache__", "generated"),
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(alternate_control / "tests" / "test_projectctl_preflight.py"),
                "LifecyclePreflightTests.test_valid_lifecycle_contract_writes_pass_evidence",
                "LifecyclePreflightTests.test_implementation_child_must_be_unassigned_and_todo_before_parent_completion",
                "LifecyclePreflightTests.test_board_observation_rejects_every_symlinked_authority_component",
            ],
            cwd=alternate_repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("Ran 3 tests", completed.stderr)

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

    def test_board_observation_rejects_every_symlinked_authority_component(self) -> None:
        components = ("hermes", "kanban", "boards", "board", "metadata", "database")
        for component in components:
            with self.subTest(component=component), tempfile.TemporaryDirectory() as case_temp:
                case_root = Path(case_temp)
                home = case_root / "home"
                board = home / ".hermes" / "kanban" / "boards" / "jellyssh"
                board.mkdir(parents=True)
                metadata = board / "board.json"
                database = board / "kanban.db"
                metadata.write_text(
                    json.dumps({"slug": "jellyssh", "default_workdir": "/var/tmp/hermes-jellyssh"}),
                    encoding="utf-8",
                )
                sqlite3.connect(database).close()
                targets = {
                    "hermes": home / ".hermes",
                    "kanban": home / ".hermes" / "kanban",
                    "boards": home / ".hermes" / "kanban" / "boards",
                    "board": board,
                    "metadata": metadata,
                    "database": database,
                }
                target = targets[component]
                outside = case_root / f"outside-{component}"
                if target.is_dir():
                    shutil.copytree(target, outside)
                    shutil.rmtree(target)
                    target.symlink_to(outside, target_is_directory=True)
                else:
                    shutil.copy2(target, outside)
                    target.unlink()
                    target.symlink_to(outside)

                with mock.patch.object(Path, "home", return_value=home):
                    with self.assertRaisesRegex(projectctl.ControlPlaneError, "symlink"):
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

    def test_implementation_child_must_be_unassigned_and_todo_before_parent_completion(self) -> None:
        mutations = {
            "assigned": {"assignee": "jellybase_jellyssh"},
            "ready": {"status": "ready"},
            "blocked": {"status": "blocked"},
        }
        original = copy.deepcopy(self.board_observation)
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                self.board_observation = copy.deepcopy(original)
                self.board_observation["tasks"]["t_22222222"].update(mutation)
                result = self.run_preflight()
                self.assertFalse(result["ok"])
                self.assertIn("implementation task", "\n".join(result["errors"]))
        self.board_observation = original

    def test_disposable_kanban_gate_keeps_child_nonspawnable_until_assignment(self) -> None:
        hermes_agent_root = Path(
            os.environ.get("HERMES_AGENT_SOURCE", str(Path.home() / ".hermes" / "hermes-agent"))
        ).resolve()
        self.assertTrue((hermes_agent_root / "hermes_cli" / "kanban_db.py").is_file())
        gate_root = Path(self.temp.name) / "disposable-kanban-gate"
        database_path = gate_root / "kanban.db"
        code = "\n".join([
            "import json, os",
            "from pathlib import Path",
            "from hermes_cli import kanban_db as kb",
            "from hermes_cli.profiles import profile_exists",
            f"gate_root = Path({str(gate_root)!r}).resolve()",
            f"expected_db = Path({str(database_path)!r}).resolve()",
            "resolved_db = kb.kanban_db_path().resolve()",
            "assert 'HERMES_DELEGATED_CHILD_CONTEXT' not in os.environ",
            "assert resolved_db == expected_db",
            "assert resolved_db.is_relative_to(gate_root)",
            "assert profile_exists('jellybase_jellyssh')",
            "kb.init_db(db_path=resolved_db)",
            "conn = kb.connect(db_path=resolved_db)",
            "try:",
            "    parent = kb.create_task(conn, title='preflight', assignee=None, workspace_kind='dir', workspace_path=str(gate_root / 'controller'))",
            "    child = kb.create_task(conn, title='implementation', assignee=None, workspace_kind='dir', workspace_path=str(gate_root / 'implementation'), parents=[parent])",
            "    assert kb.get_task(conn, child).status == 'todo'",
            "    before = kb.dispatch_once(conn, dry_run=True, max_spawn=1, max_in_progress=1, reconcile_orphans=False)",
            "    assert child not in [item[0] for item in before.spawned]",
            "    assert kb.get_task(conn, child).status == 'todo'",
            "    conn.execute(\"UPDATE tasks SET status = 'ready' WHERE id = ?\", (child,))",
            "    conn.commit()",
            "    assert kb.claim_task(conn, child, claimer='gate-test') is None",
            "    assert kb.get_task(conn, child).status == 'todo'",
            "    rejected = conn.execute(\"SELECT payload FROM task_events WHERE task_id = ? AND kind = 'claim_rejected' ORDER BY id DESC LIMIT 1\", (child,)).fetchone()",
            "    assert json.loads(rejected[0])['reason'] == 'parents_not_done'",
            "    assert kb.complete_task(conn, parent, summary='PASS evidence accepted')",
            "    assert kb.get_task(conn, child).status == 'ready'",
            "    after_pass = kb.dispatch_once(conn, dry_run=True, max_spawn=1, max_in_progress=1, reconcile_orphans=False)",
            "    assert after_pass.promoted == 0",
            "    assert kb.get_task(conn, child).status == 'ready'",
            "    assert child in after_pass.skipped_unassigned",
            "    assert child not in [item[0] for item in after_pass.spawned]",
            "    assert kb.assign_task(conn, child, 'jellybase_jellyssh')",
            "    assigned = conn.execute(\"SELECT payload FROM task_events WHERE task_id = ? AND kind = 'assigned' ORDER BY id DESC LIMIT 1\", (child,)).fetchone()",
            "    assert json.loads(assigned[0])['assignee'] == 'jellybase_jellyssh'",
            "    after_assignment = kb.dispatch_once(conn, dry_run=True, max_spawn=1, max_in_progress=1, reconcile_orphans=False)",
            "    assert child in [item[0] for item in after_assignment.spawned]",
            "    print(json.dumps({'database': str(resolved_db), 'parent': parent, 'child': child, 'status': kb.get_task(conn, child).status}))",
            "finally:",
            "    conn.close()",
        ])
        env = os.environ.copy()
        env.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
        env["HERMES_KANBAN_DB"] = str(database_path)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(hermes_agent_root), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=self.root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(Path(result["database"]), database_path.resolve())
        self.assertEqual(result["status"], "ready")

    def test_output_cannot_escape_evidence_directory(self) -> None:
        outside = Path(self.temp.name) / "outside.json"

        with mock.patch.object(projectctl, "scan", return_value=copy.deepcopy(self.scan_result)):
            result = projectctl.preflight(
                self.project,
                self.contract_path,
                outside,
                self.root,
                observed_at="2026-08-11T09:00:00Z",
                controller_repo_root=self.controller_repo_root,
                checkout_observer=lambda item: copy.deepcopy(self.checkout_observations[item["role"]]),
                board_observer=lambda slug, task_ids: copy.deepcopy(self.board_observation),
            )

        self.assertFalse(result["ok"])
        self.assertIsNone(result["evidence_path"])
        self.assertFalse(outside.exists())

    def test_atomic_evidence_write_failures_never_leave_pass_evidence(self) -> None:
        evidence_root = self.root / "generated" / "evidence"
        real_open = os.open
        real_fsync = os.fsync
        real_close = os.close
        real_unlink = Path.unlink

        invalidation_attempts: list[str] = []

        def fail_post_publish_cleanup_and_target_unlink(
            path: Path, missing_ok: bool = False
        ) -> None:
            if path == self.output:
                invalidation_attempts.append("target-unlink")
                raise OSError("target unlink denied")
            if path.parent == evidence_root:
                raise OSError("stale temp cleanup fixture")
            real_unlink(path, missing_ok=missing_ok)

        def fail_target_truncate_open(path: Any, flags: int, *args: Any) -> int:
            if Path(path) == self.output and flags & os.O_TRUNC:
                invalidation_attempts.append("target-truncate-open")
                raise OSError("fallback open denied")
            return real_open(path, flags, *args)

        with self.subTest(fault="post-publish-cleanup-is-best-effort"):
            try:
                with (
                    mock.patch.object(
                        Path,
                        "unlink",
                        autospec=True,
                        side_effect=fail_post_publish_cleanup_and_target_unlink,
                    ),
                    mock.patch.object(
                        projectctl.os,
                        "open",
                        side_effect=fail_target_truncate_open,
                    ),
                ):
                    projectctl.write_lifecycle_evidence(
                        self.root, self.output, '{"verdict":"PASS"}\n'
                    )
                self.assertEqual(invalidation_attempts, [])
                self.assertEqual(
                    json.loads(self.output.read_text(encoding="utf-8"))["verdict"],
                    "PASS",
                )
            finally:
                for entry in evidence_root.iterdir():
                    real_unlink(entry, missing_ok=True)

        def fail_pre_publish_temp_cleanup(path: Path, missing_ok: bool = False) -> None:
            if path.parent == evidence_root:
                raise OSError("pre-publish cleanup fixture")
            real_unlink(path, missing_ok=missing_ok)

        with self.subTest(fault="pre-publish-cleanup-preserves-primary-failure"):
            try:
                with (
                    mock.patch.object(
                        Path,
                        "replace",
                        side_effect=OSError("replace fixture"),
                    ),
                    mock.patch.object(
                        Path,
                        "unlink",
                        autospec=True,
                        side_effect=fail_pre_publish_temp_cleanup,
                    ),
                ):
                    with self.assertRaisesRegex(OSError, "replace fixture"):
                        projectctl.write_lifecycle_evidence(
                            self.root, self.output, '{"verdict":"PASS"}\n'
                        )
                self.assertFalse(self.output.exists())
            finally:
                for entry in evidence_root.iterdir():
                    real_unlink(entry, missing_ok=True)

        def fail_directory_open(path: Any, flags: int, *args: Any) -> int:
            if Path(path) == evidence_root:
                raise OSError("directory open fixture")
            return real_open(path, flags, *args)

        with self.subTest(fault="directory-open"):
            with mock.patch.object(projectctl.os, "open", side_effect=fail_directory_open):
                with self.assertRaises(OSError):
                    projectctl.write_lifecycle_evidence(
                        self.root, self.output, '{"verdict":"PASS"}\n'
                    )
            self.assertFalse(self.output.exists())

        def fail_directory_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory fsync fixture")
            real_fsync(fd)

        with self.subTest(fault="directory-fsync"):
            with mock.patch.object(projectctl.os, "fsync", side_effect=fail_directory_fsync):
                with self.assertRaises(OSError):
                    projectctl.write_lifecycle_evidence(
                        self.root, self.output, '{"verdict":"PASS"}\n'
                    )
            self.assertFalse(self.output.exists())

        def close_then_fail(fd: int) -> None:
            is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            real_close(fd)
            if is_directory:
                raise OSError("directory close fixture")

        with self.subTest(fault="directory-close"):
            with mock.patch.object(projectctl.os, "close", side_effect=close_then_fail):
                with self.assertRaises(OSError):
                    projectctl.write_lifecycle_evidence(
                        self.root, self.output, '{"verdict":"PASS"}\n'
                    )
            self.assertFalse(self.output.exists())

        def fail_target_unlink(path: Path, missing_ok: bool = False) -> None:
            if path == self.output:
                raise OSError("target unlink fixture")
            real_unlink(path, missing_ok=missing_ok)

        with self.subTest(fault="cleanup-unlink"):
            with (
                mock.patch.object(projectctl.os, "fsync", side_effect=fail_directory_fsync),
                mock.patch.object(Path, "unlink", autospec=True, side_effect=fail_target_unlink),
            ):
                with self.assertRaises(OSError):
                    projectctl.write_lifecycle_evidence(
                        self.root, self.output, '{"verdict":"PASS"}\n'
                    )
            self.assertTrue(self.output.exists())
            self.assertEqual(
                json.loads(self.output.read_text(encoding="utf-8"))["verdict"],
                "BLOCK",
            )

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
