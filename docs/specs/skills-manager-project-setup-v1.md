# Skills Manager and Project Setup V1 specification

> **Status:** Approved for implementation by operator decision on 2026-08-09
>
> **Phase:** 2.5 — before the first JellySSH development card

## Goal

Turn the Phase 2 JellySSH-specific Skill Control Plane foundation into a reusable, fail-closed project setup and manual skill-lifecycle manager for Hermes projects.

## Governing rules

1. Git YAML/JSON is authoritative; generated Markdown/JSON is a projection.
2. Discovery and planning are read-only.
3. Every mutation requires an immutable plan, exact precondition hashes, and the operator to supply that plan's SHA-256 approval token.
4. Setup and generated/runtime artifacts remain separate.
5. Apply is idempotent: exact existing state is a no-op; conflicting or unknown state blocks.
6. No secret value may appear in requests, plans, manifests, reports, logs, or command arguments.
7. No generic profile/model/bank/skill fallback is allowed.
8. Candidate skill releases and project setups remain non-routable until separately verified and promoted.
9. This phase creates no JellySSH development card and performs no product implementation.
10. Automatic promotion, scheduled audit, and write-capable Desktop controls remain out of scope.

## Public command seams

One CLI, `skills-control-plane/scripts/managerctl.py`, exposes four modules:

```text
managerctl project plan       REQUEST -> immutable action plan
managerctl project apply      PLAN + exact approval token -> setup result + rollback journal
managerctl project doctor     desired project + observed runtime -> health report
managerctl project reconcile  doctor report -> immutable correction plan

managerctl skill inventory    catalogue/projects -> inventory report
managerctl skill candidate-plan source + provenance -> immutable non-routable candidate plan
managerctl skill candidate    approved candidate plan -> candidate journal
managerctl skill impact       candidate + fleet authority -> impacted-project report
managerctl skill canary-plan  candidate + compatibility evidence -> one-profile canary plan
managerctl skill canary       approved canary plan -> canary journal
managerctl skill update-plan  committed candidate + evidence -> impacted-project promotion plan
managerctl skill promote      approved plan -> controlled materialization result + rollback journal
managerctl skill rollback     prior journal + approval token -> exact rollback result

managerctl fleet status       all registered projects -> JSON/Markdown fleet projection
managerctl verify             schemas, manifests, plans, journals and projections
```

The interface returns structured JSON. Human-readable output is a projection of that JSON.

## Project setup request

A request contains no credentials and declares:

- project slug, display name, repository path, exact remote, default branch and expected commit;
- control-plane manifest location and project-local contract location;
- coordinator, implementation and reviewer profile names and approved baselines;
- exact provider/model/fallback, tool, memory-bank and retention declarations;
- implementation and review workspaces;
- exact core release, capability packs, overlays and task bundles;
- expert triggers and review bindings;
- empty board slug/name/default workdir and conservative limits;
- which runtime effects are requested.

## Project setup plan

A plan is canonical JSON containing:

- schema version and operation kind;
- request digest and authority-source digests;
- discovered repository/profile/board preconditions;
- a sorted list of typed allowlisted actions;
- a sorted list of blockers and decisions;
- rollback actions for every mutation;
- `plan_sha256`, computed over the plan with that field omitted.

Allowlisted project actions are:

- write a new control-plane project manifest or exact update to a known managed manifest;
- write/update the project-local `.hermes-project/project.yaml` contract;
- create an isolated Hermes profile from an explicitly named baseline;
- set allowlisted non-secret profile configuration keys;
- materialize exact hash-verified skills into a named profile;
- create an empty board with an absolute default workdir;
- write generated setup/runtime evidence.

Arbitrary commands, shell fragments, environment assignments, secret files, cards, branches, commits, pushes, deployments, and privilege operations are not valid plan actions.

## Apply gate

`project apply` requires:

```text
--plan /absolute/path/to/plan.json
--approve sha256:<exact-plan-hash>
```

