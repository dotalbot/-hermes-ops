# Skill Control Plane and Skills Manager

This directory is the Git-backed authority for governed Hermes project setup and manual skill lifecycle management. JellySSH remains the first registered pilot. The manager does not make a project routable, create development cards, or promote mutable upstream content automatically.

## Authority layers

- `catalog.yaml` — immutable releases, capability packs and registered projects.
- `releases/` — reviewed, immutable shared skill releases.
- `packs/` — reviewed, immutable optional capability packs.
- `candidates/` — immutable, non-routable candidate bytes awaiting evidence-bound promotion.
- `projects/<slug>/project.yaml` — exact desired skill/profile/model/workspace/expert policy.
- `projects/<slug>/runtime.yaml` — schema-bound, section-scoped runtime authority. JellySSH freezes setup/paths/profiles/toolchain/board/rollback sections at the Phase 2 bootstrap cut while allowing the separately declared `review_boundary` section to evolve only with exact-hash-reviewed control-plane changes. It is not a claim about today's task count, checkout HEADs, or MCP target.
- `projects/<slug>/contracts/` or another reviewed path — short-lived, schema-validated work-item contracts; never a replacement for the approved product specification.
- `projects/<slug>/overlays/` — project-only skills; never silently promoted globally.
- `schemas/` — project, setup-request, plan, journal, lifecycle and runtime schemas.
- `templates/` — non-secret setup inputs that must be completed before planning.
- `generated/` — derived fleet/project projections; never authority.

JellySSH-specific review routing remains in `projectctl.py`, `reviewctl.py`, `review_boundary.py`, and `jellyssh_review_mcp.py`. `governancectl.py` provides the separately authenticated parent-context, timing, canonical-Kanban review, and acceptance publication boundary. Generic setup and maintenance are isolated in `managerlib.py` behind the thin `managerctl.py` CLI.

## Safety model

Every manager mutation uses the same sequence:

```text
request -> read-only discovery -> immutable JSON plan -> exact precondition recheck
        -> operator supplies sha256:<plan-hash> -> typed allowlisted actions
        -> durable journal after every action -> explicit hash-approved rollback
```

Important properties:

- planning, doctor, inventory and fleet status are read-only;
- apply accepts no shell command or environment fragment;
- plans cannot contain secret-shaped keys or values;
- full provider/model/fallback, bank, workspace, skills and review boundaries are declared before setup;
- profile baselines and empty boards are verified before mutation;
- setup-owned profiles and boards carry project-scoped ownership markers; unowned name collisions block;
- requested profile bundles are resolved from exact release/pack/overlay descriptors and hash-materialized during setup;
- unrelated repository changes, configuration drift, symlinks, traversal and unknown object types block;
- exact existing state becomes `noop`; conflicting state blocks;
- candidate releases require a new semantic version and exact tree/descriptor hashes;
- skill promotion requires complete impacted-project declarations plus hash-bound compatibility and canary evidence;
- previous managed bytes/trees and created resources are represented in the rollback journal;
- project setup and skill promotion never authorize implementation, cards, commits, PRs, merges, deployment, signing, sideloading, secrets or `sudo`.

The SHA approval token is an anti-accident and stale-plan gate, not a cryptographic trust boundary against another process already running as the same UID. The operator must inspect the immutable plan and personally provide its exact digest. The manager never discovers or refreshes approval automatically.

## Generic project setup

Start from:

```text
skills-control-plane/templates/project-setup-request.example.yaml
```

Replace every example repository, commit, path, profile, model, bank, bundle and trigger declaration. The file must contain no credentials.

Generate a plan:

```bash
python3 skills-control-plane/scripts/managerctl.py project plan \
  --request /absolute/path/to/project-setup.yaml \
  --output /absolute/path/to/project-setup.plan.json
```

Inspect the complete plan and its `blockers`. Applying requires the exact printed `plan_sha256`:

