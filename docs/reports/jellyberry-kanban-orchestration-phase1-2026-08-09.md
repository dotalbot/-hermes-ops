# Jellyberry Kanban orchestration V3 — Phase 1 completion report

> **Status:** Phase 1 revised with database/data and Skill Control Plane governance, independently reviewed, and awaiting operator acceptance
>
> **Completed:** 2026-08-09
>
> **Authority:** [Jellyberry Kanban orchestration design V3](../operations/multi-agent-development/jellyberry-kanban-orchestration-design-v3.md)

## Scope

Phase 1 inventoried the existing workflow skills and expert assets, refreshed the read-only JellySSH agent intake, selected explicit model bindings, defined reviewer tools and stop conditions, created a controlled skill manifest, and designed the `matt-kanban-development` bridge.

It did not install, update, synchronize, or promote any skill. It did not create a JellySSH checkout, profile, board, workspace, card, adapter, memory bank, or worker. It did not change LogK, Hindsight, gateway, dispatcher, existing profiles, or Kanban state.

## Deliverables

- [Skill manifest](../operations/multi-agent-development/manifests/jellyssh-phase1-skill-manifest.json)
- [Expert inventory](../operations/multi-agent-development/manifests/jellyssh-phase1-expert-inventory.json)
- [Expert and model bindings](../operations/multi-agent-development/jellyssh-phase1-expert-model-bindings.md)
- [Skill Control Plane and project initialization](../operations/multi-agent-development/skill-control-plane-and-project-initialization.md)
- [Project manifest schema](../operations/multi-agent-development/manifests/project-skill-profile.schema.json)
- [JellySSH project-initialization example](../operations/multi-agent-development/manifests/jellyssh-project-initialization.example.yaml)
- [`matt-kanban-development` bridge design](../operations/multi-agent-development/matt-kanban-development-bridge.md)
- [Updated Matt skills operating guide](../operations/multi-agent-development/matt-pocock-skills.md)

## Skill inventory result

Source reviewed:

```text
Repository: https://github.com/mattpocock/skills
Pinned active-content revision: 84fdeffd12f2ee307994d1eb6feb48173b6e0502
Previous lock revision still present in some records: ed37663cc5fbef691ddfecd080dff42f7e7e350d
```

Verified state:

- The managed collection contains 35 selected skills in both `default` and `jellybase_hermes`.
- All 35 profile copies match each other exactly.
- Thirty-four match the pinned upstream revision exactly.
- `research` matches upstream plus the local `DESCRIPTION.md` overlay.
- The upstream tree contained 41 skill directories at the observed revision; unselected skills are not implicitly approved.
- Some Hermes hub lock provenance is stale relative to active content. The manifest records exact active/upstream hashes and fails closed on future mismatches.

Approved for a Phase 2 isolated profile load test:

```text
Core:        grill-with-docs, to-spec, to-tickets, implement, tdd, code-review
Conditional: codebase-design, diagnosing-bugs
```

All other managed skills are inventory-only for this pilot. No skill has `promotion_state` permitting Phase 1 routing.

Existing rollback location:

```text
/home/jellybot/.hermes/backups/jellybase_hermes-mattpocock-skills-20260806T215958Z
```

A fresh backup remains mandatory immediately before any later promotion.

## Expert inventory result

The JellySSH repository was refreshed through an ephemeral bare/no-checkout intake:

```text
Remote: git@github.com:dotalbot/jellyssh.git
Commit: 7f612d96bd35fcaa336956d7922a82513d2e9e0d
```

The intake verified nine agent definitions, seven command definitions, the JellySSH guard plugin, `opencode.json`, and repository authority documents. Exact hashes are in the expert inventory.

Key findings:

- `code-reviewer` is the only project agent with an explicit read-only permission contract.
- Implementation specialists allow edits and broad shell commands and cannot serve as reviewer identities.
- Most project agents inherit the OpenCode runtime model and therefore are not deterministic model bindings.
- `coder` and `tester` name `openai/gpt-5.3-codex`; that is recorded reference state, not the Hermes pilot binding.
- Shared local assets cover repository governance, workflow governance, architecture, code quality, and general review.
- No shared local asset is a complete Flutter/SSH credential-security expert or Flutter/mobile UX expert, so those roles compose shared procedures with exact JellySSH project overlays.
- The JellySSH OpenCode guard is useful but does not enforce Hermes profile, bank, model, workspace, or tool boundaries by itself.

