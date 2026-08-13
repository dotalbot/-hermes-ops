from __future__ import annotations

import importlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from typing import Any
from unittest import mock

import jsonschema


CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CONTROL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


class GovernanceTimingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "timing.json"
        self.boot = "11111111-2222-3333-4444-555555555555"
        self.mod = importlib.import_module("governancectl")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _load(self) -> dict[str, object]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_parent_check_rejects_delegated_child_without_unsetting_it(self) -> None:
        ambient = os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT")
        with self.assertRaises(self.mod.GovernanceError):
            self.mod.require_parent_context({"HERMES_DELEGATED_CHILD_CONTEXT": "1"})
        self.assertEqual(os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT"), ambient)
        self.mod.require_parent_context({})

    def test_timing_transitions_are_non_overlapping_and_sum_exactly(self) -> None:
        self.mod.timing_init(
            self.path, "BUG-010", "implementation", "active_execution",
            "2026-08-12T00:00:00+00:00", 100, self.boot, "init-1",
        )
        self.mod.timing_transition(
            self.path, "review_queue", "queue_wait", "CONTINUE",
            "2026-08-12T00:00:00.000100+00:00", 200, self.boot, "transition-1",
        )
        self.mod.timing_transition(
            self.path, "review", "active_execution", "WAIT",
            "2026-08-12T00:00:00.000300+00:00", 400, self.boot, "transition-2",
        )
        result = self.mod.timing_finalize(
            self.path, "PASS", "2026-08-12T00:00:00.000600+00:00", 700, self.boot, "final-1",
        )
        self.assertEqual(result["total_wall_ns"], 600)
        self.assertEqual(result["interval_total_ns"], 600)
        self.assertEqual(result["unattributed_gap_ns"], 0)
        self.assertEqual(result["category_totals_ns"]["active_execution"], 400)
        self.assertEqual(result["category_totals_ns"]["queue_wait"], 200)
        self.assertEqual(result["stage_totals_ns"], {"implementation": 100, "review": 300, "review_queue": 200})
        self.assertEqual(sum(result["stage_totals_ns"].values()), result["interval_total_ns"])
        self.assertEqual([item["duration_ns"] for item in result["intervals"]], [100, 200, 300])
        jsonschema.Draft202012Validator(
            json.loads((CONTROL_ROOT / "schemas/governance-timing.schema.json").read_text(encoding="utf-8")),
            format_checker=jsonschema.FormatChecker(),
        ).validate(result)

    def test_exact_idempotent_replay_is_noop_but_conflicting_replay_blocks(self) -> None:
        args = (self.path, "BUG-010", "implementation", "active_execution", "2026-08-12T00:00:00+00:00", 100, self.boot, "same-key")
        first = self.mod.timing_init(*args)
        second = self.mod.timing_init(*args)
        self.assertEqual(first, second)
        with self.assertRaises(self.mod.GovernanceError):
            self.mod.timing_transition(
                self.path, "review", "active_execution", "PASS",
                "2026-08-12T00:00:01+00:00", 200, self.boot, "same-key",
            )

    def test_cross_boot_or_backwards_monotonic_transition_blocks(self) -> None:
        self.mod.timing_init(
            self.path, "BUG-010", "implementation", "active_execution",
            "2026-08-12T00:00:00+00:00", 100, self.boot, "init",
        )
        for boot, monotonic in (("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", 200), (self.boot, 99)):
            with self.subTest(boot=boot, monotonic=monotonic), self.assertRaises(self.mod.GovernanceError):
                self.mod.timing_transition(
                    self.path, "review", "active_execution", "PASS",
                    "2026-08-12T00:00:01+00:00", monotonic, boot, f"key-{monotonic}",
                )

    def test_timeout_and_block_remain_distinct_outcomes(self) -> None:
        self.mod.timing_init(
            self.path, "BUG-010", "review", "active_execution",
            "2026-08-12T00:00:00+00:00", 10, self.boot, "init",
        )
        self.mod.timing_transition(
            self.path, "remediation", "reviewer_remediation", "TIMEOUT",
            "2026-08-12T00:00:01+00:00", 20, self.boot, "timeout",
        )
        result = self.mod.timing_finalize(
            self.path, "BLOCK", "2026-08-12T00:00:02+00:00", 30, self.boot, "final",
        )
        self.assertEqual(result["intervals"][0]["outcome"], "TIMEOUT")
        self.assertEqual(result["intervals"][1]["outcome"], "BLOCK")
        self.assertNotIn("verdict", result)

    def test_atomic_writer_rejects_relative_path_and_symlink_target(self) -> None:
        with self.assertRaises(self.mod.GovernanceError):
            self.mod.timing_init(
                Path("relative.json"), "BUG-010", "implementation", "active_execution",
                "2026-08-12T00:00:00+00:00", 1, self.boot, "relative",
            )
        target = Path(self.temp.name) / "real.json"
        target.write_text("{}", encoding="utf-8")
        link = Path(self.temp.name) / "link.json"
        link.symlink_to(target)
        with self.assertRaises(self.mod.GovernanceError):
            self.mod.timing_init(
                link, "BUG-010", "implementation", "active_execution",
                "2026-08-12T00:00:00+00:00", 1, self.boot, "link",
            )
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        ancestor = Path(self.temp.name) / "ancestor"
        ancestor.symlink_to(outside, target_is_directory=True)
        escaped = ancestor / "nested" / "timing.json"
        with self.assertRaises(self.mod.GovernanceError):
            self.mod.timing_init(
                escaped, "BUG-010", "implementation", "active_execution",
                "2026-08-12T00:00:00+00:00", 1, self.boot, "ancestor-link",
            )
        self.assertFalse((outside / "nested" / "timing.json").exists())

    def test_atomic_writer_has_no_reported_failure_after_pass_exposure(self) -> None:
        real_fsync = os.fsync
        real_open = os.open
        real_close = os.close

        def fail_directory_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory fsync fixture")
            real_fsync(fd)

        # Directory durability is best-effort after the atomic rename commit
        # point. A post-commit fsync failure must not report failure while PASS
        # is visible.
        with mock.patch.object(self.mod.os, "fsync", side_effect=fail_directory_fsync):
            result = self.mod.timing_init(
                self.path, "BUG-010", "implementation", "active_execution",
                "2026-08-12T00:00:00+00:00", 1, self.boot, "fsync-failure",
            )
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), result)

        self.path.unlink()
        with mock.patch.object(Path, "replace", side_effect=OSError("replace fixture")):
            with self.assertRaisesRegex(self.mod.GovernanceError, "publication failed"):
                self.mod.timing_init(
                    self.path, "BUG-010", "implementation", "active_execution",
                    "2026-08-12T00:00:00+00:00", 1, self.boot, "replace-failure",
                )
        self.assertFalse(self.path.exists())

        def fail_directory_open(path: Any, flags: int, *args: Any) -> int:
            if Path(path) == self.path.parent and flags & getattr(os, "O_DIRECTORY", 0):
                raise OSError("directory open fixture")
            return real_open(path, flags, *args)

        with mock.patch.object(self.mod.os, "open", side_effect=fail_directory_open):
            with self.assertRaisesRegex(self.mod.GovernanceError, "publication failed"):
                self.mod.timing_init(
                    self.path, "BUG-010", "implementation", "active_execution",
                    "2026-08-12T00:00:00+00:00", 1, self.boot, "directory-open-failure",
                )
        self.assertFalse(self.path.exists())

        def fail_directory_close(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory close fixture")
            real_close(fd)

        # Close is also post-commit cleanup and cannot turn exposed PASS into a
        # reported failure.
        with mock.patch.object(self.mod.os, "close", side_effect=fail_directory_close):
            result = self.mod.timing_init(
                self.path, "BUG-010", "implementation", "active_execution",
                "2026-08-12T00:00:00+00:00", 1, self.boot, "directory-close-failure",
            )
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), result)

    def _authority(self) -> dict[str, str]:
        return {
            "repository": "git@github.com:dotalbot/jellyssh.git",
            "base_commit": "1" * 40,
            "specification_commit": "2" * 40,
            "specification_path": "docs/bugs/BUG-010.md",
            "approved_specification_sha256": "sha256:" + "3" * 64,
            "target_commit": "4" * 40,
            "target_tree": "5" * 40,
        }

    def _review_contract(self, capability_digest: str | None = None) -> dict[str, object]:
        return {
            "schema_version": 1,
            "work_item": "BUG-010",
            "review_card_id": "t_abcdef12",
            "capability_evidence_sha256": capability_digest or "sha256:" + "6" * 64,
            "focused_check": "terminal-behaviour-test",
            "authority": self._authority(),
            "required_axes": ["standards", "specification"],
            "expected_workspace_kind": "scratch",
            "expected_max_runtime_seconds": 1200,
            "expected_max_retries": 1,
        }

    def _review_terminal(self, capability_digest: str | None = None) -> dict[str, Any]:
        return {
            "task": {
                "id": "t_abcdef12", "assignee": "jellybase_jellyssh_reviewer",
                "status": "done", "workspace_kind": "scratch",
                "max_runtime_seconds": 1200, "max_retries": 1, "current_run_id": None,
            },
            "parents": [],
            "run": {
                "id": 1, "task_id": "t_abcdef12", "profile": "jellybase_jellyssh_reviewer",
                "status": "done", "max_runtime_seconds": 1200, "started_at": 100,
                "ended_at": 200, "outcome": "completed", "error": None,
                "metadata": {
                    "work_item": "BUG-010", "verdict": "PASS", "findings": [],
                    "standards_axis": "PASS", "specification_axis": "PASS",
                    "capability_evidence_sha256": capability_digest or "sha256:" + "6" * 64,
                    "authority": self._authority(),
                },
            },
        }

    def _write_kanban_fixture(self, review: dict[str, Any], acceptance: dict[str, Any] | None = None) -> Path:
        root = Path(self.temp.name) / "hermes-root"
        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db)
        connection.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, assignee TEXT, status TEXT, workspace_kind TEXT,
                max_runtime_seconds INTEGER, max_retries INTEGER, current_run_id INTEGER
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY, task_id TEXT, profile TEXT, status TEXT,
                max_runtime_seconds INTEGER, started_at INTEGER, ended_at INTEGER,
                outcome TEXT, metadata TEXT, error TEXT
            );
            CREATE TABLE task_links (parent_id TEXT, child_id TEXT, PRIMARY KEY(parent_id, child_id));
        """)
        for terminal in [review] + ([acceptance] if acceptance is not None else []):
            assert terminal is not None
            task = terminal["task"]
            run = terminal["run"]
            connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task["id"], task.get("assignee"), task["status"], task.get("workspace_kind"),
                 task.get("max_runtime_seconds"), task.get("max_retries"), task["current_run_id"]),
            )
            connection.execute(
                "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run["id"], run["task_id"], run.get("profile"), run["status"],
                 run.get("max_runtime_seconds"), run["started_at"], run["ended_at"],
                 run["outcome"], json.dumps(run["metadata"]), run.get("error")),
            )
            for parent in terminal.get("parents", []):
                connection.execute("INSERT INTO task_links VALUES (?, ?)", (parent, task["id"]))
        connection.commit()
        connection.close()
        return root

    def test_active_snapshot_resolves_exact_current_run_pointer(self) -> None:
        active = self._review_terminal()
        active["task"]["status"] = "running"
        active["task"]["current_run_id"] = 1
        active["run"]["status"] = "running"
        active["run"]["ended_at"] = None
        active["run"]["outcome"] = None
        root = self._write_kanban_fixture(active)
        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        connection = sqlite3.connect(db)
        newer = active["run"] | {"id": 2, "started_at": 200}
        connection.execute(
            "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (newer["id"], newer["task_id"], newer["profile"], newer["status"],
             newer["max_runtime_seconds"], newer["started_at"], newer["ended_at"],
             newer["outcome"], json.dumps(newer["metadata"]), newer["error"]),
        )
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            snapshot, _ = self.mod._kanban_snapshot("jellyssh", "t_abcdef12")
        self.assertEqual(snapshot["task"]["current_run_id"], 1)
        self.assertEqual(snapshot["run"]["id"], 1)

    def _capability(self) -> dict[str, object]:
        return {
            "attempt_id": "t_abcdef12",
            "review_specification": {
                "base_commit": "1" * 40,
                "specification_commit": "2" * 40,
                "specification_path": "docs/bugs/BUG-010.md",
                "expected_commit": "4" * 40,
                "expected_tree": "5" * 40,
                "review_type": "final",
                "focused_check": "terminal-behaviour-test",
                "schema_version": 1,
                "project": "jellyssh",
                "paths": ["docs/bugs/BUG-010.md"],
                "focus": [],
            },
            "approved_specification": {"sha256": "sha256:" + "3" * 64},
            "capability_verdict": "PASS",
            "semantic_verdict": None,
        }

    def _write_json(self, name: str, value: object) -> Path:
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_review_binder_reads_canonical_kanban_and_rejects_forged_producer_or_run(self) -> None:
        capability = self._write_json("capability.json", self._capability())
        capability_digest = "sha256:" + hashlib.sha256(capability.read_bytes()).hexdigest()
        contract_value = self._review_contract(capability_digest)
        contract_value.update({
            "kanban_board": "jellyssh",
            "expected_reviewer_profile": "jellybase_jellyssh_reviewer",
        })
        contract = self._write_json("review-contract.json", contract_value)
        terminal: dict[str, Any] = self._review_terminal(capability_digest)
        root = self._write_kanban_fixture(terminal)
        output = Path(self.temp.name) / "review-authority.json"
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
        ):
            result = self.mod.bind_review_authority(
                contract, capability, output, "2026-08-12T01:00:00+00:00"
            )
        self.assertEqual(result["kind"], "governed-review-authority")
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["authority"], self._authority())
        self.assertEqual(result["review_type"], "final")
        self.assertEqual(result["focused_check"], "terminal-behaviour-test")
        self.assertEqual(result["capability_evidence_sha256"], capability_digest)
        self.assertEqual(result["kanban_provenance"]["board"], "jellyssh")
        self.assertEqual(result["kanban_provenance"]["run_id"], 1)
        self.assertEqual(result["kanban_provenance"]["profile"], "jellybase_jellyssh_reviewer")
        self.assertEqual(result["kanban_provenance"]["run_metadata"]["verdict"], "PASS")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

        malformed_capability_value = self._capability()
        malformed_capability_value["review_specification"]["review_type"] = "code"
        malformed_capability = self._write_json("malformed-capability.json", malformed_capability_value)
        malformed_digest = "sha256:" + hashlib.sha256(malformed_capability.read_bytes()).hexdigest()
        malformed_contract_value = self._review_contract(malformed_digest)
        malformed_contract_value.update({
            "kanban_board": "jellyssh",
            "expected_reviewer_profile": "jellybase_jellyssh_reviewer",
        })
        malformed_contract = self._write_json("malformed-contract.json", malformed_contract_value)
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
        ):
            with self.assertRaisesRegex(self.mod.GovernanceError, "review specification is invalid"):
                self.mod.bind_review_authority(
                    malformed_contract, malformed_capability,
                    Path(self.temp.name) / "malformed-authority.json",
                )

        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        connection = sqlite3.connect(db)
        older_completion = terminal["run"] | {"id": 2, "started_at": 50, "ended_at": 150}
        connection.execute(
            "INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (older_completion["id"], older_completion["task_id"], older_completion["profile"],
             older_completion["status"], older_completion["max_runtime_seconds"],
             older_completion["started_at"], older_completion["ended_at"],
             older_completion["outcome"], json.dumps(older_completion["metadata"]),
             older_completion["error"]),
        )
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            latest_ended, _ = self.mod._kanban_snapshot("jellyssh", "t_abcdef12")
        self.assertEqual(latest_ended["run"]["id"], 1)

        secret = "github_pat_" + "a" * 30
        secret_contract_value = json.loads(contract.read_text(encoding="utf-8"))
        secret_contract_value["authority"]["repository"] = secret
        secret_contract = self._write_json("secret-contract.json", secret_contract_value)
        secret_capability_value = json.loads(capability.read_text(encoding="utf-8"))
        secret_capability_value["notes"] = secret
        secret_capability = self._write_json("secret-capability.json", secret_capability_value)
        for name, contract_input, capability_input in (
            ("contract", secret_contract, capability),
            ("capability", contract, secret_capability),
        ):
            with (
                self.subTest(secret_input=name),
                mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
                mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
            ):
                with self.assertRaisesRegex(self.mod.GovernanceError, "secret-shaped material"):
                    self.mod.bind_review_authority(
                        contract_input, capability_input,
                        Path(self.temp.name) / f"secret-{name}-authority.json",
                    )

        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        connection = sqlite3.connect(db)
        secret_metadata = terminal["run"]["metadata"] | {"notes": "github_pat_" + "a" * 30}
        connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(secret_metadata),))
        connection.commit(); connection.close()
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
        ):
            with self.assertRaisesRegex(self.mod.GovernanceError, "secret-shaped material"):
                self.mod.bind_review_authority(contract, capability, Path(self.temp.name) / "secret-review.json")
        connection = sqlite3.connect(db)
        connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(terminal["run"]["metadata"]),))
        connection.commit(); connection.close()

        race_output = Path(self.temp.name) / "race-output.json"
        original_snapshot = self.mod._kanban_snapshot
        calls = 0
        def mutate_before_second_snapshot(board: str, task_id: str) -> tuple[dict[str, Any], str]:
            nonlocal calls
            calls += 1
            if calls == 2:
                connection = sqlite3.connect(root / "kanban" / "boards" / "jellyssh" / "kanban.db")
                changed = terminal["run"]["metadata"] | {"verdict": "BLOCK"}
                connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(changed),))
                connection.commit(); connection.close()
            return original_snapshot(board, task_id)
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod, "_kanban_snapshot", side_effect=mutate_before_second_snapshot),
            mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
        ):
            with self.assertRaisesRegex(self.mod.GovernanceError, "changed before publication"):
                self.mod.bind_review_authority(contract, capability, race_output)
        self.assertFalse(race_output.exists())
        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        db.unlink()
        root = self._write_kanban_fixture(terminal)

        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        for name, statement, values in (
            ("wrong-profile", "UPDATE task_runs SET profile=? WHERE id=1", ("forged",)),
            ("wrong-current-run", "UPDATE tasks SET current_run_id=? WHERE id=?", (99, "t_abcdef12")),
            ("wrong-runtime", "UPDATE tasks SET max_runtime_seconds=? WHERE id=?", (600, "t_abcdef12")),
        ):
            with self.subTest(name=name):
                connection = sqlite3.connect(db)
                connection.execute(statement, values)
                connection.commit()
                connection.close()
                with (
                    mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
                    mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
                ):
                    with self.assertRaises(self.mod.GovernanceError):
                        self.mod.bind_review_authority(
                            contract, capability, Path(self.temp.name) / f"{name}.json",
                            "2026-08-12T01:00:00+00:00",
                        )
                db.unlink()
                (db.parent / "logs").mkdir(exist_ok=True)
                root = self._write_kanban_fixture(terminal)
                db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"

        with mock.patch.dict(os.environ, {
            "HOME": str(Path(self.temp.name) / "caller-home"),
            "HERMES_HOME": str(Path(self.temp.name) / "forged"),
            "HERMES_KANBAN_DB": str(db),
        }):
            self.assertEqual(
                self.mod._shared_hermes_root(),
                Path(self.mod.pwd.getpwuid(os.getuid()).pw_dir) / ".hermes",
            )
        with self.assertRaises(SystemExit):
            self.mod.main(["review-bind", "--contract", str(contract), "--terminal", "forged.json", "--capability", str(capability), "--output", str(output)])

    def test_acceptance_binder_requires_canonical_run_metadata_checks_and_parent(self) -> None:
        schema = json.loads((CONTROL_ROOT / "schemas/governed-acceptance-request.schema.json").read_text())
        hyphenated = {
            "schema_version": 1, "work_item": "BUG-010",
            "acceptance_card_id": "t_1234abcd", "review_card_id": "t_abcdef12",
            "review_authority_sha256": "sha256:" + "1" * 64,
            "kanban_board": "jellyssh", "expected_acceptance_profile": "operator-review",
            "authority": self._authority(),
            "checks": [{"name": "focused-tests", "ok": True, "evidence": "pass"}],
        }
        jsonschema.Draft202012Validator(schema).validate(hyphenated)
        capability = self._write_json("capability-acceptance.json", self._capability())
        capability_digest = "sha256:" + hashlib.sha256(capability.read_bytes()).hexdigest()
        contract_value = self._review_contract(capability_digest)
        contract_value.update({"kanban_board": "jellyssh", "expected_reviewer_profile": "jellybase_jellyssh_reviewer"})
        contract = self._write_json("review-contract.json", contract_value)
        checks = [
            {"name": "focused-tests", "ok": True, "evidence": "19/19"},
            {"name": "full-tests", "ok": True, "evidence": "718/718"},
        ]
        review_terminal: dict[str, Any] = self._review_terminal(capability_digest)
        root = self._write_kanban_fixture(review_terminal)
        review_path = Path(self.temp.name) / "review-authority.json"
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod.reviewctl, "validate_capability_envelope", return_value={}),
        ):
            self.mod.bind_review_authority(contract, capability, review_path, "2026-08-12T01:00:00+00:00")
        review_digest = "sha256:" + hashlib.sha256(review_path.read_bytes()).hexdigest()
        request = {
            "schema_version": 1,
            "work_item": "BUG-010",
            "acceptance_card_id": "t_1234abcd",
            "review_card_id": "t_abcdef12",
            "review_authority_sha256": review_digest,
            "kanban_board": "jellyssh",
            "expected_acceptance_profile": None,
            "authority": self._authority(),
            "checks": checks,
        }
        acceptance = {
            "task": {
                "id": "t_1234abcd", "assignee": None, "status": "done", "workspace_kind": "dir",
                "max_runtime_seconds": None, "max_retries": None, "current_run_id": None,
            },
            "parents": ["t_abcdef12"],
            "run": {
                "id": 2, "task_id": "t_1234abcd", "profile": None, "status": "completed",
                "max_runtime_seconds": None, "started_at": 300, "ended_at": 400,
                "outcome": "completed", "error": None,
                "metadata": {
                    "work_item": "BUG-010", "acceptance_card_id": "t_1234abcd",
                    "verdict": "PASS", "review_card_id": "t_abcdef12",
                    "review_authority_sha256": review_digest,
                    "authority": self._authority(), "checks": checks,
                },
            },
        }
        db = root / "kanban" / "boards" / "jellyssh" / "kanban.db"
        connection = sqlite3.connect(db)
        task = acceptance["task"]; run = acceptance["run"]
        connection.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)", (task["id"], task["assignee"], task["status"], task["workspace_kind"], task["max_runtime_seconds"], task["max_retries"], task["current_run_id"]))
        connection.execute("INSERT INTO task_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run["id"], run["task_id"], run["profile"], run["status"], run["max_runtime_seconds"], run["started_at"], run["ended_at"], run["outcome"], json.dumps(run["metadata"]), run["error"]))
        connection.execute("INSERT INTO task_links VALUES (?, ?)", ("t_abcdef12", "t_1234abcd"))
        connection.commit(); connection.close()
        request_path = self._write_json("acceptance-request.json", request)
        output = Path(self.temp.name) / "acceptance-authority.json"
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            result = self.mod.bind_acceptance_authority(request_path, review_path, output, "2026-08-12T02:00:00+00:00")
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["checks"], checks)
        self.assertEqual(result["kanban_provenance"]["run_metadata"]["checks"], checks)
        self.assertEqual(result["gates"], {"pr_opening": "UNAUTHORIZED", "merge": "UNAUTHORIZED"})

        connection = sqlite3.connect(db)
        connection.execute("UPDATE tasks SET assignee=? WHERE id=?", ("forged-profile", "t_1234abcd"))
        connection.execute("UPDATE task_runs SET profile=? WHERE id=2", ("forged-profile",))
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaisesRegex(self.mod.GovernanceError, "producer"):
                self.mod.bind_acceptance_authority(request_path, review_path, Path(self.temp.name) / "forged-profile.json")
        connection = sqlite3.connect(db)
        connection.execute("UPDATE tasks SET assignee=NULL WHERE id=?", ("t_1234abcd",))
        connection.execute("UPDATE task_runs SET profile=NULL WHERE id=2")
        connection.commit(); connection.close()

        connection = sqlite3.connect(db)
        connection.execute("INSERT INTO task_links VALUES (?, ?)", ("t_deadbeef", "t_1234abcd"))
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaisesRegex(self.mod.GovernanceError, "exact parent"):
                self.mod.bind_acceptance_authority(request_path, review_path, Path(self.temp.name) / "extra-parent.json")
        connection = sqlite3.connect(db)
        connection.execute("DELETE FROM task_links WHERE parent_id=? AND child_id=?", ("t_deadbeef", "t_1234abcd"))
        connection.commit(); connection.close()

        original_snapshot = self.mod._kanban_snapshot
        mutated = False
        def mutate_review_during_acceptance(board: str, task_id: str) -> tuple[dict[str, Any], str]:
            nonlocal mutated
            snapshot = original_snapshot(board, task_id)
            if task_id == "t_1234abcd" and not mutated:
                mutated = True
                connection = sqlite3.connect(db)
                changed = review_terminal["run"]["metadata"] | {"verdict": "BLOCK"}
                connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(changed),))
                connection.commit(); connection.close()
            return snapshot
        with (
            mock.patch.object(self.mod, "_shared_hermes_root", return_value=root),
            mock.patch.object(self.mod, "_kanban_snapshot", side_effect=mutate_review_during_acceptance),
        ):
            with self.assertRaisesRegex(self.mod.GovernanceError, "changed before publication"):
                self.mod.bind_acceptance_authority(request_path, review_path, Path(self.temp.name) / "upstream-race.json")
        connection = sqlite3.connect(db)
        connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(review_terminal["run"]["metadata"]),))
        connection.commit(); connection.close()

        for name, evidence in (
            ("secret", "github_pat_" + "a" * 30),
            ("oversized-utf8", "é" * 3000),
        ):
            with self.subTest(name=name):
                blocked = {**request, "checks": [{"name": "focused-tests", "ok": True, "evidence": evidence}]}
                blocked_path = self._write_json(f"acceptance-{name}.json", blocked)
                blocked_output = Path(self.temp.name) / f"acceptance-{name}-out.json"
                with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
                    with self.assertRaises(self.mod.GovernanceError):
                        self.mod.bind_acceptance_authority(blocked_path, review_path, blocked_output)
                self.assertFalse(blocked_output.exists())

        forged = {**request, "checks": [{"name": "focused-tests", "ok": True, "evidence": "forged"}]}
        forged_path = self._write_json("acceptance-forged.json", forged)
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaises(self.mod.GovernanceError):
                self.mod.bind_acceptance_authority(forged_path, review_path, Path(self.temp.name) / "forged-out.json")

        tampered_review = json.loads(review_path.read_text(encoding="utf-8"))
        tampered_review["axes"]["standards"] = "BLOCK"
        tampered_review_path = self._write_json("tampered-review.json", tampered_review)
        tampered_digest = "sha256:" + hashlib.sha256(tampered_review_path.read_bytes()).hexdigest()
        tampered_request = {**request, "review_authority_sha256": tampered_digest}
        tampered_request_path = self._write_json("tampered-review-request.json", tampered_request)
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaisesRegex(self.mod.GovernanceError, "disagrees with its canonical run metadata"):
                self.mod.bind_acceptance_authority(tampered_request_path, tampered_review_path, Path(self.temp.name) / "tampered-review-out.json")

        connection = sqlite3.connect(db)
        stale_metadata = review_terminal["run"]["metadata"] | {"verdict": "BLOCK"}
        connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(stale_metadata),))
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaisesRegex(self.mod.GovernanceError, "changed before publication"):
                self.mod.bind_acceptance_authority(request_path, review_path, Path(self.temp.name) / "stale-review.json")
        connection = sqlite3.connect(db)
        connection.execute("UPDATE task_runs SET metadata=? WHERE id=1", (json.dumps(review_terminal["run"]["metadata"]),))
        connection.commit(); connection.close()

        connection = sqlite3.connect(db)
        connection.execute("DELETE FROM task_links WHERE child_id=?", ("t_1234abcd",))
        connection.commit(); connection.close()
        with mock.patch.object(self.mod, "_shared_hermes_root", return_value=root):
            with self.assertRaises(self.mod.GovernanceError):
                self.mod.bind_acceptance_authority(request_path, review_path, Path(self.temp.name) / "no-parent.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