Before the first mutation it must:

1. validate the plan schema and recompute its digest;
2. reject symlinks/non-regular files and traversal;
3. recheck every filesystem, repository, profile, board and authority precondition;
4. create a private backup directory and rollback journal;
5. prove every requested runtime action has an implementation adapter.

The digest token protects against accidental, modified and stale application. It does not authenticate a human against another process already running as the same UID; operator procedure must ensure the digest is inspected and supplied personally. The manager does not mint or refresh its own approval.

Apply writes each journal entry durably after the corresponding action. On failure it stops; it never continues to later actions. Rollback is explicit and approval-bound. Existing exact state is recorded as `noop`.

## Project doctor and reconciliation

Doctor is non-mutating and reports:

- manifest/schema and hash integrity;
- repository remote/branch/commit/cleanliness;
- desired versus active profile/model/tool/bank/retention state;
- desired versus active skill names/hashes and shadowing;
- workspace separation/accessibility;
- board existence/default workdir/task counts;
- last compatibility/canary/route evidence;
- state: `GREEN`, `BLUE`, `AMBER`, `RED`, or `GREY`.

Reconcile only emits a new immutable action plan. It never applies automatically.

## Skill lifecycle

The manager supports manual, reviewed lifecycle stages:

```text
inventory -> candidate -> impact -> compatibility evidence -> canary evidence
          -> approval-bound promotion -> fresh-session verification -> rollback retention
```

A candidate may not modify an immutable release directory in place. It must have a new semantic version, deterministic bundle and descriptor hashes, provenance, compatibility declaration, and non-routable state under `candidates/`. It is created and journaled separately, then committed to Git before impact/canary/promotion planning.

Promotion blocks unless:

- every impacted project is listed;
- overlay compatibility is explicit;
- required compatibility and canary evidence is present and hash-bound;
- target profiles are exact and backed up;
- the operator supplies the promotion plan hash;
- previous release/profile materialization remains available for rollback.

Project-only overlays may target only their declared project profiles. Core/pack promotion produces a fleet impact report.

## Fleet view

Generated JSON and Markdown include:

- one row per project with core, packs, overlays, experts and health state;
- skill-to-project/profile matrix;
- pending candidates and impacted projects;
- drift/update/rebase inbox;
- last verification, promotion and rollback references;
- project setup/doctor status.

The fleet view cannot mutate state.

## Test seams

Tests exercise public command modules through temporary repositories and a fake Hermes adapter:

1. request -> deterministic plan;
2. changed precondition -> apply BLOCK before mutation;
3. wrong approval hash -> BLOCK;
4. exact apply -> expected artifacts and journal;
5. second apply -> no-op;
6. partial adapter failure -> durable stop journal and no later actions;
7. rollback -> exact prior bytes/state;
8. traversal/symlink/secret/arbitrary-command inputs -> BLOCK;
9. doctor detects missing, extra, shadowed and drifted skills;
10. promotion blocks without impact/compatibility/canary evidence;
11. project-only promotion cannot affect another project;
12. fleet projections are deterministic and derived from authority;
13. existing JellySSH Phase 2 tests remain green.

## Acceptance criteria

- [ ] Generic schemas contain no JellySSH-only constants.
- [ ] Project plan/apply/doctor/reconcile commands work in isolated tests.
- [ ] Skill inventory/update-plan/promote/rollback commands work in isolated tests.
- [ ] Fleet JSON and Markdown are deterministic.
- [ ] No test writes to live `~/.hermes`, live boards, or non-temporary profiles.
- [ ] Existing JellySSH manifests and 43 tests still pass.
- [ ] New negative tests prove approval, precondition, scope and rollback controls.
- [ ] Operating and rollback documentation is complete.
- [ ] Independent specification and code-quality review pass.
- [ ] Feature branch is committed and pushed; no PR/merge without a separate operator decision.