No JellySSH repository checkout or working tree was created.

## Approved proposed model bindings

```text
Design/spec/tickets:  default
                      openai-codex / gpt-5.6-sol

Implementation:       jellybase_jellyssh (proposed Phase 2 profile)
                      openai-codex / gpt-5.6-terra

Testing/review/final: jellybase_jellyssh_reviewer (proposed Phase 2 profile)
                      openrouter / deepseek/deepseek-v3.2

UI expert:            jellybase_jellyssh_reviewer with exact task override
                      openrouter / google/gemini-3.1-pro-preview
```

The OpenRouter credential is configured without exposing its value. `deepseek/deepseek-v3.2` and the UI candidate were visible in the live model catalogue on 2026-08-09. DeepSeek replaces the earlier Claude proposal to reduce review cost. Both exact identifiers must be rechecked during Phase 2; disappearance or identifier drift blocks for operator selection rather than triggering fallback.

Implementation and final review use different provider/model families. Review also requires fresh context, an exact commit, separate workspace, automatic retention disabled, and a tested write boundary.

## Expert triggers

```text
Architecture: architecture or multi-module change
Security:     credentials, auth, host keys, networking/forwarding,
              secure storage, external processes, or sensitive logging
UI:           any user-visible or interaction change
Database/data: schema, migration, query/integrity, pipeline, retention,
               backup/restore, or sensitive-data change
Code quality: every implementation
Final review: every Level 1-or-higher implementation after all required reports
```

Triggered experts run both before implementation against the design and after implementation against the exact diff. Missing reports block final acceptance.

Cross-model activation is risk-tiered: Level 0 mechanical work has no cross-model gate; Level 1 normal implementation has a post-commit final review; Level 2 architecture/security/UI/database-data/dependency/concurrency/material work has pre/post expert review plus final review; and Level 3 destructive, irreversible, production-data, credential/signing/release/deployment, or disputed work adds an explicit operator hold.

The database/data capability pack is globally governed but opt-in per project. It supplies database-design, data-engineering, and data-governance contracts and composes with project overlays such as JellySSH's Drift/Riverpod rules. Mandatory reports cover invariants, migration and rollback, transaction/index strategy, classification/retention, backup/restore, integrity/query evidence, and residual production-data gates.

## Reviewer boundary

The reviewer may inspect the exact commit, run read-only Git commands, Flutter analysis/tests in its isolated workspace, and append a structured result to its Kanban card. It may not edit source, commit, push, switch branches, create PRs, merge, release, sign, sideload, deploy, use sudo, read secrets, access arbitrary network resources, or share the implementation workspace.

Hermes's native `file` toolset includes write tools. Therefore a prompt-only reviewer role is not sufficient. Phase 2 must implement and smoke-test a restricted adapter/command boundary. If write tools, arbitrary terminal commands, or implementation-workspace writes remain reachable, the reviewer profile fails and routing remains blocked.

## Independent revision review

The completed Phase 1 revision was reviewed read-only with OpenRouter `google/gemini-3.1-pro-preview`, independently of the OpenAI Codex authoring model and the proposed DeepSeek runtime reviewer. The direct repository review returned `REVIEW PASS` on 2026-08-09. It confirmed the Phase 2 boundary, exact fail-closed DeepSeek binding, Level 0–3 activation policy, database/data contract, four-layer authority, Hermes external-directory/bundle caveats, schema-backed dry-run initialization, non-routable zero hashes, and read-only generated visual layer. An earlier review attempt that was denied permission to create a temporary file produced no verdict and is not counted.

## Controlled promotion process

```text
inventory
  -> fetch exact candidate outside active profiles
  -> source/integrity record
  -> diff upstream and local overlays
  -> security and compatibility review
  -> isolated profile/session test
  -> profile/bank/model/workspace routing preflight
  -> operator approval
  -> selective promotion to named profiles
  -> fresh rollback copy and updated provenance
```