```bash
python3 skills-control-plane/scripts/managerctl.py project apply \
  --plan /absolute/path/to/project-setup.plan.json \
  --approve sha256:<exact-plan-hash> \
  --journal-dir /absolute/private/path/to/setup-journal
```

Run health and reconciliation planning:

```bash
python3 skills-control-plane/scripts/managerctl.py project doctor \
  --request /absolute/path/to/project-setup.yaml \
  --output /absolute/path/to/doctor.report.json

python3 skills-control-plane/scripts/managerctl.py project reconcile \
  --doctor-report /absolute/path/to/doctor.report.json \
  --output /absolute/path/to/reconcile.plan.json
```

`doctor` records the exact setup request path and digest. `reconcile` consumes that doctor report, rechecks the request digest, and writes a plan only. It never applies automatically.

Rollback a completed apply journal:

```bash
python3 skills-control-plane/scripts/managerctl.py project rollback \
  --journal /absolute/path/to/apply-....json \
  --approve sha256:<exact-journal-hash> \
  --journal-dir /absolute/private/path/to/rollback-journal
```

Rollback blocks if any managed result has changed since apply.

## Skill lifecycle

Inventory current authority, create a non-routable candidate plan and calculate impact:

```bash
python3 skills-control-plane/scripts/managerctl.py skill inventory

python3 skills-control-plane/scripts/managerctl.py skill candidate-plan \
  --request /absolute/path/to/skill-candidate.yaml \
  --output /absolute/path/to/skill-candidate.plan.json

python3 skills-control-plane/scripts/managerctl.py skill candidate \
  --plan /absolute/path/to/skill-candidate.plan.json \
  --approve sha256:<exact-plan-hash> \
  --journal-dir /absolute/private/path/to/candidate-journal

python3 skills-control-plane/scripts/managerctl.py skill impact \
  --request /absolute/path/to/skill-candidate.yaml \
  --output /absolute/path/to/skill-impact.json
```

After approving and applying the candidate plan, commit the candidate authority bytes for review. The candidate is not added to the active catalogue and does not affect profiles.

Plan an explicit canary rollout only after exact compatibility evidence exists:

```bash
python3 skills-control-plane/scripts/managerctl.py skill canary-plan \
  --request /absolute/path/to/skill-canary.yaml \
  --output /absolute/path/to/skill-canary.plan.json

python3 skills-control-plane/scripts/managerctl.py skill canary \
  --plan /absolute/path/to/skill-canary.plan.json \
  --approve sha256:<exact-plan-hash> \
  --journal-dir /absolute/private/path/to/canary-journal
```

A later promotion request declares:

- the exact committed candidate authority path and hashes;
- the exact derived impacted-project set;
- one hash-verified compatibility record per impacted project;
- a hash-verified canary record;
- complete updated project manifests pinning the candidate;
- exact project/profile/skill materialization targets.

Plan, inspect and promote:

```bash
python3 skills-control-plane/scripts/managerctl.py skill update-plan \
  --request /absolute/path/to/skill-update.yaml \
  --output /absolute/path/to/skill-promotion.plan.json

python3 skills-control-plane/scripts/managerctl.py skill promote \
  --plan /absolute/path/to/skill-promotion.plan.json \
  --approve sha256:<exact-plan-hash> \
  --journal-dir /absolute/private/path/to/promotion-journal
```

Roll back a candidate, canary or promotion journal with the skill-specific seam:

```bash
python3 skills-control-plane/scripts/managerctl.py skill rollback \
  --journal /absolute/path/to/apply-....json \
  --approve sha256:<exact-journal-hash> \
  --journal-dir /absolute/private/path/to/rollback-journal
```

Candidate source bytes, authority commit, evidence content and target preconditions are rechecked immediately before apply. A canary is not considered successful merely because files copied: the promotion request requires a separate structured `PASS` evidence document bound to the exact candidate, project and authority commit. Project-only overlays remain project-scoped; the V1 shared promotion path handles releases and packs.

## Fleet status

