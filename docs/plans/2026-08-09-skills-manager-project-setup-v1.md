# Skills Manager and Project Setup V1 implementation plan

> **For Hermes:** Execute this plan in vertical TDD slices. Preserve the user's review rule: rerun only a failed review axis unless implementation scope changes fundamentally.

**Goal:** Build a reusable, approval-bound project setup and manual skill-lifecycle manager on top of the accepted Phase 2 Skill Control Plane.

**Architecture:** Add a generic `managerlib.py` deep module whose interface produces, verifies, applies and rolls back immutable typed plans through an injected runtime adapter. `managerctl.py` is a thin CLI. Existing JellySSH routing validation remains in `projectctl.py`; generic schemas and fleet/lifecycle commands do not weaken its controls.

**Tech stack:** Python 3.11 standard library, PyYAML, jsonschema, Git CLI, Hermes CLI adapter, unittest.

---

### Task 1: Define generic schemas and canonical plan hashing

**Files:**
- Create: `skills-control-plane/schemas/project-setup-request.schema.json`
- Create: `skills-control-plane/schemas/manager-plan.schema.json`
- Create: `skills-control-plane/schemas/manager-journal.schema.json`
- Create: `skills-control-plane/scripts/managerlib.py`
- Create: `skills-control-plane/tests/test_managerctl.py`

**Steps:**
1. Write failing tests for schema rejection, canonical plan hashing, traversal, secret-like keys and unknown actions.
2. Implement schema loading, canonical JSON hashing and typed dataclasses/results.
3. Run the focused tests and existing control-plane tests.

### Task 2: Implement project discovery and immutable setup planning

**Files:**
- Modify: `skills-control-plane/scripts/managerlib.py`
- Create: `skills-control-plane/scripts/managerctl.py`
- Modify: `skills-control-plane/tests/test_managerctl.py`

**Steps:**
1. Test a temporary clean Git repository and setup request through the public `project plan` seam.
2. Test dirty/wrong-remote/wrong-commit/unknown-profile and non-absolute-workspace blockers.
3. Generate sorted typed actions, preconditions, rollbacks and a stable plan digest.
4. Add CLI JSON output and atomic plan writing.

### Task 3: Implement approval-bound project apply and rollback journals

**Files:**
- Modify: `skills-control-plane/scripts/managerlib.py`
- Modify: `skills-control-plane/scripts/managerctl.py`
- Modify: `skills-control-plane/tests/test_managerctl.py`

**Steps:**
1. Define an injected runtime adapter and fake adapter used by tests.
2. Test wrong approval, precondition drift and unsupported actions block before mutation.
3. Implement atomic managed-file writes, exact no-op detection and durable journals.
4. Implement allowlisted Hermes CLI profile/board adapters without shell interpolation.
5. Test partial failure stops, journal durability and explicit approval-bound rollback.

### Task 4: Implement project doctor, reconciliation and fleet views

**Files:**
- Modify: `skills-control-plane/scripts/managerlib.py`
- Modify: `skills-control-plane/scripts/managerctl.py`
- Modify: `skills-control-plane/tests/test_managerctl.py`
- Create: `skills-control-plane/generated/fleet-status.json`
- Create: `skills-control-plane/generated/fleet-status.md`

**Steps:**
1. Test GREEN/BLUE/AMBER/RED/GREY classifications through the doctor interface.
2. Compare repository, manifests, profiles, skills, workspaces and board observations.
3. Make reconciliation emit a plan only.
4. Generate deterministic fleet JSON/Markdown and verify repeated output is byte-identical.

### Task 5: Implement manual skill lifecycle planning and promotion

**Files:**
- Modify: `skills-control-plane/scripts/managerlib.py`
- Modify: `skills-control-plane/scripts/managerctl.py`
- Modify: `skills-control-plane/tests/test_managerctl.py`

**Steps:**
1. Test deterministic inventory across catalogue, releases, packs, overlays and projects.
2. Test candidate versions cannot overwrite immutable releases or use floating references.
3. Generate impacted-project and overlay-compatibility plans.
4. Require hash-bound compatibility and canary evidence before promotion.
5. Apply only exact approved profile materializations through the adapter and retain rollback state.
6. Prove project-only overlays cannot target other projects.

### Task 6: Generalize project schema constraints without weakening JellySSH

**Files:**
- Modify: `skills-control-plane/schemas/project-skill-profile.schema.json`
- Modify: `skills-control-plane/scripts/projectctl.py`
- Modify: `skills-control-plane/tests/test_projectctl.py`
- Modify: `skills-control-plane/projects/jellyssh/project.yaml` only if required by schema migration

**Steps:**
1. Add tests for a second generic project manifest and JellySSH regression.
2. Replace schema constants with generic patterns and cross-field semantic checks.
3. Move JellySSH-only model/UI/host rules into its project constraints/adapter.
4. Run both test suites and scan/verify/audit JellySSH.

### Task 7: Document operation, verification and rollback

**Files:**
- Modify: `skills-control-plane/README.md`
- Modify: `docs/operations/multi-agent-development/skill-control-plane-and-project-initialization.md`
- Create: `docs/operations/multi-agent-development/skills-manager-project-setup-runbook.md`
- Create: `docs/reports/skills-manager-project-setup-v1-2026-08-09.md`

**Steps:**
1. Document plan/apply separation, approval tokens, safe sample workflow and status meanings.
2. Document candidate/update/canary/promotion/rollback lifecycle.
3. Document failure recovery and prove no live runtime changes are needed for acceptance tests.
4. Validate links, YAML/JSON, Python compilation, tests and `git diff --check`.

### Task 8: Review and publication

**Steps:**
1. Freeze the stable candidate after generated projections settle.
2. Run specification compliance once.
3. Run standards/code-quality review once; remediate and rerun only failed axes.
4. Credential-scan changed files.
5. Commit and push `feat/skills-manager-project-setup`.
6. Stop before PR, merge, live project apply, scheduled audit, Desktop plugin or JellySSH development card.
