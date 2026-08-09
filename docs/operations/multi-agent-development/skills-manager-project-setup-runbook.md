# Skills Manager and Project Setup runbook

## Purpose

Use this runbook to register a project, create its non-executable Hermes setup, inspect drift, plan a skill update, or roll back an approved manager operation.

The operator controls every mutation. Never paste credentials into a request or plan.

## 1. Prepare project authority

Prerequisites:

- the repository is a clean Git checkout on the intended branch and exact commit;
- `origin` is the intended authoritative remote;
- coordinator, implementation and reviewer workspaces are absolute and separate;
- every provider/model is an exact ID with fallback `block`;
- every profile has an exact Hindsight bank and retention policy in the embedded project manifest;
- core release, packs, overlays and bundles have exact nonzero hashes;
- expert triggers and final-review handoff are declared;
- the board is setup-only and has no development cards;
- credentials already exist outside Git-backed requests.

Copy the example:

```bash
cp skills-control-plane/templates/project-setup-request.example.yaml \
  /private/work/path/<project>-setup.yaml
vim /private/work/path/<project>-setup.yaml
```

Keep the completed request outside the repository if it contains host-specific paths. It must still contain no secret values.

## 2. Read-only plan

```bash
python3 skills-control-plane/scripts/managerctl.py project plan \
  --request /private/work/path/<project>-setup.yaml \
  --output /private/work/path/<project>-setup.plan.json
```

Expected outcomes:

- exit `0`: schema, repository and observed preconditions are plan-ready;
- exit `1`: a valid plan was emitted but has explicit blockers;
- exit `2`: malformed/unsafe input or CLI failure; no plan may be applied.

Review:

- `created_from.request_sha256` and `control_commit`;
- every precondition;
- every typed action and rollback declaration;
- `blockers` is empty;
- no unexpected profile, board, file, skill or path;
- `plan_sha256` is nonzero.

A changed request or environment requires a new plan.

## 3. Apply setup

Apply only after reviewing the exact plan:

```bash
install -d -m 700 /private/work/path/<project>-journals
python3 skills-control-plane/scripts/managerctl.py project apply \
  --plan /private/work/path/<project>-setup.plan.json \
  --approve sha256:<plan_sha256> \
  --journal-dir /private/work/path/<project>-journals
```

The manager revalidates the plan and all preconditions before its first action. It then writes a private journal after each action.

A failure stops the sequence. Do not rerun blindly; inspect the failed journal and current state first.

## 4. Verify setup

```bash
python3 skills-control-plane/scripts/managerctl.py project doctor \
  --request /private/work/path/<project>-setup.yaml \
  --output /private/work/path/<project>-doctor.report.json
python3 skills-control-plane/scripts/managerctl.py verify
```

`doctor` verifies repository authority, exact managed files, requested profiles and settings, and an exact empty board. It records the setup request path and digest for later reconciliation. `GREEN` means setup matches desired state; it does not mean development is authorized.

Commit project-local `.hermes-project/project.yaml` separately in that project's repository after review. Commit control-plane authority through the normal operations-repository review path.

Start fresh Hermes sessions after profile changes.

## 5. Reconcile drift

```bash
python3 skills-control-plane/scripts/managerctl.py project reconcile \
  --doctor-report /private/work/path/<project>-doctor.report.json \
  --output /private/work/path/<project>-reconcile.plan.json
```

This consumes the doctor report, rechecks the original setup request digest, and remains plan-only. Review and apply it using the same exact-hash process. Unmanaged repository changes, non-empty/drifted boards, missing baselines or conflicting managed files block.

## 6. Inventory skills and projects

```bash
python3 skills-control-plane/scripts/managerctl.py skill inventory \
  --output /private/work/path/skill-inventory.json
python3 skills-control-plane/scripts/managerctl.py fleet status --format markdown \
  --output /private/work/path/fleet-status.md
```

The inventory includes catalogue and project references. Fleet status is a projection and may truthfully return exit `1` while any project reports `RED`.

