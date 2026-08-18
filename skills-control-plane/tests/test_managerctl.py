from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from typing import Any
from unittest import mock

import yaml

CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CONTROL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import managerlib
import managerctl


class FakeHermesAdapter(managerlib.HermesAdapter):
    def __init__(self, root: Path | None = None) -> None:
        self.profiles: set[str] = set()
        self.profile_owners: dict[str, dict] = {}
        self.boards: dict[str, dict] = {}
        self.settings: dict[tuple[str, str], object] = {}
        self.fail_kind: str | None = None
        self.root = root

    def profile_exists(self, name: str) -> bool:
        return name in self.profiles

    def profile_observation(self, name: str) -> dict:
        return {"exists": name in self.profiles, "ownership": copy.deepcopy(self.profile_owners.get(name))}

    def board_exists(self, slug: str) -> bool:
        return slug in self.boards

    def board_observation(self, slug: str) -> dict:
        return copy.deepcopy(self.boards.get(slug, {"exists": False}))

    def profile_skill_root(self, name: str) -> Path:
        if self.root is None:
            raise managerlib.ManagerError("fake profile root unavailable")
        return self.root / "profiles" / name / "skills"

    def get_profile_config(self, name: str, key: str) -> object:
        return self.settings.get((name, key))

    def create_profile(self, action: dict) -> None:
        if self.fail_kind == "create-profile":
            raise managerlib.ManagerError("injected profile failure")
        self.profiles.add(action["target"])
        self.profile_owners[action["target"]] = copy.deepcopy(action["parameters"]["ownership"])
        self.profile_skill_root(action["target"]).mkdir(parents=True, exist_ok=True)

    def delete_profile(self, name: str) -> None:
        self.profiles.discard(name)
        self.profile_owners.pop(name, None)
        root = self.profile_skill_root(name).parent
        if root.exists():
            import shutil
            shutil.rmtree(root)

    def set_profile_config(self, action: dict) -> None:
        if self.fail_kind == "set-profile-config":
            raise managerlib.ManagerError("injected config failure")
        self.settings[(action["target"], action["parameters"]["key"])] = action["parameters"]["value"]

    def unset_profile_config(self, name: str, key: str) -> None:
        self.settings.pop((name, key), None)

    def create_board(self, action: dict) -> None:
        if self.fail_kind == "create-empty-board":
            raise managerlib.ManagerError("injected board failure")
        params = action["parameters"]
        self.boards[action["target"]] = {
            "exists": True, "name": params["name"], "description": params["description"],
            "default_workdir": params["default_workdir"], "task_count": 0,
            "ownership": copy.deepcopy(params["ownership"]),
        }

    def archive_board(self, slug: str) -> None:
        self.boards.pop(slug, None)


class ManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.control = self.root / "skills-control-plane"
        (self.control / "schemas").mkdir(parents=True)
        for name in (
            "project-setup-request.schema.json", "manager-plan.schema.json",
            "manager-journal.schema.json", "lifecycle-evidence.schema.json",
            "skill-candidate-request.schema.json",
            "skill-canary-request.schema.json",
            "skill-update-request.schema.json",
            "project-definition.schema.json",
        ):
            (self.control / "schemas" / name).write_bytes((CONTROL_ROOT / "schemas" / name).read_bytes())
        (self.control / "projects").mkdir()
        (self.control / "releases").mkdir()
        (self.control / "packs").mkdir()
        (self.control / "candidates").mkdir()
        self.repo = self.root / "project"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        (self.repo / "README.md").write_text("test\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo, check=True, stdout=subprocess.DEVNULL)
        self.head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        subprocess.run(["git", "remote", "add", "origin", "git@example.invalid:owner/project.git"], cwd=self.repo, check=True)
        manifest = yaml.safe_load((CONTROL_ROOT / "projects/jellyssh/project.yaml").read_text())
        manifest["project"] = {"slug": "example", "display_name": "Example", "state": "proposed"}
        manifest["authority"].update({
            "remote": "git@example.invalid:owner/project.git",
            "commit": self.head,
            "project_manifest_path": "skills-control-plane/projects/example/project.yaml",
            "manifest_storage": "control-plane",
        })
        profile_names = {
            "coordinator": "examplecoord",
            "implementation": "exampleimpl",
            "reviewer": "examplereview",
        }
        for role, binding in manifest["profiles"].items():
            binding["name"] = profile_names[role]
            binding["workspace"] = str(self.root / f"workspace-{role}")
        for expert, binding in manifest["expert_policy"].items():
            if expert != "risk_levels":
                binding["profile"] = profile_names["reviewer"]
        manifest["execution_policy"]["implementation_review_handoff"]["target_profile"] = profile_names["reviewer"]
        manifest["execution_routes"] = [{
            "id": "implementation-hermes",
            "role": "implementation",
            "owner_profile": profile_names["implementation"],
            "engine": "hermes-worker",
            "host": "jellybase",
            "account": "jellydev",
            "model": copy.deepcopy(manifest["profiles"]["implementation"]["model"]),
            "bundle": "implementation-runtime",
            "workspace": manifest["profiles"]["implementation"]["workspace"],
            "memory": {
                "bank": manifest["profiles"]["implementation"]["bank"],
                "auto_recall": manifest["profiles"]["implementation"]["auto_recall"],
                "auto_retain": manifest["profiles"]["implementation"]["auto_retain"],
            },
            "permissions": ["repository-write", "tests", "git-commit"],
            "preflight": "project-setup-and-work-item",
            "evidence": "commit-tests-independent-review",
            "fallback": "block",
        }]
        manifest["skill_layers"]["project_overlays"] = []
        self.request = {
            "schema_version": 1,
            "project": {"slug": "example", "display_name": "Example"},
            "repository": {
                "path": str(self.repo),
                "remote": "git@example.invalid:owner/project.git",
                "branch": "main",
                "commit": self.head,
                "contract_path": ".hermes-project/project.yaml",
            },
            "project_manifest": manifest,
            "runtime_manifest": {"schema_version": 1, "project": "example", "state": "proposed"},
            "profiles": [{
                "role": role,
                "name": binding["name"],
                "clone_from": "default",
                "description": f"Example {role} profile",
                "no_skills": True,
                "settings": {
                    "model.provider": binding["model"]["provider"],
                    "model.default": binding["model"]["model"],
                    "model.fallback": binding["model"]["fallback"],
                    "terminal.cwd": binding["workspace"],
                },
            } for role, binding in manifest["profiles"].items()],
            "board": {"slug": "example", "name": "Example", "description": "Example board", "default_workdir": str(self.repo)},
            "effects": {
                "write_control_manifest": True, "write_project_contract": True,
                "create_profiles": True, "materialize_profile_skills": False,
                "create_empty_board": True,
            },
        }
        self.request_path = self.root / "request.yaml"
        self.request_path.write_text(yaml.safe_dump(self.request, sort_keys=False))
        self.adapter = FakeHermesAdapter(self.root)
        self.adapter.profiles.add("default")
        self.adapter.profile_skill_root("default").mkdir(parents=True, exist_ok=True)
        (self.control / "catalog.yaml").write_text(yaml.safe_dump({
            "schema_version": 1,
            "catalog_id": "test-control-plane",
            "state": "test",
            "hash_algorithm": "sha256-framed",
            "releases": [{
                "name": "core-development", "version": "0.1.0",
                "manifest": "releases/core-development/0.1.0/release.yaml",
                "bundle_sha256": "sha256:" + "1" * 64,
                "manifest_sha256": "sha256:" + "2" * 64,
            }],
            "packs": [],
            "projects": [{
                "slug": "example", "manifest": "projects/example/project.yaml", "runtime": "projects/example/runtime.yaml",
            }],
        }, sort_keys=False))
        subprocess.run(["git", "init", "-b", "control"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "skills-control-plane"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "control"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        self.control_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, text=True, stdout=subprocess.PIPE
        ).stdout.strip()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_atomic_write_has_single_commit_point(self) -> None:
        target = self.root / "atomic" / "authority.json"
        content = b'{"verdict":"PASS"}\n'
        real_open = os.open
        real_fsync = os.fsync
        real_close = os.close

        def fail_directory_open(path: Any, flags: int, *args: Any) -> int:
            if Path(path) == target.parent:
                raise OSError("directory open fixture")
            return real_open(path, flags, *args)

        with mock.patch.object(managerlib.os, "open", side_effect=fail_directory_open):
            with self.assertRaisesRegex(OSError, "directory open fixture"):
                managerlib._atomic_write(target, content)
        self.assertFalse(target.exists())

        def fail_directory_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory fsync fixture")
            real_fsync(fd)

        with mock.patch.object(managerlib.os, "fsync", side_effect=fail_directory_fsync):
            managerlib._atomic_write(target, content)
        self.assertEqual(target.read_bytes(), content)
        target.unlink()

        def close_then_fail(fd: int) -> None:
            is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            real_close(fd)
            if is_directory:
                raise OSError("directory close fixture")

        with mock.patch.object(managerlib.os, "close", side_effect=close_then_fail):
            managerlib._atomic_write(target, content)
        self.assertEqual(target.read_bytes(), content)

    def test_public_output_write_failure_is_structured_block(self) -> None:
        target = self.root / "fleet.json"
        with (
            mock.patch.object(managerctl.managerlib, "fleet_status", return_value={"state": "GREEN"}),
            mock.patch.object(managerctl.managerlib, "_atomic_write", side_effect=OSError("directory open fixture")),
            mock.patch("builtins.print") as printed,
        ):
            rc = managerctl.main([
                "--control-root", str(self.control), "fleet", "status", "--output", str(target),
            ])
        self.assertEqual(rc, 2)
        self.assertFalse(target.exists())
        self.assertTrue(any("BLOCK:" in str(call) for call in printed.call_args_list))

    def test_plan_is_deterministic_and_hash_bound(self) -> None:
        first = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        second = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertEqual(first, second)
        self.assertEqual(first["plan_sha256"], managerlib.document_digest(first, "plan_sha256"))
        self.assertFalse(first["blockers"])

    def test_execution_route_catalog_requires_declared_owner_bundle_and_block_fallback(self) -> None:
        value = copy.deepcopy(self.request)
        value["project_manifest"].pop("execution_routes")
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)

        value = copy.deepcopy(self.request)
        value["project_manifest"]["execution_routes"] = [{
            "id": "implementation-hermes",
            "role": "implementation",
            "owner_profile": "exampleimpl",
            "engine": "hermes-worker",
            "host": "jellybase",
            "account": "jellydev",
            "model": {"provider": "openai-codex", "model": "gpt-5.6-terra", "fallback": "block"},
            "bundle": "implementation-runtime",
            "workspace": str(self.root / "workspace-implementation"),
            "memory": {"bank": "jellyssh-main", "auto_recall": True, "auto_retain": False},
            "permissions": ["repository-write", "tests", "git-commit"],
            "preflight": "project-setup-and-work-item",
            "evidence": "commit-tests-independent-review",
            "fallback": "block",
        }]
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertFalse(plan["blockers"])

        value["project_manifest"]["execution_routes"][0]["owner_profile"] = "unknownprofile"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertIn("execution route owner profile does not match role binding: implementation-hermes", plan["blockers"])

        value["project_manifest"]["execution_routes"][0]["owner_profile"] = "exampleimpl"
        value["project_manifest"]["execution_routes"][0]["bundle"] = "missing-bundle"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertIn("execution route bundle is not declared: implementation-hermes", plan["blockers"])

        value["project_manifest"]["execution_routes"][0]["bundle"] = "implementation-runtime"
        value["project_manifest"]["execution_routes"][0]["workspace"] = str(self.root / "workspace-reviewer")
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertIn("execution route workspace does not match role binding: implementation-hermes", plan["blockers"])

        value["project_manifest"]["execution_routes"][0]["workspace"] = str(self.root / "workspace-implementation")
        value["project_manifest"]["execution_routes"][0]["memory"]["auto_retain"] = True
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertIn("execution route memory does not match role binding: implementation-hermes", plan["blockers"])

        value["project_manifest"]["execution_routes"][0]["memory"]["auto_retain"] = False
        value["project_manifest"]["execution_routes"][0]["fallback"] = "retry-another-engine"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)

        value = copy.deepcopy(self.request)
        value["project_manifest"]["execution_routes"][0]["owner_profile"] = "examplereview"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        report = managerlib.doctor_project(self.request_path, self.control, self.adapter)
        self.assertTrue(any(item["code"] == "execution-route-owner" for item in report["findings"]))

    def test_dirty_repository_blocks_plan(self) -> None:
        (self.repo / "dirty.txt").write_text("dirty\n")
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertTrue(any("not clean" in item for item in plan["blockers"]))

    def test_secret_shaped_request_key_is_rejected(self) -> None:
        value = copy.deepcopy(self.request)
        value["profiles"][0]["settings"]["model.api_key"] = "not-a-real-key"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)

    def test_secret_shaped_request_value_is_rejected(self) -> None:
        value = copy.deepcopy(self.request)
        value["profiles"][0]["description"] = "github_pat_" + "a" * 30
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)

    def test_underscore_profile_names_match_contracts(self) -> None:
        value = copy.deepcopy(self.request)
        role = value["profiles"][0]["role"]
        value["profiles"][0]["name"] = "example_impl"
        value["profiles"][0]["clone_from"] = "base_profile"
        value["project_manifest"]["profiles"][role]["name"] = "example_impl"
        self.adapter.profiles.add("base_profile")
        self.adapter.profile_skill_root("base_profile").mkdir(parents=True, exist_ok=True)
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertFalse(plan["blockers"])

    def test_routable_setup_authority_blocks(self) -> None:
        value = copy.deepcopy(self.request)
        value["project_manifest"]["project"]["state"] = "routable"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("non-routable" in item for item in plan["blockers"]))
        value = copy.deepcopy(self.request)
        value["project_manifest"]["profiles"]["implementation"]["state"] = "routable"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("profile binding" in item for item in plan["blockers"]))
        for key in ("state", "project_state"):
            value = copy.deepcopy(self.request)
            value["runtime_manifest"] = {"schema_version": 1, "project": "example", key: "routable"}
            self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
            plan = managerlib.build_project_plan(
                self.request_path, self.control, self.adapter, control_commit=self.control_commit
            )
            self.assertTrue(any("runtime manifest" in item and "non-routable" in item for item in plan["blockers"]))
            doctor = managerlib.doctor_project(self.request_path, self.control, self.adapter)
            self.assertEqual(doctor["state"], "RED")
            self.assertTrue(any(item["code"] == "runtime-routable" for item in doctor["findings"]))

    def test_generic_expert_or_handoff_profile_fallback_blocks(self) -> None:
        value = copy.deepcopy(self.request)
        for expert, binding in value["project_manifest"]["expert_policy"].items():
            if expert != "risk_levels":
                binding["profile"] = "default"
        value["project_manifest"]["execution_policy"]["implementation_review_handoff"]["target_profile"] = "default"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("expert binding profile" in item for item in plan["blockers"]))
        self.assertTrue(any("handoff target profile" in item for item in plan["blockers"]))

    def test_lifecycle_schemas_accept_underscore_profile_names(self) -> None:
        canary = yaml.safe_load((CONTROL_ROOT / "templates/skill-canary-request.example.yaml").read_text())
        canary["profile"] = "example_impl"
        managerlib._validate(
            canary,
            managerlib._load_schema(CONTROL_ROOT, "skill-canary-request.schema.json"),
            "skill canary request",
        )
        update = yaml.safe_load((CONTROL_ROOT / "templates/skill-update-request.example.yaml").read_text())
        update["profile_targets"].append({
            "project": "example-project",
            "profile": "example_impl",
            "skills": [{"name": "test-skill", "source_relative_path": "skills/test-skill"}],
        })
        managerlib._validate(
            update,
            managerlib._load_schema(CONTROL_ROOT, "skill-update-request.schema.json"),
            "skill update request",
        )

    def test_wrong_approval_blocks_before_mutation(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, "sha256:" + "0" * 64, self.control, self.adapter, self.root / "journals")
        self.assertEqual(self.adapter.profiles, {"default"})
        self.assertFalse(self.adapter.boards)

    def test_apply_writes_artifacts_and_second_apply_is_noop(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        first = managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.assertEqual(first["state"], "completed")
        self.assertTrue((self.control / "projects/example/project.yaml").is_file())
        self.assertTrue((self.repo / ".hermes-project/project.yaml").is_file())
        self.assertIn("exampleimpl", self.adapter.profiles)
        self.assertIn("example", self.adapter.boards)
        second_plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        second = managerlib.apply_plan(second_plan, second_plan["plan_sha256"], self.control, self.adapter, self.root / "journals2")
        self.assertEqual(second["state"], "completed")
        self.assertTrue(all(item["state"] == "noop" for item in second["entries"]))

    def test_precondition_drift_blocks_before_apply(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        (self.repo / "README.md").write_text("changed\n")
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.assertEqual(self.adapter.profiles, {"default"})

    def test_profile_config_drift_blocks_before_any_apply_action(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.adapter.settings[("exampleimpl", "model.provider")] = "drifted"
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.assertFalse((self.control / "projects/example/project.yaml").exists())

    def test_existing_nonempty_board_blocks_idempotent_setup(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.adapter.boards["example"]["task_count"] = 1
        retry = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertTrue(any("not an exact empty setup board" in item for item in retry["blockers"]))

    def test_rehashed_plan_with_duplicate_action_ids_is_rejected(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        plan["actions"][1]["id"] = plan["actions"][0]["id"]
        plan["plan_sha256"] = managerlib.document_digest(plan, "plan_sha256")
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.assertFalse((self.control / "projects/example/project.yaml").exists())

    def test_manifest_profile_mismatch_is_a_plan_blocker(self) -> None:
        value = copy.deepcopy(self.request)
        value["project_manifest"]["profiles"]["implementation"]["name"] = "otherimpl"
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertTrue(any("profile name does not match" in item for item in plan["blockers"]))

    def test_partial_failure_stops_later_actions_and_writes_journal(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.adapter.fail_kind = "create-profile"
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        self.assertFalse(self.adapter.boards)
        journals = list((self.root / "journals").glob("*.json"))
        self.assertEqual(len(journals), 1)
        self.assertEqual(json.loads(journals[0].read_text())["state"], "failed")

    def test_rollback_restores_pre_apply_state(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        journal = managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        journal_path = next((self.root / "journals").glob("*.json"))
        result = managerlib.rollback_journal(
            journal_path, journal["journal_sha256"], self.control, self.adapter, self.root / "rollbacks"
        )
        self.assertEqual(result["state"], "rolled-back")
        self.assertFalse((self.control / "projects/example/project.yaml").exists())
        self.assertFalse((self.repo / ".hermes-project/project.yaml").exists())
        self.assertEqual(self.adapter.profiles, {"default"})
        self.assertFalse(self.adapter.boards)
        self.assertFalse(self.adapter.settings)

    def test_rollback_drift_blocks_before_any_revert(self) -> None:
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        journal = managerlib.apply_plan(
            plan, plan["plan_sha256"], self.control, self.adapter, self.root / "drift-apply"
        )
        journal_path = next((self.root / "drift-apply").glob("*.json"))
        self.adapter.settings[("exampleimpl", "model.provider")] = "external-drift"
        with self.assertRaises(managerlib.ManagerError):
            managerlib.rollback_journal(
                journal_path, journal["journal_sha256"], self.control, self.adapter,
                self.root / "drift-rollback",
            )
        self.assertIn("example", self.adapter.boards)
        self.assertTrue((self.control / "projects/example/project.yaml").is_file())
        self.assertFalse((self.root / "drift-rollback").exists())

    def _make_skill_update_request(self) -> Path:
        setup = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        managerlib.apply_plan(setup, setup["plan_sha256"], self.control, self.adapter, self.root / "setup-journal")
        source = self.root / "candidate"
        (source / "skills/test-skill").mkdir(parents=True)
        (source / "skills/test-skill/SKILL.md").write_text("---\nname: test-skill\n---\n# Test\n")
        (source / "release.yaml").write_text("schema_version: 1\nname: core-development\nversion: 0.2.0\n")
        bundle_sha, _ = managerlib.tree_snapshot(source)
        manifest_sha = managerlib.bytes_digest((source / "release.yaml").read_bytes())
        candidate_request = {
            "schema_version": 1,
            "candidate": {
                "layer": "release", "name": "core-development", "version": "0.2.0",
                "source_path": str(source), "manifest_path": "release.yaml",
                "bundle_sha256": bundle_sha, "manifest_sha256": manifest_sha,
            },
            "provenance": {"source": "test fixture", "commit": "3" * 40},
            "compatibility": {"tested_against": ["core-development@0.1.0"]},
        }
        candidate_request_path = self.root / "skill-candidate.yaml"
        candidate_request_path.write_text(yaml.safe_dump(candidate_request, sort_keys=False))
        candidate_plan = managerlib.build_skill_candidate_plan(
            candidate_request_path, self.control, control_commit=self.control_commit
        )
        self.assertFalse(candidate_plan["blockers"])
        managerlib.apply_plan(
            candidate_plan, candidate_plan["plan_sha256"], self.control, self.adapter,
            self.root / "candidate-journal",
        )
        candidate_source = self.control / "candidates/releases/core-development/0.2.0"
        subprocess.run(["git", "add", "skills-control-plane/candidates"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "candidate"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        self.control_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, text=True, stdout=subprocess.PIPE
        ).stdout.strip()
        compatibility = self.root / "compatibility.json"
        compatibility.write_text(json.dumps({
            "schema_version": 1, "kind": "compatibility", "result": "PASS", "project": "example",
            "candidate_bundle_sha256": bundle_sha, "candidate_manifest_sha256": manifest_sha,
            "control_commit": self.control_commit,
            "checks": [{"name": "isolated compatibility", "result": "PASS", "evidence_sha256": "sha256:" + "9" * 64}],
        }, sort_keys=True) + "\n")
        canary = self.root / "canary.json"
        canary.write_text(json.dumps({
            "schema_version": 1, "kind": "canary", "result": "PASS", "project": "example",
            "candidate_bundle_sha256": bundle_sha, "candidate_manifest_sha256": manifest_sha,
            "control_commit": self.control_commit,
            "checks": [{"name": "fresh-session canary", "result": "PASS", "evidence_sha256": "sha256:" + "8" * 64}],
        }, sort_keys=True) + "\n")
        updated = copy.deepcopy(self.request["project_manifest"])
        updated["skill_layers"]["core_release"]["version"] = "0.2.0"
        request = {
            "schema_version": 1,
            "candidate": {
                "layer": "release", "name": "core-development", "version": "0.2.0",
                "source_path": str(candidate_source), "manifest_path": "release.yaml",
                "bundle_sha256": bundle_sha,
                "manifest_sha256": manifest_sha,
            },
            "declared_impacted_projects": ["example"],
            "compatibility_evidence": [{
                "project": "example", "path": str(compatibility),
                "sha256": managerlib.bytes_digest(compatibility.read_bytes()),
            }],
            "canary_evidence": {
                "project": "example", "path": str(canary),
                "sha256": managerlib.bytes_digest(canary.read_bytes()),
            },
            "project_manifest_updates": [{"project": "example", "manifest": updated}],
            "profile_targets": [{
                "project": "example", "profile": "exampleimpl",
                "skills": [{"name": "test-skill", "source_relative_path": "skills/test-skill"}],
            }],
        }
        path = self.root / "skill-update.yaml"
        path.write_text(yaml.safe_dump(request, sort_keys=False))
        return path

    def test_skill_inventory_update_promotion_and_rollback(self) -> None:
        request_path = self._make_skill_update_request()
        impact = managerlib.skill_impact(self.root / "skill-candidate.yaml", self.control)
        self.assertEqual([item["project"] for item in impact["impacted_projects"]], ["example"])
        inventory = managerlib.skill_inventory(self.control)
        self.assertEqual(inventory["projects"][0]["slug"], "example")
        plan = managerlib.build_skill_update_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertFalse(plan["blockers"])
        journal = managerlib.apply_plan(
            plan, plan["plan_sha256"], self.control, self.adapter, self.root / "promotion-journal"
        )
        self.assertTrue((self.control / "releases/core-development/0.2.0/release.yaml").is_file())
        self.assertTrue((self.adapter.profile_skill_root("exampleimpl") / "test-skill/SKILL.md").is_file())
        journal_path = next((self.root / "promotion-journal").glob("*.json"))
        rolled_back = managerlib.rollback_journal(
            journal_path, journal["journal_sha256"], self.control, self.adapter, self.root / "promotion-rollback"
        )
        self.assertEqual(rolled_back["state"], "rolled-back")
        self.assertFalse((self.control / "releases/core-development/0.2.0").exists())
        self.assertTrue((self.control / "candidates/releases/core-development/0.2.0").is_dir())
        self.assertFalse((self.adapter.profile_skill_root("exampleimpl") / "test-skill").exists())
        restored = yaml.safe_load((self.control / "projects/example/project.yaml").read_text())
        self.assertEqual(restored["skill_layers"]["core_release"]["version"], "0.1.0")

    def test_skill_promotion_blocks_without_complete_evidence(self) -> None:
        request_path = self._make_skill_update_request()
        value = yaml.safe_load(request_path.read_text())
        value["compatibility_evidence"] = []
        request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_skill_update_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("compatibility evidence" in item for item in plan["blockers"]))
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "blocked-journal")

    def test_skill_promotion_blocks_invalid_manifest_update_and_missing_overlay_compatibility(self) -> None:
        request_path = self._make_skill_update_request()
        value = yaml.safe_load(request_path.read_text())
        update = value["project_manifest_updates"][0]["manifest"]
        update["unexpected"] = "not allowed"
        request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_skill_update_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("schema validation failed" in item for item in plan["blockers"]))

        value = yaml.safe_load(request_path.read_text())
        value["project_manifest_updates"][0]["manifest"].pop("unexpected")
        value["project_manifest_updates"][0]["manifest"]["skill_layers"]["project_overlays"] = [{
            "name": "example-overlay",
            "version": "0.1.0",
            "path": "skills-control-plane/projects/example/overlays/example-overlay",
            "authority": "control-plane",
            "bundle_sha256": "sha256:" + "7" * 64,
            "tested_against": ["core-development@0.1.0"],
        }]
        request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_skill_update_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("overlay compatibility" in item for item in plan["blockers"]))

    def test_skill_canary_plan_apply_and_rollback(self) -> None:
        promotion_path = self._make_skill_update_request()
        promotion = yaml.safe_load(promotion_path.read_text())
        canary_request = {
            "schema_version": 1,
            "candidate": promotion["candidate"],
            "project": "example",
            "profile": "exampleimpl",
            "skills": promotion["profile_targets"][0]["skills"],
            "compatibility_evidence": promotion["compatibility_evidence"][0],
        }
        request_path = self.root / "skill-canary.yaml"
        request_path.write_text(yaml.safe_dump(canary_request, sort_keys=False))
        plan = managerlib.build_skill_canary_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertFalse(plan["blockers"])
        journal = managerlib.apply_plan(
            plan, plan["plan_sha256"], self.control, self.adapter, self.root / "canary-journal"
        )
        skill = self.adapter.profile_skill_root("exampleimpl") / "test-skill"
        self.assertTrue((skill / "SKILL.md").is_file())
        journal_path = next((self.root / "canary-journal").glob("*.json"))
        result = managerlib.rollback_journal(
            journal_path, journal["journal_sha256"], self.control, self.adapter,
            self.root / "canary-rollback",
        )
        self.assertEqual(result["state"], "rolled-back")
        self.assertFalse(skill.exists())

    def test_skill_promotion_blocks_on_hash_valid_blocking_canary(self) -> None:
        request_path = self._make_skill_update_request()
        value = yaml.safe_load(request_path.read_text())
        canary_path = Path(value["canary_evidence"]["path"])
        evidence = json.loads(canary_path.read_text())
        evidence["result"] = "BLOCK"
        canary_path.write_text(json.dumps(evidence, sort_keys=True) + "\n")
        value["canary_evidence"]["sha256"] = managerlib.bytes_digest(canary_path.read_bytes())
        request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        plan = managerlib.build_skill_update_plan(
            request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("canary evidence" in item for item in plan["blockers"]))

    def test_doctor_and_fleet_report_exact_setup(self) -> None:
        before = managerlib.doctor_project(self.request_path, self.control, self.adapter)
        self.assertEqual(before["state"], "RED")
        self.assertEqual(before["request_path"], str(self.request_path.resolve()))
        report_path = self.root / "doctor.json"
        report_path.write_text(json.dumps(before, sort_keys=True) + "\n")
        reconcile = managerlib.build_project_reconcile_plan(
            report_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertEqual(reconcile["kind"], "project-reconcile")
        self.assertEqual(reconcile["created_from"]["request_sha256"], before["request_sha256"])
        self.assertFalse(reconcile["blockers"])
        self.assertTrue(reconcile["actions"])
        self.request_path.write_text(self.request_path.read_text() + "\n")
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_reconcile_plan(
                report_path, self.control, self.adapter, control_commit=self.control_commit
            )
        self.request_path.write_text(yaml.safe_dump(self.request, sort_keys=False))
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        after = managerlib.doctor_project(self.request_path, self.control, self.adapter)
        self.assertEqual(after["state"], "GREEN")
        for runtime_state, expected in (
            ("reviewed-update-available", "BLUE"),
            ("pinned", "AMBER"),
            ("inventory-only", "GREY"),
        ):
            value = copy.deepcopy(self.request)
            value["runtime_manifest"] = {"schema_version": 1, "project": "example", "state": runtime_state}
            value["effects"] = {
                "write_control_manifest": False,
                "write_project_contract": False,
                "create_profiles": False,
                "materialize_profile_skills": False,
                "create_empty_board": False,
            }
            self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
            self.assertEqual(managerlib.doctor_project(self.request_path, self.control, self.adapter)["state"], expected)
            runtime_path = self.control / "projects/example/runtime.yaml"
            runtime_path.write_text(yaml.safe_dump({"schema_version": 1, "project": "example", "state": runtime_state}, sort_keys=False))
            self.assertEqual(managerlib.fleet_status(self.control)["projects"][0]["state"], expected)
        self.request_path.write_text(yaml.safe_dump(self.request, sort_keys=False))
        (self.control / "projects/example/runtime.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "project": "example", "state": "proposed"}, sort_keys=False)
        )
        fleet = managerlib.fleet_status(self.control)
        self.assertEqual(fleet["projects"][0]["slug"], "example")
        self.assertEqual(fleet["projects"][0]["runtime_evidence_scopes"], {})
        self.assertEqual(fleet["projects"][0]["current_state_source"], "runtime-manifest")
        self.assertEqual(fleet, managerlib.fleet_status(self.control))
        markdown = managerlib.render_fleet_markdown(fleet)
        self.assertIn("Example", markdown)
        self.assertIn("GREEN", markdown)
        generated = self.control / "generated"
        generated.mkdir()
        (generated / "fleet-status.json").write_text(json.dumps(fleet, indent=2, sort_keys=True) + "\n")
        (generated / "fleet-status.md").write_text(markdown)
        self.assertTrue(managerlib.verify_manager(self.control)["ok"])
        (generated / "fleet-status.md").write_text(markdown.replace("GREEN", "AMBER", 1))
        verify = managerlib.verify_manager(self.control)
        self.assertFalse(verify["ok"])
        self.assertIn("generated fleet-status.md is stale", verify["errors"])
        (generated / "fleet-status.md").write_text(markdown)
        (generated / "setup.plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
        self.assertTrue(managerlib.verify_manager(self.control)["ok"])
        broken_plan = copy.deepcopy(plan)
        broken_plan["project"] = "other"
        (generated / "setup.plan.json").write_text(json.dumps(broken_plan, indent=2, sort_keys=True) + "\n")
        verify = managerlib.verify_manager(self.control)
        self.assertFalse(verify["ok"])
        self.assertTrue(any("manager plan digest mismatch" in item for item in verify["errors"]))

    def test_authority_manifest_secret_values_fail_verify_and_do_not_render(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        project_path = self.control / "projects/example/project.yaml"
        manifest = yaml.safe_load(project_path.read_text())
        secret = "github_pat_" + "a" * 30
        manifest["project"]["display_name"] = secret
        project_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
        verify = managerlib.verify_manager(self.control)
        self.assertFalse(verify["ok"])
        self.assertTrue(any("secret-shaped value" in item for item in verify["errors"]))
        fleet = managerlib.fleet_status(self.control)
        rendered = managerlib.render_fleet_markdown(fleet)
        self.assertNotIn(secret, json.dumps(fleet, sort_keys=True))
        self.assertNotIn(secret, rendered)
        self.assertEqual(fleet["projects"][0]["state"], "RED")

    def test_runtime_and_lifecycle_evidence_secret_values_fail_verify(self) -> None:
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        managerlib.apply_plan(plan, plan["plan_sha256"], self.control, self.adapter, self.root / "journals")
        secret = "github_pat_" + "a" * 30
        runtime_path = self.control / "projects/example/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text())
        runtime["notes"] = secret
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False))
        verify = managerlib.verify_manager(self.control)
        self.assertFalse(verify["ok"])
        self.assertTrue(any("secret-shaped value" in item for item in verify["errors"]))
        runtime.pop("notes")
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False))
        evidence = {
            "schema_version": 1,
            "kind": "compatibility",
            "result": "PASS",
            "project": "example",
            "candidate_bundle_sha256": "sha256:" + "1" * 64,
            "candidate_manifest_sha256": "sha256:" + "2" * 64,
            "control_commit": self.control_commit,
            "checks": [{"name": secret, "result": "PASS", "evidence_sha256": "sha256:" + "3" * 64}],
        }
        (self.control / "generated").mkdir(exist_ok=True)
        (self.control / "generated/lifecycle-evidence.json").write_text(json.dumps(evidence, sort_keys=True) + "\n")
        verify = managerlib.verify_manager(self.control)
        self.assertFalse(verify["ok"])
        self.assertTrue(any("secret-shaped value" in item for item in verify["errors"]))

    def test_existing_profile_config_secret_blocks_without_plan_leak(self) -> None:
        secret = "github_pat_" + "a" * 30
        self.adapter.profiles.add("exampleimpl")
        self.adapter.profile_owners["exampleimpl"] = {"schema_version": 1, "owner": "skills-manager", "project": "example"}
        self.adapter.profile_skill_root("exampleimpl").mkdir(parents=True, exist_ok=True)
        self.adapter.settings[("exampleimpl", "model.provider")] = secret
        plan = managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)
        self.assertTrue(any("existing profile config" in item for item in plan["blockers"]))
        self.assertNotIn(secret, json.dumps(plan, sort_keys=True))

    def test_managerctl_project_doctor_and_reconcile_cli_seam(self) -> None:
        doctor_path = self.root / "doctor-cli.json"
        reconcile_path = self.root / "reconcile-cli.json"
        with (
            mock.patch.object(managerctl, "_adapter", return_value=self.adapter),
            mock.patch.object(managerctl, "_control_commit", return_value=self.control_commit),
        ):
            doctor_rc = managerctl.main([
                "--control-root", str(self.control),
                "project", "doctor",
                "--request", str(self.request_path),
                "--output", str(doctor_path),
            ])
            self.assertEqual(doctor_rc, 1)
            doctor = json.loads(doctor_path.read_text())
            self.assertEqual(doctor["state"], "RED")
            self.assertEqual(doctor["request_path"], str(self.request_path.resolve()))
            reconcile_rc = managerctl.main([
                "--control-root", str(self.control),
                "project", "reconcile",
                "--doctor-report", str(doctor_path),
                "--output", str(reconcile_path),
            ])
            self.assertEqual(reconcile_rc, 0)
            reconcile = json.loads(reconcile_path.read_text())
            self.assertEqual(reconcile["kind"], "project-reconcile")
            self.assertEqual(reconcile["created_from"]["request_sha256"], doctor["request_sha256"])
            self.assertTrue(reconcile["actions"])

    def test_setup_materializes_exact_declared_profile_skills(self) -> None:
        import shutil
        source_release = CONTROL_ROOT / "releases/core-development/0.1.0"
        target_release = self.control / "releases/core-development/0.1.0"
        shutil.copytree(source_release, target_release)
        value = copy.deepcopy(self.request)
        value["project_manifest"]["skill_layers"]["capability_packs"] = []
        for binding in value["project_manifest"]["profiles"].values():
            binding["bundle"] = "design"
        for route in value["project_manifest"]["execution_routes"]:
            route["bundle"] = "design"
        value["effects"]["materialize_profile_skills"] = True
        self.request_path.write_text(yaml.safe_dump(value, sort_keys=False))
        catalog_path = self.control / "catalog.yaml"
        catalog = yaml.safe_load(catalog_path.read_text())
        core = value["project_manifest"]["skill_layers"]["core_release"]
        catalog["releases"][0]["bundle_sha256"] = core["bundle_sha256"]
        catalog["releases"][0]["manifest_sha256"] = core["manifest_sha256"]
        catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False))
        subprocess.run(["git", "add", "skills-control-plane"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "skill authority"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        self.control_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root, check=True, text=True, stdout=subprocess.PIPE
        ).stdout.strip()
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertFalse(plan["blockers"])
        managerlib.apply_plan(
            plan, plan["plan_sha256"], self.control, self.adapter, self.root / "skill-setup-journal"
        )
        for profile in value["profiles"]:
            self.assertTrue(
                (self.adapter.profile_skill_root(profile["name"]) / "grill-with-docs/SKILL.md").is_file()
            )
        doctor = managerlib.doctor_project(self.request_path, self.control, self.adapter)
        self.assertEqual(doctor["state"], "GREEN")

    def test_existing_unowned_profile_blocks_setup(self) -> None:
        self.adapter.profiles.add("exampleimpl")
        self.adapter.profile_skill_root("exampleimpl").mkdir(parents=True, exist_ok=True)
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("profile is not owned" in item for item in plan["blockers"]))

    def test_existing_unowned_board_blocks_setup(self) -> None:
        board = self.request["board"]
        self.adapter.boards["example"] = {
            "exists": True, "name": board["name"], "description": board["description"],
            "default_workdir": board["default_workdir"], "task_count": 0, "ownership": None,
        }
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        self.assertTrue(any("existing board" in item for item in plan["blockers"]))

    def test_schema_rejects_broadened_action_parameters(self) -> None:
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        plan["actions"][0]["parameters"]["arbitrary"] = "forbidden"
        plan["plan_sha256"] = managerlib.document_digest(plan, "plan_sha256")
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(
                plan, plan["plan_sha256"], self.control, self.adapter, self.root / "unsafe-journal"
            )

    def test_control_commit_drift_blocks_before_mutation(self) -> None:
        plan = managerlib.build_project_plan(
            self.request_path, self.control, self.adapter, control_commit=self.control_commit
        )
        (self.control / "catalog.yaml").write_text((self.control / "catalog.yaml").read_text() + "\n")
        subprocess.run(["git", "add", "skills-control-plane/catalog.yaml"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "authority drift"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        with self.assertRaises(managerlib.ManagerError):
            managerlib.apply_plan(
                plan, plan["plan_sha256"], self.control, self.adapter, self.root / "authority-journal"
            )
        self.assertFalse((self.control / "projects/example/project.yaml").exists())

    def test_symlink_managed_target_blocks(self) -> None:
        target = self.control / "projects/example/project.yaml"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.repo / "README.md")
        with self.assertRaises(managerlib.ManagerError):
            managerlib.build_project_plan(self.request_path, self.control, self.adapter, control_commit=self.control_commit)


if __name__ == "__main__":
    unittest.main()