Global installs, direct active-profile overwrites, silent overlay loss, and routable candidates are prohibited.

## Skill Control Plane and project initialization result

The revised design adds four versioned layers:

```text
immutable core release
  -> opt-in capability packs
  -> project-prefixed overlays in the project repository
  -> profile/model/tool/bank/workspace runtime bindings
```

The private `hermes-ops` repository is the desired-state authority; `~/.hermes` backups remain recovery artifacts rather than a release source. Core and pack changes create a new release, impacted-project report, isolated tests, canary result, approval, controlled rollout, and rollback. Project tweaks create separately versioned overlays and affect only named project profiles.

The proposed `/project-init` workflow is dry-run first and backed by schema-validated `projectctl scan`, `plan`, `apply`, `verify`, `reconcile`, and `status` stages. Scan/plan detect repository authority, stack, data/security/UI risk, existing agent assets, profile/model/bank/tool/workspace state, and skill hashes. Apply is a separate future authorization and leaves the board non-executable.

Long-running projects receive non-mutating health states for current, update available, deliberately pinned/rebase due, unsafe drift, and inventory-only state. Generated Markdown/JSON and a later read-only Desktop Skill Control Center render fleet, project, skill, expert, dependency, drift, update, provenance, and rollback views. The visual layer never becomes a second authority.

Native Hermes caveats are explicit: writable external directories are mutable, local skill names shadow external names, absent external directories are skipped, and bundles skip missing members. The project preflight turns each of those into a blocking error.

## Bridge result

The bridge design defines:

- explicit Matt skill-to-Kanban phase composition;
- atomic preflight checks;
- design, specification, expert, ticket, implementation, test/review, fix, and final fan-in card contracts;
- one-card-at-a-time execution;
- operator-controlled `ready` transitions;
- exact evidence and stop conditions;
- no automatic fallback, decomposition, PR, merge, release, or deployment.

The bridge remains documentation. No local Hermes skill was created.

## Completion criteria assessment

- Every current design/spec/ticket route names the real `default` profile and installed skills.
- Every later implementation/review route names an approved Hermes profile identity and exact skill set, but those profiles intentionally do not exist until Phase 2. They are non-routable until live creation and smoke tests satisfy the Phase 2 gate.
- Required expert triggers are explicit.
- Database/data expertise is opt-in by project and mandatory for defined data-risk triggers.
- Cross-model review activation is explicit from Level 0 through Level 3.
- Reviewer independence is testable through provider/model, fresh context, exact commit, retention, workspace, and hard tool-boundary checks.
- Local overlays are recorded separately and cannot be silently overwritten by the manifest process.
- Core and project changes have separate versioned release paths.
- The project initializer is schema-described, idempotent, dry-run first, and non-executable until live verification.
- The visual status is generated from manifests and audit evidence.
- No candidate skill was copied into any profile.

## Known Phase 2 blockers and tests

These are expected setup gates, not permission to act now:

1. Implement and independently review the minimum catalogue/projectctl dry-run path after Phase 2 authorization.
2. Materialize real core/pack release hashes; the Phase 1 example intentionally uses non-routable zero-hash placeholders.
3. Create and verify the two project profiles only after Phase 2 authorization.
4. Prove a hard reviewer write boundary; prompt instructions are insufficient.
5. Reconcile stale hub lock provenance during selective promotion without losing local overlays.
6. Recheck exact DeepSeek/Gemini OpenRouter model availability and credential usability in fresh profile sessions.
7. Verify the proposed Jellyberry/Jellybase paths, repository SSH authentication, ownership, clean state, remote, Flutter/Dart/Android tooling, and separate workspaces.
8. Verify `jellyssh-main` exists and test implementation/reviewer retention modes.
9. Implement no development and keep the proposed board without executable cards.

## Gate

Phase 1 completion does not authorize Phase 2. The next action is operator acceptance, revision, or rollback of this report. No profile, board, checkout, skill promotion, memory-bank creation, adapter, or development dispatch may begin without a new explicit decision.