## 7. Prepare, register and assess a shared skill candidate

Never modify an immutable release or pack in place. Create a source directory with a new semantic version, descriptor, exact skill directories, provenance and compatibility metadata, and no symlinks or special files.

Create `skill-candidate-request.yaml`, then plan and apply only the non-routable candidate:

```bash
python3 skills-control-plane/scripts/managerctl.py skill candidate-plan \
  --request /private/work/path/skill-candidate-request.yaml \
  --output /private/work/path/skill-candidate.plan.json
python3 skills-control-plane/scripts/managerctl.py skill candidate \
  --plan /private/work/path/skill-candidate.plan.json \
  --approve sha256:<plan_sha256> \
  --journal-dir /private/work/path/skill-candidate-journal
```

Review and commit `skills-control-plane/candidates/...` to Git. Candidate apply does not update the active catalogue or a profile. Calculate the complete impact projection:

```bash
python3 skills-control-plane/scripts/managerctl.py skill impact \
  --request /private/work/path/skill-candidate-request.yaml \
  --output /private/work/path/skill-impact.json
```

After exact compatibility evidence passes, create a one-profile canary request and run an independently approved canary plan:

```bash
python3 skills-control-plane/scripts/managerctl.py skill canary-plan \
  --request /private/work/path/skill-canary-request.yaml \
  --output /private/work/path/skill-canary.plan.json
python3 skills-control-plane/scripts/managerctl.py skill canary \
  --plan /private/work/path/skill-canary.plan.json \
  --approve sha256:<plan_sha256> \
  --journal-dir /private/work/path/skill-canary-journal
```

A file copy is not canary acceptance. Start a fresh session, run the declared checks, and produce structured `PASS` evidence bound to the exact candidate hashes, project and control commit.

## 8. Promote and verify a skill update

Prepare a promotion request containing the exact committed candidate path, derived impacted projects, one passing compatibility record per impacted project, passing canary evidence, complete updated project manifests, and exact project-owned profile/skill targets.

```bash
python3 skills-control-plane/scripts/managerctl.py skill update-plan \
  --request /private/work/path/skill-update-request.yaml \
  --output /private/work/path/skill-promotion.plan.json
python3 skills-control-plane/scripts/managerctl.py skill promote \
  --plan /private/work/path/skill-promotion.plan.json \
  --approve sha256:<plan_sha256> \
  --journal-dir /private/work/path/skill-promotion-journal
```

Promotion blocks on uncommitted or changed candidates, stale versions, destination collisions, incomplete impact, blocking/mismatched evidence, unowned profiles, source hash drift or manifests that do not pin the candidate.

After promotion:

1. run `managerctl verify`;
2. run `project doctor` for every impacted project;
3. start fresh profile sessions;
4. perform route preflight and required expert/final reviews;
5. record acceptance separately.

Promotion does not automatically dispatch work.

## 9. Rollback

Use the completed apply journal's exact `journal_sha256`. Use `project rollback` for setup/reconcile journals and `skill rollback` for candidate/canary/promotion journals:

```bash
python3 skills-control-plane/scripts/managerctl.py skill rollback \
  --journal /private/work/path/<journal>/apply-....json \
  --approve sha256:<journal_sha256> \
  --journal-dir /private/work/path/<rollback-journal>
```

Rollback proceeds in reverse action order and stops on drift. It restores previous managed file/tree bytes, unsets/restores profile settings, deletes profiles created by the operation, and archives boards created by the operation.

If rollback blocks:

- do not manually overwrite current state;
- preserve the apply and rollback journals;
- identify the changed target;
- decide whether to retain current state or produce a separately reviewed repair plan.

## 10. Disable/remove the capability

The manager is not a service and creates no cron job. To disable it, stop invoking `managerctl.py`.

To remove a planned but unapplied setup, delete only its private request/plan files.

To reverse an applied operation, use the approval-bound rollback. Do not remove immutable releases or project authority manually while any project references them.

The existing JellySSH `projectctl.py` route remains independently usable if the generic manager is not invoked.
