from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


CONTROL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = CONTROL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import projectctl  # noqa: E402
import reviewctl  # noqa: E402
import review_boundary  # noqa: E402
from review_boundary import ReviewBoundaryError, ReviewRepository  # noqa: E402


class ControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "skills-control-plane"
        shutil.copytree(CONTROL_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "generated"))
        self.project = self.root / "projects" / "jellyssh" / "project.yaml"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_current_catalog_and_project_static_scan_pass(self) -> None:
        # Unit tests copy repository authority into a temporary control root.
        # Keep checked-in runtime schema, authority, evidence and bundle checks;
        # skip only mutable host/profile/checkout/MCP/board discovery.
        result = projectctl.scan(self.project, self.root, live_discovery=False)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["project"], "jellyssh")
        self.assertGreaterEqual(len(result["skills"]), 13)

    def test_static_scan_detects_runtime_authority_drift(self) -> None:
        runtime_path = self.project.parent / "runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["project_manifest_sha256"] = "sha256:" + "1" * 64
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any("project authority manifest hash drift" in error for error in result["errors"]),
            result["errors"],
        )

    def test_static_scan_detects_current_controller_source_drift(self) -> None:
        boundary = self.root / "scripts/review_boundary.py"
        boundary.write_text(boundary.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertIn(
            "controller implementation hash drift: review_boundary.py",
            result["errors"],
        )

    def test_static_scan_rejects_controller_source_changed_during_validation(self) -> None:
        boundary = self.root / "scripts/review_boundary.py"
        original_file_sha256 = projectctl.file_sha256
        changed = False

        def racing_file_sha256(path: Path) -> str:
            nonlocal changed
            digest = original_file_sha256(path)
            if path == boundary and not changed:
                boundary.write_text(
                    boundary.read_text(encoding="utf-8") + "\n# concurrent drift\n",
                    encoding="utf-8",
                )
                changed = True
            return digest

        with mock.patch.object(projectctl, "file_sha256", side_effect=racing_file_sha256):
            result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertTrue(changed)
        self.assertFalse(result["ok"])
        self.assertIn(
            "authority changed during validation: controller implementation review_boundary.py",
            result["errors"],
        )

    def test_static_scan_rejects_compact_evidence_changed_during_validation(self) -> None:
        evidence = self.root / "projects/jellyssh/evidence/flutter-test-compact-summary.json"
        original_file_sha256 = projectctl.file_sha256
        changed = False

        def racing_file_sha256(path: Path) -> str:
            nonlocal changed
            digest = original_file_sha256(path)
            if path == evidence and not changed:
                evidence.write_text(
                    evidence.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                )
                changed = True
            return digest

        with mock.patch.object(projectctl, "file_sha256", side_effect=racing_file_sha256):
            result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertTrue(changed)
        self.assertFalse(result["ok"])
        self.assertIn(
            "authority changed during validation: compact Flutter test evidence",
            result["errors"],
        )

    def test_static_scan_never_consumes_transient_unpinned_compact_evidence(self) -> None:
        evidence = self.root / "projects/jellyssh/evidence/flutter-test-compact-summary.json"
        original_bytes = evidence.read_bytes()
        transient = json.loads(original_bytes.decode("utf-8"))
        transient["generated_at"] = "transient-unpinned-value"
        transient_bytes = (json.dumps(transient, indent=2) + "\n").encode("utf-8")
        original_read_bytes = Path.read_bytes
        original_validate = projectctl._validate_compact_flutter_evidence
        injected = False
        observed_generated_at: list[object] = []

        def racing_read_bytes(path: Path) -> bytes:
            nonlocal injected
            content = original_read_bytes(path)
            if path == evidence and not injected:
                path.write_bytes(transient_bytes)
                injected = True
            return content

        def observing_validate(value: object, producer_hashes: object) -> list[str]:
            if isinstance(value, dict):
                observed_generated_at.append(value.get("generated_at"))
            evidence.write_bytes(original_bytes)
            return original_validate(value, producer_hashes)

        with (
            mock.patch.object(Path, "read_bytes", racing_read_bytes),
            mock.patch.object(
                projectctl,
                "_validate_compact_flutter_evidence",
                side_effect=observing_validate,
            ),
        ):
            result = projectctl.scan(self.project, self.root, live_discovery=False)

        original = json.loads(original_bytes.decode("utf-8"))
        self.assertTrue(injected)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(observed_generated_at, [original["generated_at"]])
        self.assertNotEqual(observed_generated_at, [transient["generated_at"]])
        self.assertEqual(evidence.read_bytes(), original_bytes)

    def test_static_scan_never_consumes_transient_unpinned_quality_evidence(self) -> None:
        evidence = self.root / "projects/jellyssh/evidence/flutter-quality-gate.json"
        original_bytes = evidence.read_bytes()
        transient = json.loads(original_bytes.decode("utf-8"))
        transient["project"] = "transient-unpinned-project"
        transient_bytes = (json.dumps(transient, indent=2) + "\n").encode("utf-8")
        original_read_bytes = Path.read_bytes
        original_load_pinned_json = projectctl._load_pinned_json
        injected = False
        observed_projects: list[object] = []

        def racing_read_bytes(path: Path) -> bytes:
            nonlocal injected
            content = original_read_bytes(path)
            if path == evidence and not injected:
                path.write_bytes(transient_bytes)
                injected = True
            return content

        def observing_load(path: Path, expected: object, error: str) -> dict[str, object]:
            value = original_load_pinned_json(path, expected, error)
            if path == evidence:
                observed_projects.append(value.get("project"))
                evidence.write_bytes(original_bytes)
            return value

        with (
            mock.patch.object(Path, "read_bytes", racing_read_bytes),
            mock.patch.object(projectctl, "_load_pinned_json", side_effect=observing_load),
        ):
            result = projectctl.scan(self.project, self.root, live_discovery=False)

        original = json.loads(original_bytes.decode("utf-8"))
        self.assertTrue(injected)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(observed_projects, [original["project"]])
        self.assertNotEqual(observed_projects, [transient["project"]])
        self.assertEqual(evidence.read_bytes(), original_bytes)

    def test_static_scan_rejects_quality_evidence_changed_during_validation(self) -> None:
        evidence = self.root / "projects/jellyssh/evidence/flutter-quality-gate.json"
        original_file_sha256 = projectctl.file_sha256
        changed = False

        def racing_file_sha256(path: Path) -> str:
            nonlocal changed
            digest = original_file_sha256(path)
            if path == evidence and not changed:
                evidence.write_text(
                    evidence.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                )
                changed = True
            return digest

        with mock.patch.object(projectctl, "file_sha256", side_effect=racing_file_sha256):
            result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertTrue(changed)
        self.assertFalse(result["ok"])
        self.assertIn(
            "authority changed during validation: Flutter quality evidence",
            result["errors"],
        )

    def test_runtime_evidence_scopes_are_required(self) -> None:
        runtime_path = self.project.parent / "runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        del runtime["evidence_scopes"]
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertTrue(any("runtime schema" in error and "evidence_scopes" in error for error in result["errors"]))

    def test_plan_fails_closed_on_auth_and_toolchain(self) -> None:
        result = projectctl.plan(self.project, self.root)
        self.assertFalse(result["ok"])
        joined = "\n".join(result["blockers"])
        self.assertIn("deploy key", joined)
        self.assertIn("Flutter/Android", joined)

    def test_tree_hash_detects_content_drift(self) -> None:
        skill = self.root / "releases" / "core-development" / "0.1.0" / "skills" / "implement" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("hash drift for implement" in item for item in result["errors"]))

    def test_project_overlay_cannot_shadow_core_name(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        overlay = copy.deepcopy(doc["skill_layers"]["project_overlays"][0])
        overlay["name"] = "code-review"
        overlay["path"] = ".hermes-project/skills/code-review/"
        doc["skill_layers"]["project_overlays"] = [overlay]
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("shadows shared skill" in item for item in result["errors"]))

    def test_bundle_unknown_skill_blocks(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        doc["skill_layers"]["bundles"]["implementation"].append("not-a-real-skill")
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("unknown skill not-a-real-skill" in item for item in result["errors"]))

    def test_project_init_without_dry_run_is_refused(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "projectctl.py"), "--project", str(CONTROL_ROOT / "projects/jellyssh/project.yaml"), "project-init"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("requires --dry-run", proc.stderr)

    def test_status_output_cannot_escape_generated_directory(self) -> None:
        with self.assertRaises(projectctl.ControlPlaneError):
            projectctl.write_generated(Path(self.temp.name) / "outside.md", "unsafe")

    def test_generated_write_cleans_temp_file_on_replace_failure(self) -> None:
        original_root = projectctl.CONTROL_ROOT
        projectctl.CONTROL_ROOT = self.root
        generated = self.root / "generated"
        try:
            with mock.patch.object(Path, "replace", side_effect=OSError("fixture")):
                with self.assertRaises(OSError):
                    projectctl.write_generated(generated / "status.md", "content")
            self.assertEqual(list(generated.iterdir()), [])
        finally:
            projectctl.CONTROL_ROOT = original_root

    def test_missing_runtime_returns_structured_block(self) -> None:
        runtime = self.project.parent / "runtime.yaml"
        runtime.unlink()
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["source_digests"]["runtime_manifest"])
        self.assertTrue(any("missing YAML" in item for item in result["errors"]))
        plan = projectctl.plan(self.project, self.root)
        self.assertFalse(plan["ok"])
        self.assertTrue(any("missing YAML" in item for item in plan["blockers"]))

    def test_missing_project_plan_and_status_return_structured_block(self) -> None:
        missing = self.root / "projects" / "missing" / "project.yaml"
        plan = projectctl.plan(missing, self.root)
        self.assertFalse(plan["ok"])
        self.assertTrue(plan["blockers"])
        rendered = projectctl.render_status_json(projectctl.scan(missing, self.root), plan)
        payload = json.loads(rendered)
        self.assertFalse(payload["manifest_ok"])
        self.assertTrue(payload["blockers"])

        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "projectctl.py"), "--project", str(missing), "status", "--format", "json"],
            cwd=CONTROL_ROOT.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["blockers"])

    def test_runtime_profile_skills_must_match_authoritative_bundle(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        doc["skill_layers"]["bundles"]["implementation-runtime"].remove("diagnosing-bugs")
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("runtime skill set does not match authoritative bundle" in item for item in result["errors"]))

    def test_absolute_path_schema_rejects_lexical_traversal(self) -> None:
        import jsonschema

        schema = json.loads((self.root / "schemas" / "runtime-state.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        runtime_path = self.root / "projects" / "jellyssh" / "runtime.yaml"
        for unsafe in ("/../escape", "/..", "/./escape", "/tmp//escape"):
            runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
            runtime["paths"]["implementation_checkout"] = unsafe
            with self.subTest(path=unsafe):
                self.assertTrue(list(validator.iter_errors(runtime)))

    def test_schema_invalid_runtime_returns_structured_block(self) -> None:
        runtime_path = self.root / "projects" / "jellyssh" / "runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["exposed_tools"] = 1
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("runtime schema review_boundary.exposed_tools" in item for item in result["errors"]))

    def test_skill_symlink_is_rejected(self) -> None:
        skill = self.root / "releases/core-development/0.1.0/skills/implement"
        (skill / "escape").symlink_to(Path(self.temp.name))
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("contains a symlink" in item for item in result["errors"]))

    def test_zero_hash_is_rejected_semantically(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        doc["skill_layers"]["core_release"]["bundle_sha256"] = projectctl.ZERO_HASH
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("zero hash" in item for item in result["errors"]))

    def test_unknown_expert_profile_and_bundle_are_rejected(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        doc["expert_policy"]["cross_model_final"]["profile"] = "missing-profile"
        doc["expert_policy"]["cross_model_final"]["bundle"] = "missing-bundle"
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        joined = "\n".join(result["errors"])
        self.assertIn("unknown profile", joined)
        self.assertIn("unknown bundle", joined)

    def test_shared_workspace_and_floating_model_are_rejected(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        doc["profiles"]["reviewer"]["workspace"] = doc["profiles"]["implementation"]["workspace"]
        doc["profiles"]["reviewer"]["model"]["model"] = "deepseek/latest"
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        joined = "\n".join(result["errors"])
        self.assertIn("must not be shared", joined)
        self.assertIn("floating model alias", joined)

    def test_overlay_compatibility_and_duplicates_are_rejected(self) -> None:
        doc = yaml.safe_load(self.project.read_text(encoding="utf-8"))
        overlay = copy.deepcopy(doc["skill_layers"]["project_overlays"][0])
        overlay["tested_against"] = ["unknown-pack@9.9.9"]
        doc["skill_layers"]["project_overlays"].append(overlay)
        self.project.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        result = projectctl.scan(self.project, self.root)
        self.assertFalse(result["ok"])
        joined = "\n".join(result["errors"])
        self.assertIn("duplicate project overlay", joined)
        self.assertIn("tested_against unknown artifact", joined)


    def test_descriptor_metadata_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skills-control-plane"
            shutil.copytree(CONTROL_ROOT, copied)
            descriptor = copied / "packs" / "database-data" / "0.1.0" / "pack.yaml"
            data = yaml.safe_load(descriptor.read_text(encoding="utf-8"))
            data["state"] = "revoked"
            descriptor.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            result = projectctl.scan(copied / "projects" / "jellyssh" / "project.yaml", copied)
        self.assertFalse(result["ok"])
        self.assertTrue(any("governance/provenance manifest drift" in item for item in result["errors"]))

    def test_phase2_runtime_routable_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "skills-control-plane"
            shutil.copytree(CONTROL_ROOT, copied)
            runtime = copied / "projects" / "jellyssh" / "runtime.yaml"
            data = yaml.safe_load(runtime.read_text(encoding="utf-8"))
            data["state"] = "routable"
            runtime.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            result = projectctl.scan(copied / "projects" / "jellyssh" / "project.yaml", copied)
        self.assertFalse(result["ok"])
        self.assertTrue(any("runtime schema state" in item for item in result["errors"]))

    def test_compact_flutter_evidence_semantic_drift_is_rejected(self) -> None:
        evidence_path = self.root / "projects/jellyssh/evidence/flutter-test-compact-summary.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["summary"]["success"] = False
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        runtime_path = self.root / "projects/jellyssh/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["flutter_test_compact_evidence_sha256"] = (
            "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root)

        self.assertFalse(result["ok"])
        self.assertIn("compact Flutter test evidence contract drift", result["errors"])

    def test_compact_flutter_evidence_producer_hash_drift_is_rejected(self) -> None:
        runtime_path = self.root / "projects/jellyssh/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["flutter_test_compact_producer_sha256"][
            "review_boundary.py"
        ] = "sha256:" + "1" * 64
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertIn("compact Flutter test evidence contract drift", result["errors"])

    def test_compact_flutter_evidence_incomplete_protocol_is_rejected(self) -> None:
        evidence_path = self.root / "projects/jellyssh/evidence/flutter-test-compact-summary.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["summary"]["protocol_version"] = "0.1."
        canonical = json.dumps(evidence["summary"], sort_keys=True, separators=(",", ":")) + "\n"
        evidence["output_bytes"] = len(canonical.encode("utf-8"))
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        runtime_path = self.root / "projects/jellyssh/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["flutter_test_compact_evidence_sha256"] = (
            "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertIn("compact Flutter test evidence contract drift", result["errors"])

    def test_compact_flutter_evidence_over_byte_bound_is_rejected(self) -> None:
        evidence_path = self.root / "projects/jellyssh/evidence/flutter-test-compact-summary.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["summary"]["diagnostics"] = ["😀" * 320 for _ in range(8)]
        canonical = json.dumps(
            evidence["summary"], sort_keys=True, separators=(",", ":")
        ) + "\n"
        self.assertGreater(len(canonical.encode("utf-8")), evidence["output_bound_bytes"])
        evidence["output_bytes"] = len(canonical.encode("utf-8"))
        evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        runtime_path = self.root / "projects/jellyssh/runtime.yaml"
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        runtime["review_boundary"]["flutter_test_compact_evidence_sha256"] = (
            "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
        runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

        result = projectctl.scan(self.project, self.root, live_discovery=False)

        self.assertFalse(result["ok"])
        self.assertIn("compact Flutter test evidence contract drift", result["errors"])


class ReviewControlTests(unittest.TestCase):
    def test_review_spec_requires_exact_specification_commit(self) -> None:
        valid = {
            "schema_version": 1,
            "project": "jellyssh",
            "expected_commit": "c" * 40,
            "base_commit": "a" * 40,
            "specification_commit": "b" * 40,
            "specification_path": "docs/spec.md",
            "review_type": "final",
            "paths": ["docs/spec.md"],
            "focus": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(reviewctl.load_spec(path), valid)
            for mutation in (
                {key: value for key, value in valid.items() if key != "specification_commit"},
                {key: value for key, value in valid.items() if key != "specification_path"},
                {**valid, "specification_commit": "not-a-sha"},
                {**valid, "specification_path": "../spec.md"},
                {**valid, "specification_path": "docs/other.md"},
                {**valid, "additional_ref": "d" * 40},
            ):
                path.write_text(json.dumps(mutation), encoding="utf-8")
                with self.assertRaises(reviewctl.ReviewControlError):
                    reviewctl.load_spec(path)

    def test_repository_binding_admits_only_base_specification_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Review Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "review@example.invalid"], check=True)
            commits = []
            for index in range(4):
                (root / "spec.md").write_text(f"version {index}\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(root), "add", "spec.md"], check=True)
                subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", f"commit {index}"], check=True)
                commits.append(
                    subprocess.run(
                        ["git", "-C", str(root), "rev-parse", "HEAD"],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                )
            config = {
                "mcp_servers": {
                    "jellyssh_review": {
                        "env": {
                            "JELLYSSH_REVIEW_ROOT": str(root),
                        }
                    }
                }
            }
            repository = reviewctl._repository_from_config(
                config,
                commits[2],
                commits[0],
                commits[1],
            )
            for ref in commits[:3]:
                self.assertTrue(repository.git_show(ref, "spec.md").startswith("version "))
            subprocess.run(["git", "-C", str(root), "branch", "approved-target-alias", commits[2]], check=True)
            subprocess.run(["git", "-C", str(root), "tag", "approved-spec-alias", commits[1]], check=True)
            for alias in ("approved-target-alias", "approved-spec-alias"):
                with self.assertRaises(ReviewBoundaryError):
                    repository._validate_ref(alias)
            with self.assertRaises(ReviewBoundaryError):
                repository._validate_ref("HEAD")
            subprocess.run(["git", "-C", str(root), "checkout", "-q", "--detach", commits[2]], check=True)
            self.assertEqual(repository._validate_ref("HEAD"), commits[2])
            subprocess.run(["git", "-C", str(root), "checkout", "-q", "--detach", commits[1]], check=True)
            with self.assertRaises(ReviewBoundaryError):
                repository._validate_ref("HEAD")
            subprocess.run(["git", "-C", str(root), "checkout", "-q", "--detach", commits[2]], check=True)
            with self.assertRaises(ReviewBoundaryError):
                repository.git_show(commits[3], "spec.md")
            with self.assertRaises(ReviewBoundaryError):
                reviewctl._repository_from_config(
                    config,
                    commits[1],
                    commits[0],
                    commits[2],
                )
            with self.assertRaises(ReviewBoundaryError):
                ReviewRepository(
                    root,
                    commits[2],
                    allowed_refs=set(commits),
                    base_commit=commits[0],
                    specification_commit=commits[1],
                )

    def test_final_review_requires_sandbox_and_quality_checks(self) -> None:
        self.assertEqual(
            reviewctl._required_checks("final"),
            [
                "sandbox-self-check",
                "head-clean",
                "diff-check",
                "submodule-status",
                "dart-format-check",
                "flutter-analyze",
                "sftp-browser-test",
                "flutter-test",
            ],
        )

    def test_result_contract_rejects_pass_with_high_finding(self) -> None:
        spec = {
            "schema_version": 1,
            "project": "jellyssh",
            "expected_commit": "a" * 40,
            "base_commit": "b" * 40,
            "specification_commit": "b" * 40,
            "specification_path": "docs/spec.md",
            "review_type": "code",
            "paths": [],
            "focus": [],
        }
        result = {
            "verdict": "PASS",
            "project": "jellyssh",
            "expected_commit": "a" * 40,
            "base_commit": "b" * 40,
            "specification_commit": "b" * 40,
            "specification_path": "docs/spec.md",
            "approved_specification_sha256": "sha256:" + "1" * 64,
            "review_type": "code",
            "findings": [{"severity": "high", "path": "lib/a.dart", "line": 1, "summary": "problem"}],
            "checks": ["controller:PASS"],
        }
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl.parse_result(json.dumps(result), spec, "sha256:" + "1" * 64)

    def test_prompt_explicitly_denies_kanban_and_writes(self) -> None:
        spec = {
            "schema_version": 1,
            "project": "jellyssh",
            "expected_commit": "a" * 40,
            "base_commit": "b" * 40,
            "specification_commit": "b" * 40,
            "specification_path": "docs/spec.md",
            "review_type": "final",
            "paths": [],
            "focus": [],
        }
        evidence = {
            "controller": "test",
            "approved_specification": {"sha256": "sha256:" + "1" * 64, "content": "approved"},
        }
        prompt = reviewctl.build_prompt(spec, evidence)
        self.assertIn("Do not claim to edit", prompt)
        self.assertIn("update Kanban", prompt)
        self.assertIn("authoritative-procedure", prompt)
        self.assertIn("jellyssh-controller-evidence-review", prompt)
        self.assertIn(spec["specification_commit"], prompt)
        self.assertIn(spec["specification_path"], prompt)
        self.assertIn(evidence["approved_specification"]["sha256"], prompt)
        other_prompt = reviewctl.build_prompt(
            {**spec, "specification_commit": "c" * 40},
            evidence,
        )
        self.assertNotEqual(prompt, other_prompt)

    def test_mcp_facade_requires_full_base_specification_and_target_shas(self) -> None:
        script = SCRIPTS / "jellyssh_review_mcp.py"
        base_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "JELLYSSH_REVIEW_ROOT": str(CONTROL_ROOT),
            "JELLYSSH_EXPECTED_COMMIT": "a" * 40,
            "JELLYSSH_REVIEW_BASE_COMMIT": "b" * 40,
            "JELLYSSH_REVIEW_SPECIFICATION_COMMIT": "c" * 40,
        }
        for key in (
            "JELLYSSH_EXPECTED_COMMIT",
            "JELLYSSH_REVIEW_BASE_COMMIT",
            "JELLYSSH_REVIEW_SPECIFICATION_COMMIT",
        ):
            env = dict(base_env)
            env.pop(key)
            proc = subprocess.run(
                ["/home/jellybot/.hermes/hermes-agent/venv/bin/python", str(script)],
                env=env,
                text=True,
                capture_output=True,
                timeout=2,
            )
            self.assertNotEqual(proc.returncode, 0, key)
            self.assertIn(key, proc.stderr)

    def test_result_contract_binds_base_and_authenticated_specification_identity(self) -> None:
        spec = {
            "project": "jellyssh",
            "expected_commit": "a" * 40,
            "base_commit": "b" * 40,
            "specification_commit": "c" * 40,
            "specification_path": "docs/spec.md",
            "review_type": "code",
        }
        approved_digest = "sha256:" + "1" * 64
        result = {
            "verdict": "PASS",
            **{key: spec[key] for key in ("project", "expected_commit", "base_commit", "specification_commit", "specification_path", "review_type")},
            "approved_specification_sha256": approved_digest,
            "findings": [],
            "checks": ["controller:PASS"],
        }
        self.assertEqual(reviewctl.parse_result(json.dumps(result), spec, approved_digest)["verdict"], "PASS")
        for key, replacement in (
            ("base_commit", "d" * 40),
            ("specification_commit", "d" * 40),
            ("specification_path", "docs/other.md"),
            ("approved_specification_sha256", "sha256:" + "2" * 64),
        ):
            mutated = {**result, key: replacement}
            with self.assertRaises(reviewctl.ReviewControlError):
                reviewctl.parse_result(json.dumps(mutated), spec, approved_digest)
        missing_path = dict(result)
        del missing_path["specification_path"]
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl.parse_result(json.dumps(missing_path), spec, approved_digest)

    def test_approved_specification_evidence_uses_exact_ref_path_and_bytes(self) -> None:
        approved = "approved immutable specification\n"
        target_mutated = approved + "implementation evidence appended\n"
        calls: list[tuple[str, dict[str, object]]] = []

        async def call(name: str, arguments: dict[str, object]) -> tuple[bool, str]:
            calls.append((name, arguments))
            return True, approved

        spec = {
            "specification_commit": "b" * 40,
            "specification_path": "docs/bugs/BUG-009.md",
        }
        evidence = asyncio.run(reviewctl._approved_specification_evidence(spec, call))
        self.assertEqual(
            calls,
            [("review_git_show", {"ref": "b" * 40, "relative_path": "docs/bugs/BUG-009.md"})],
        )
        self.assertEqual(evidence["content"], approved)
        self.assertEqual(evidence["sha256"], "sha256:" + hashlib.sha256(approved.encode()).hexdigest())
        self.assertNotEqual(evidence["sha256"], "sha256:" + hashlib.sha256(target_mutated.encode()).hexdigest())

        async def empty_call(name: str, arguments: dict[str, object]) -> tuple[bool, str]:
            return True, ""

        with self.assertRaises(reviewctl.ReviewControlError):
            asyncio.run(reviewctl._approved_specification_evidence(spec, empty_call))

    def test_review_procedure_hash_drift_blocks_prompt(self) -> None:
        spec = {
            "review_type": "final",
            "expected_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "base_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "specification_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "specification_path": "app/spec.md",
            "paths": ["app"],
            "focus": [],
        }
        with mock.patch.object(reviewctl, "tree_snapshot", return_value=("sha256:" + "f" * 64, {})):
            with self.assertRaises(reviewctl.ReviewControlError):
                reviewctl.build_prompt(spec, {"controller": "test"})

    def test_review_prompt_uses_the_exact_hash_verified_skill_bytes(self) -> None:
        spec = {
            "schema_version": 1,
            "project": "jellyssh",
            "expected_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "review_type": "final",
            "base_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "specification_commit": "7f612d96bd35fcaa336956d7922a82513d2e9e0d",
            "specification_path": "app/spec.md",
            "paths": ["app"],
            "focus": [],
        }
        project = yaml.safe_load((CONTROL_ROOT / "projects/jellyssh/project.yaml").read_text(encoding="utf-8"))
        name = project["skill_layers"]["bundles"]["final-review"][0]
        overlay = next(item for item in project["skill_layers"]["project_overlays"] if item["name"] == name)
        captured = b"# exact captured procedure bytes\n"
        evidence = {
            "controller": "test",
            "approved_specification": {"sha256": "sha256:" + "1" * 64, "content": "approved"},
        }
        with mock.patch.object(reviewctl, "tree_snapshot", return_value=(overlay["bundle_sha256"], {"SKILL.md": captured})):
            prompt = reviewctl.build_prompt(spec, evidence)
        self.assertIn(captured.decode("utf-8"), prompt)

    def test_mobile_ux_uses_exact_conditional_gemini_model(self) -> None:
        self.assertEqual(
            reviewctl._selected_model({"review_type": "mobile-ux"}),
            "google/gemini-3.1-pro-preview",
        )
        self.assertEqual(
            reviewctl._selected_model({"review_type": "final"}),
            "deepseek/deepseek-v3.2",
        )

    def test_check_output_rejects_dirty_or_mismatched_success(self) -> None:
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl._validate_check_output("head-clean", True, " M changed.txt")
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl._validate_check_output("submodule-status", True, "-deadbeef app/vendor")

    def test_flutter_test_check_requires_exact_compact_terminal_contract(self) -> None:
        valid = {
            "schema_version": 1,
            "check": "flutter-test",
            "reporter": "json",
            "protocol_version": "0.1.1",
            "exit_code": 0,
            "success": True,
            "terminal": "done",
            "passed": 11,
            "failed": 0,
            "skipped": 2,
            "total": 13,
            "diagnostics": [],
        }
        reviewctl._validate_check_output("flutter-test", True, json.dumps(valid))

        invalid = {
            "raw-pass": "PASS",
            "missing-done": json.dumps({**valid, "terminal": "missing"}),
            "nonzero": json.dumps({**valid, "exit_code": 1}),
            "failed": json.dumps({**valid, "failed": 1, "success": False}),
            "contradictory-counts": json.dumps({**valid, "total": 99}),
            "invalid-diagnostic": json.dumps({**valid, "diagnostics": [1]}),
            "oversized-diagnostic": json.dumps({**valid, "diagnostics": ["x" * 321]}),
            "too-many-diagnostics": json.dumps({**valid, "diagnostics": ["warning"] * 9}),
        }
        for name, output in invalid.items():
            with self.subTest(name=name), self.assertRaises(reviewctl.ReviewControlError):
                reviewctl._validate_check_output("flutter-test", True, output)
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl._validate_check_output("flutter-test", False, json.dumps(valid))

    def test_focused_sftp_check_requires_exact_compact_identity(self) -> None:
        valid = {
            "schema_version": 1,
            "check": "sftp-browser-test",
            "reporter": "json",
            "protocol_version": "0.1.1",
            "exit_code": 0,
            "success": True,
            "terminal": "done",
            "passed": 19,
            "failed": 0,
            "skipped": 0,
            "total": 19,
            "diagnostics": [],
        }

        reviewctl._validate_check_output("sftp-browser-test", True, json.dumps(valid))

        for identity in ("flutter-test", "caller-supplied-test"):
            with self.subTest(identity=identity), self.assertRaises(reviewctl.ReviewControlError):
                reviewctl._validate_check_output(
                    "sftp-browser-test",
                    True,
                    json.dumps({**valid, "check": identity}),
                )
        with self.assertRaises(reviewctl.ReviewControlError):
            reviewctl._validate_check_output("sftp-browser-test", False, json.dumps(valid))


class ReviewBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Boundary Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "boundary@example.invalid"], check=True)
        (self.root / "lib").mkdir()
        (self.root / "lib" / "safe.txt").write_text("one\ntwo\n", encoding="utf-8")
        (self.root / ".env").write_text("SECRET=not-real\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "lib/safe.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "initial"], check=True)
        self.head = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.repo = ReviewRepository(
            self.root,
            self.head,
            allowed_refs={self.head},
            base_commit=self.head,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metadata_is_exact_and_declares_no_write_tools(self) -> None:
        meta = self.repo.metadata()
        self.assertEqual(meta["head"], self.head)
        self.assertTrue(meta["expected_commit_matches"])
        self.assertFalse(meta["write_tools_exposed"])

    def test_bounded_read_and_list(self) -> None:
        self.assertEqual(self.repo.read_text("lib/safe.txt"), "1|one\n2|two")
        self.assertEqual(self.repo.list_files("*.txt"), ["lib/safe.txt"])

    def test_path_escape_git_metadata_secret_and_symlink_escape_are_denied(self) -> None:
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (self.root / "link.txt").symlink_to(outside)
        for candidate in ("../outside.txt", ".git/config", ".env", "link.txt"):
            with self.subTest(candidate=candidate), self.assertRaises(ReviewBoundaryError):
                self.repo.read_text(candidate)

    def test_only_allowlisted_checks_run(self) -> None:
        # The deliberately untracked credential-like fixture must keep the
        # checkout non-clean even though its contents are unreadable.
        self.assertIn(".env", self.repo.run_check("head-clean"))
        with self.assertRaises(ReviewBoundaryError):
            self.repo.run_check("shell")

    def test_diff_uses_validated_refs_and_paths(self) -> None:
        (self.root / "lib" / "safe.txt").write_text("one\nchanged\n", encoding="utf-8")
        diff = self.repo.git_diff(self.head, "HEAD", ["lib/safe.txt"])
        self.assertEqual(diff, "")
        with self.assertRaises(ReviewBoundaryError):
            self.repo.git_diff("HEAD;touch /tmp/nope")
        with self.assertRaises(ReviewBoundaryError):
            self.repo.git_diff("HEAD", paths=["../outside"])
        with self.assertRaises(ReviewBoundaryError):
            self.repo.git_diff("HEAD", paths=[])
        with self.assertRaises(ReviewBoundaryError):
            self.repo.git_diff("HEAD", paths=[".env"])
        with self.assertRaises(ReviewBoundaryError):
            self.repo.git_show("HEAD", ".env")
        self.assertEqual(self.repo.validate_tracked_paths(self.head, ["lib/safe.txt"]), ["lib/safe.txt"])
        with self.assertRaises(ReviewBoundaryError):
            self.repo.validate_tracked_paths(self.head, ["lib"])
        with self.assertRaises(ReviewBoundaryError):
            self.repo.validate_tracked_paths(self.head, ["missing"])

    def test_diff_check_covers_exact_base_to_target_range(self) -> None:
        (self.root / "middle.txt").write_text("trailing whitespace   \n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "middle.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "middle"], check=True)
        (self.root / "target.txt").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "target.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "target"], check=True)
        target = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        repository = ReviewRepository(
            self.root,
            target,
            allowed_refs={self.head, target},
            base_commit=self.head,
        )
        with self.assertRaises(ReviewBoundaryError):
            repository.run_check("diff-check")

    def test_parent_directory_diff_denies_credential_like_child(self) -> None:
        (self.root / "app").mkdir()
        (self.root / "app" / "key.properties").write_text("storePassword=TOP_SECRET_PROBE\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "app/key.properties"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "secret fixture"], check=True)
        target = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        repository = ReviewRepository(self.root, target, allowed_refs={self.head, target})
        with self.assertRaises(ReviewBoundaryError):
            repository.git_diff(self.head, target, ["app"])

    def test_materializer_ignores_export_ignore_and_rejects_symlinks(self) -> None:
        (self.root / ".gitattributes").write_text("hidden.dart export-ignore\n", encoding="utf-8")
        (self.root / "hidden.dart").write_text("void broken( {\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitattributes", "hidden.dart"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "export fixture"], check=True)
        export_commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        destination = Path(self.temp.name) / "materialized"
        subprocess.run(
            [sys.executable, "-c", review_boundary._MATERIALIZE_COMMIT_CODE, str(self.root), export_commit, str(destination)],
            check=True,
        )
        self.assertEqual((destination / "hidden.dart").read_text(encoding="utf-8"), "void broken( {\n")

        link = self.root / "unsafe-link"
        link.symlink_to("/tmp/outside")
        subprocess.run(["git", "-C", str(self.root), "add", "unsafe-link"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "symlink fixture"], check=True)
        symlink_commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        rejected = subprocess.run(
            [sys.executable, "-c", review_boundary._MATERIALIZE_COMMIT_CODE, str(self.root), symlink_commit, str(Path(self.temp.name) / "rejected")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(rejected.returncode, 0)

    def test_project_state_hash_rejects_symlinks(self) -> None:
        state = Path(self.temp.name) / "state"
        state.mkdir()
        (state / "regular").write_text("ok", encoding="utf-8")
        ok = subprocess.run(
            [sys.executable, "-c", review_boundary._TREE_HASH_CODE, str(state)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(ok.returncode, 0)
        self.assertTrue(ok.stdout.startswith("sha256:"))
        (state / "link").symlink_to("regular")
        blocked = subprocess.run(
            [sys.executable, "-c", review_boundary._TREE_HASH_CODE, str(state)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertNotEqual(blocked.returncode, 0)

    def test_secret_names_and_pathspec_magic_are_denied(self) -> None:
        for denied in (".env.local", ".npmrc", "android/key.properties", "release.jks", ":(glob)app/*"):
            with self.subTest(candidate=denied), self.assertRaises(ReviewBoundaryError):
                self.repo.read_text(denied)

    def test_historical_credential_blob_is_denied(self) -> None:
        secret = self.root / ".env.local"
        secret.write_text("TOKEN=not-a-real-token\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", ".env.local"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "credential fixture"], check=True)
        historical = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        secret.unlink()
        subprocess.run(["git", "-C", str(self.root), "add", "-u"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "remove fixture"], check=True)
        current = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        repository = ReviewRepository(self.root, current)
        with self.assertRaises(ReviewBoundaryError):
            repository.git_show(historical, ".env.local")

    def test_undeclared_historical_ref_is_denied_for_innocent_path(self) -> None:
        historical = self.head
        tracked = self.root / "tracked.txt"
        tracked.write_text("new accepted content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "new target"], check=True)
        current = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        repository = ReviewRepository(self.root, current)
        with self.assertRaises(ReviewBoundaryError):
            repository.git_show(historical, "tracked.txt")

    def test_tracked_symlink_blob_is_denied(self) -> None:
        link = self.root / "lib" / "linked.txt"
        link.symlink_to("safe.txt")
        subprocess.run(["git", "-C", str(self.root), "add", "lib/linked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "symlink fixture"], check=True)
        head = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        repository = ReviewRepository(self.root, head)
        with self.assertRaises(ReviewBoundaryError):
            repository.read_text("lib/linked.txt")

    def test_read_uses_exact_commit_not_modified_worktree(self) -> None:
        tracked = self.root / "tracked.txt"
        tracked.write_text("accepted\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", "tracked"], check=True)
        head = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        tracked.write_text("changed-after-preflight\n", encoding="utf-8")
        repository = ReviewRepository(self.root, head)
        result = repository.read_text("tracked.txt")
        self.assertIn("accepted", result)
        self.assertNotIn("changed-after-preflight", result)

    def test_git_fsmonitor_config_cannot_execute(self) -> None:
        marker = self.root / "fsmonitor-ran"
        hook = self.root / "fsmonitor.sh"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
        hook.chmod(0o755)
        subprocess.run(["git", "-C", str(self.root), "config", "core.fsmonitor", str(hook)], check=True)
        self.repo.metadata()
        self.assertFalse(marker.exists())

    def test_reviewer_finding_must_stay_in_requested_scope(self) -> None:
        profile = Path(self.temp.name) / "profile"
        profile.mkdir()
        (profile / "config.yaml").write_text(
            yaml.safe_dump({"mcp_servers": {"jellyssh_review": {"env": {"JELLYSSH_REVIEW_ROOT": str(self.root)}}}}),
            encoding="utf-8",
        )
        spec = {
            "expected_commit": self.head,
            "base_commit": self.head,
            "specification_commit": self.head,
            "specification_path": "lib/spec.md",
            "paths": ["lib"],
        }
        result = {"findings": [{"path": "outside/file.txt"}]}
        with self.assertRaises(reviewctl.ReviewControlError):
            config = yaml.safe_load((profile / "config.yaml").read_text(encoding="utf-8"))
            reviewctl.validate_result_scope(result, spec, config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