```bash
python3 skills-control-plane/scripts/managerctl.py fleet status --format json \
  --output /absolute/path/to/fleet-status.json
python3 skills-control-plane/scripts/managerctl.py fleet status --format markdown \
  --output /absolute/path/to/fleet-status.md
```

States are projections:

- `GREEN` — authority files are readable and runtime is not reporting a blocker;
- `BLUE` — reviewed update available (reserved for update-inbox integration);
- `AMBER` — deliberately pinned or rebase/test due;
- `RED` — blocked, drifted, missing or unsafe;
- `GREY` — inventory-only/non-routable.

JellySSH currently appears `RED` because its runtime is deliberately `setup-verified-routing-blocked`; this is accurate and does not invalidate the manager.

## JellySSH Phase 2 commands

```bash
python3 skills-control-plane/scripts/projectctl.py scan
python3 skills-control-plane/scripts/projectctl.py plan
python3 skills-control-plane/scripts/projectctl.py project-init --dry-run
python3 skills-control-plane/scripts/projectctl.py verify
python3 skills-control-plane/scripts/projectctl.py audit
python3 skills-control-plane/scripts/projectctl.py status --output skills-control-plane/generated/jellyssh-status.md
python3 skills-control-plane/scripts/projectctl.py status --format json --output skills-control-plane/generated/jellyssh-status.json
```

JellySSH `runtime.yaml` declares two non-overlapping evidence scopes. `bootstrap_baseline` assigns the Phase 2 cut only to setup, paths, profiles, repository auth, toolchain, board, rollback, skill materialization, and governance decisions. `reviewed_authority` assigns `review_boundary` to an evolving exact-hash-reviewed authority so later controller sources and BUG-008 evidence are not misdated as Phase 2 observations. `current_state_source` remains `live-projectctl-scan-and-work-item-preflight`. Bootstrap `scan`, `verify`, and `audit` compare live state with the immutable baseline sections and therefore truthfully report drift after a work cycle; they do not turn the old `task_count: 0` into a current observation. Validate one release gate through the additive lifecycle interface instead:

```bash
cp skills-control-plane/templates/jellyssh-work-item-lifecycle.example.json \
  /absolute/reviewed/path/BUG-008-implementation-release.json

python3 skills-control-plane/scripts/projectctl.py \
  --project skills-control-plane/projects/jellyssh/project.yaml \
  --json preflight \
  --contract /absolute/reviewed/path/BUG-008-implementation-release.json \
  --output skills-control-plane/generated/evidence/<evidence-name>.json
```

The contract schema rejects unknown fields and binds exact local/SSH checkout paths, transport, origin, commit, branch, detached state, cleanliness, replacement refs, board/card identities, parent links, assignee, workspace, status, the unassigned dependency hold lane, and conservative concurrency. Exact Git probes run with replacement objects disabled. Evidence is canonical JSON written atomically as a direct `.json` child of `generated/evidence`; the CLI reports both contract and evidence SHA-256 digests and exits non-zero on every block or pre-commit write failure. Atomic replacement is the publication commit point for every authoritative/generated single-file writer, including manager, status, lifecycle, capability, timing, review, and acceptance artifacts. The authenticated implementation manifest covers `managerctl.py` and shared `managerlib.py` as well as the review, governance, project, boundary, and MCP controllers. Directory handles open before replacement. Failures before replacement leave no new trusted target and public CLI seams translate them to structured `BLOCK`; post-commit directory durability and stale-temp cleanup are best effort and never report failure after PASS exposure. No controller attempts fallible unlink/truncate repair after publishing PASS.

For an `implementation-release` gate, create an unassigned preflight parent and an unassigned dependent implementation child. Do not use `--initial-status blocked`. Before parent completion, the child must remain `todo`; run preflight and accept only PASS evidence. Completing the parent may promote the child to `ready`, but an embedded dispatcher pass must list it as skipped/unassigned and must not spawn it. The operator releases the exact child only by assigning `jellybase_jellyssh` after reviewing the PASS evidence. Dispatcher and claim paths still recheck unfinished parents independently.

### Restricted exact-ref evidence

`review_git_show` accepts a closed authority set: exact full-SHA base, target, and—when required—specification commits. Caller-supplied branches, tags, abbreviated or uppercase SHAs, and arbitrary commits are rejected. The legacy `HEAD` token is accepted only after resolving to the exact configured target SHA, so it cannot widen the readable set or alias the base/specification. When the approved specification was introduced at an intermediate commit and its target-path bytes later changed (for example, implementation evidence was appended), the review contract must bind one exact `specification_commit`. The controller requires full lowercase SHAs, exact configuration keys, and proves `base <= specification <= target` with replacement objects disabled; the MCP boundary then admits exactly those three commits and rejects any fourth ref. The MCP facade refuses to start unless all three exact SHAs are present. The retained evidence controller includes base and specification commits in both its model prompt and validated response contract, and fetches the required `specification_path` with `review_git_show` at that exact commit. It sends the bounded authenticated bytes plus SHA-256 as `approved_specification`; the validated reviewer result must echo the exact specification path and authenticated SHA-256, preventing target-mutated bytes or verdict reuse across different paths or specification authority. Reading the specification at target is valid only when its authenticated bytes are identical to the approved commit.

### Certified review warm path

`templates/governed-bug-workflow/` is the copyable operator package for a small real-bug canary after independent publication of the controller tree. `reviewctl.py --capability-preflight-output ... --attempt-id t_<id>` runs the real restricted profile/MCP/ref/specification/toolchain readiness path without calling the semantic model and publishes an authenticated non-semantic envelope. Before dispatch, the operator validates that exact envelope for the same attempt, base, specification commit/path/digest, target commit/tree, controller/schema bytes, profile, and repository metadata, then attaches it to the fresh Kanban review card. The reviewer still performs independent semantic analysis and fresh policy-required product checks; canonical latest-run metadata echoes the exact capability-file digest so `governancectl review-bind` can authenticate the handoff. Product meaning and verdicts are never cached. Every card/attempt/target/specification change requires fresh capability evidence and a fresh semantic verdict.

`governancectl.py` rejects parent-only publication in delegated-child context, records non-overlapping `active_execution`, `queue_wait`, `reviewer_remediation`, and `operator_delay` intervals with both category and stage totals, and normalizes canonical read-only Kanban review/acceptance snapshots. It derives the shared Hermes root from the invoking OS account database rather than caller-controlled `HOME`. The review binder requires the exact configured board and reviewer profile, terminal completion with `current_run_id = NULL`, the latest ended terminal run ordered by `ended_at DESC, id DESC`, scratch workspace, a 1,200-second runtime cap, one retry, both Standards and Specification PASS, zero findings, and the exact authority object. Active tasks resolve only their exact `current_run_id`. The acceptance binder requires the same board, an exact single review parent, an explicit producer/null contract matched by both task assignee and latest-run profile, the unchanged normalized review snapshot, and canonical latest-terminal-run metadata containing an identical review digest, authority, verdict, and check list. Immediately before publication it recaptures review and acceptance in one SQLite read transaction. Canonical snapshots, review contracts, capability envelopes, review-authority inputs, and acceptance requests reject secret-bearing keys and secret-shaped scalar values; acceptance evidence is bounded to 4096 UTF-8 bytes per check. Both outputs archive task/run/profile/timestamps/metadata/parents/log path plus a reproducible source snapshot digest. Exported JSON, card prose, and free-text completion result/summary are not authority. Atomic rename is the publication commit point: pre-rename failures leave no new PASS target, and post-commit durability cleanup cannot report failure after PASS exposure. PR opening and merge remain unauthorized.

Use both rollout phases: certify this reusable machinery before the next bug, then run the next small deterministic bug as a measured canary. Do not repair controller infrastructure inside that product attempt; close it as BLOCK/TIMEOUT, measure remediation separately, independently review the remediation tree, and start a fresh attempt. Capability evidence never authorizes a semantic PASS.

### Restricted Flutter test evidence

`run_readonly_check("flutter-test")` and the closed-enum focused routes use Flutter's `--machine` JSON reporter. A final review specification must select exactly one controller-owned `focused_check`: `sftp-browser-test` is pinned to `test/screens/sftp/sftp_browser_screen_test.dart`, while `terminal-behaviour-test` is pinned to `test/screens/settings/terminal_behaviour_settings_screen_test.dart`. Neither route accepts caller-supplied paths or arguments. One in-memory semantic validator is applied during file loading, capability generation, capability validation, and governance binding; governed review authority retains both `review_type` and `focused_check` so the selected route cannot disappear after binding. The unbounded event stream and stderr stay inside the disposable sandbox; only a versioned JSON summary of at most 4096 bytes crosses Docker, SSH, and MCP. The summary includes the exact fixed check identity, reporter/protocol, real Flutter exit code, terminal `done` marker, success, pass/fail/skip/total counts, and at most eight diagnostics of 320 characters each.

The reporter requires one initial complete `0.1.<digits>` protocol event, valid allowlisted Flutter progress events, unique test completions, at least one visible test, exactly one final `done` event, exit `0`, terminal success, and zero failures/errors. Malformed JSON/events, events after `done`, missing or contradictory terminal state, unknown results, duplicate completions, nonzero exit, failed tests, or inconsistent totals fail closed. The controller independently parses the compact object and rejects raw `PASS` text or any semantic/size drift. Existing exact-commit materialization, network-none, read-only root/input, bounded tmpfs/storage/PID/memory/swap/CPU, no-new-privileges, timeout, and sequential-check controls are unchanged.

Retained proof for the frozen BUG-008 review target is `projects/jellyssh/evidence/flutter-test-compact-summary.json`; `runtime.yaml` separately pins its immutable producer-source hashes and the current governed controller-source hashes. A reviewed controller update therefore does not rewrite historical provenance, while drift in either authority remains blocking. Semantic validation parses the same in-memory byte snapshot whose digest was authenticated, so transient unpinned file contents cannot influence a verdict even if the path is restored before validation ends. Static and live validation also re-hash each pinned controller/evidence path twice immediately before returning, so later authority changes or unavailability block that same invocation.

## Verification

```bash
python3 skills-control-plane/scripts/managerctl.py verify
python3 -m unittest discover -s skills-control-plane/tests -p 'test_*.py'
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile skills-control-plane/scripts/*.py
```

## Hash contract

Skill-package hashes use:

```text
sha256(sorted(u64be(path-byte-length) + UTF-8-relative-path
              + u64be(content-byte-length) + content-bytes))
```

Symlinks and non-regular files are rejected. Release/pack aggregate hashes use canonical JSON over artifact name, version and sorted skill name/hash pairs. Descriptor hashes cover governance metadata, provenance, ownership, compatibility, approvals, state and aggregate hash. Content or metadata drift requires a new reviewed version; changing an immutable directory in place is not an update path.

## Deferred capabilities

Not part of this V1 manager:

- scheduled/automatic audits or promotion;
- mutable upstream tracking or automatic downloads;
- a write-capable Desktop control surface;
- automatic overlay conflict resolution;
- automatic or general JellySSH Phase 3 rollout beyond separately approved manual lifecycle contracts;
- LogK adapter rollout.

The manual BUG-008 pilot exercised the additive lifecycle-preflight interface; it did not make arbitrary Phase 3 cards routable or remove operator assignment, PR, merge, release, or deployment gates.

Repository unit tests run `scan(..., live_discovery=False)` to validate checked-in catalog, project/runtime schema, authority bindings, controller/evidence hashes, runtime skill bundles, quality evidence, and setup-state semantics without reading mutable host state. The CLI defaults to live discovery: run `projectctl scan` for current profile, checkout, MCP, board, network, and rollback drift; run `projectctl preflight` with an approved lifecycle contract before releasing an exact work item. A green unit suite is not runtime authorization.

Generated JSON/Markdown may later feed a read-only Desktop view. Git remains authoritative.
