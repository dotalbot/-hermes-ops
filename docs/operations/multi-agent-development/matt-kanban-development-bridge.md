# `matt-kanban-development` bridge design

> **Status:** Phase 1 design only; not installed as a Hermes skill and not dispatchable
>
> **Purpose:** Compose reviewed Matt Pocock workflows with Jellyberry Kanban without changing upstream skill content
>
> **Skill authority:** [JellySSH Phase 1 skill manifest](manifests/jellyssh-phase1-skill-manifest.json)
>
> **Expert authority:** [JellySSH Phase 1 expert/model bindings](jellyssh-phase1-expert-model-bindings.md)

## 1. Boundary

`matt-kanban-development` is a proposed local orchestration bridge. It owns phase transitions, card contracts, dependency links, routing preflight, and evidence fan-in. It does not fork, patch, wrap in-place, or silently replace `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`, or any JellySSH repository asset.

```text
upstream Matt skill       how one phase is performed
bridge                    when a phase may run and what evidence crosses the gate
JellySSH repository       product, architecture, security, and quality authority
Hermes profile            identity, host, bank, model, tools, and safety boundary
Kanban                    live task state, dependencies, comments, and worker lifecycle
Git                       branch, commit, diff, and durable handoff
operator                  approval and release decisions
```

The bridge remains repository documentation until a later phase explicitly approves creating a local skill from this design.

## 2. Required inputs

```yaml
project:
  name: jellyssh
  remote: git@github.com:dotalbot/jellyssh.git
  authority_commit: exact_commit_required
  specification_root: docs/specifications
route:
  board: jellyssh
  implementation_profile: jellybase_jellyssh
  reviewer_profile: jellybase_jellyssh_reviewer
  implementation_bank: jellyssh-main
  reviewer_bank: jellyssh-main
  implementation_auto_retain: true
  reviewer_auto_retain: false
policy:
  auto_decompose: false
  max_spawn: 1
  max_in_progress: 1
  default_assignee: null
  orchestrator_profile: null
skills_manifest: manifests/jellyssh-phase1-skill-manifest.json
expert_bindings: jellyssh-phase1-expert-model-bindings.md
```

Every path and profile is non-routable until Phase 2 verifies it live.

## 3. Workflow graph

```text
operator-approved problem
  -> interactive design [default + grill-with-docs]
  -> versioned spec [default + to-spec]
  -> architecture/security/UI expert parents as triggered
  -> operator design approval
  -> dependency-aware tickets [default + to-tickets]
  -> one ready implementation card [jellybase_jellyssh + implement + tdd]
  -> exact implementation commit
  -> independent test/review cards [jellybase_jellyssh_reviewer + code-review]
  -> triggered diff-based expert reviews
  -> fresh cross-model final review
  -> operator acceptance decision
```

No bridge step automatically moves a card to `ready`. Only the operator-facing coordinator may do so after checking all parents and preflight evidence.

## 4. Preflight contract

Before creating or readying an executable card, verify as one atomic gate:

1. The board exists and has the approved workdir.
2. The assignee is a real installed Hermes profile.
3. A fresh profile session reports the expected provider/model, bank, and retention mode.
4. Every pinned skill is approved in the exact manifest and its active hash matches.
5. Repository path, owner, remote, clean state, branch, and exact base commit match the project route.
6. Implementation and review workspaces are separate.
7. The JellySSH guard equivalent and repository invariants are active.
8. Required expert parent cards are complete and name the same specification revision.
9. Automatic decomposition and fallback assignment remain disabled.
10. No other executable pilot card or worker is active.

Any mismatch blocks the card with an audit comment. The bridge must not repair, clone, reassign, install, promote, or fall back as a side effect of preflight.

## 5. Card contracts

### 5.1 Design card

```yaml
assignee: default
skills: [grill-with-docs]
inputs:
  - exact repository authority commit
  - problem and non-goals
  - existing roadmap/specifications/decisions
outputs:
  - agreed design questions and decisions
  - triggered expert list
stop_on:
  - missing authority
  - unresolved product/security/device decision
```

Interactive design is a session-level activity. It does not edit implementation code.

### 5.2 Specification card

```yaml
assignee: default
skills: [to-spec]
outputs:
  - versioned file under docs/specifications/
  - acceptance criteria
  - non-goals
  - test and device-evidence plan
  - expert triggers
  - rollback/stop conditions
```

### 5.3 Expert design-review card

```yaml
assignee: jellybase_jellyssh_reviewer
skills: [codebase-design] # architecture only
model: exact binding from expert document
mode: read-only
parents: [specification]
outputs:
  - PASS or BLOCKED
  - numbered findings with severity and file:line/spec references
  - model/profile/commit identity
```

Security and UI experts use the same contract with their approved shared procedure and project overlay. Missing triggered expert reports block implementation.

### 5.4 Ticketing card

```yaml
assignee: default
skills: [to-tickets]
parents:
  - accepted specification
  - all required expert design reviews
outputs:
  - small vertical tickets
  - dependency edges
  - exact acceptance criteria per ticket
  - one proposed first implementation ticket
```

Ticket generation does not create or ready implementation cards automatically.

### 5.5 Implementation card

```yaml
assignee: jellybase_jellyssh
skills: [implement, tdd]
parents:
  - accepted specification
  - approved ticket
  - required design expert reviews
required_body:
  repository: exact approved Jellybase path
  remote: git@github.com:dotalbot/jellyssh.git
  branch: exact feature branch
  base_commit: exact hash
  specification: exact path and revision
  ticket: exact path or identifier
  allowed_files: explicit list or bounded area
  tests: explicit commands
  bank: jellyssh-main
  model: openai-codex/gpt-5.6-terra
  stop_conditions: explicit list
outputs:
  - exact commit
  - changed files
  - commands and exact results
  - remaining risks
```

Only one implementation card may be `ready` or `running`. No PR, merge, release, signing, sideloading, deployment, sudo, secret access, or physical-device claim is authorized.

### 5.6 Independent test/review card

```yaml
assignee: jellybase_jellyssh_reviewer
skills: [code-review]
parents: [implementation]
mode: read-only
required_body:
  exact_branch: required
  exact_commit: required
  separate_workspace: required
  implementation_model: required
  reviewer_model: openrouter/anthropic/claude-sonnet-4.6
outputs:
  - PASS or BLOCKED
  - exact commands and results
  - findings by severity
  - write-boundary verification
```

A reviewer finding never authorizes the reviewer to fix code.

### 5.7 Fix card

A fix is a new bounded implementation card linked to the failed review. It names accepted findings, exact scope, tests, and the prior commit. It cannot reuse the reviewer workspace. Applicable experts rerun against the fix commit, followed by a fresh final review.

### 5.8 Final fan-in card

```yaml
assignee: jellybase_jellyssh_reviewer
skills: [code-review]
model: openrouter/anthropic/claude-sonnet-4.6
parents:
  - independent tests
  - code-quality review
  - every triggered diff-based expert review
inputs:
  - exact final commit
  - complete parent reports
outputs:
  - PASS or BLOCKED
  - missing/stale/wrong-commit report detection
  - unresolved finding ledger
  - residual manual/device gates
```

The final card blocks if a required report is absent, stale, malformed, from the wrong model/profile, or refers to another commit.

## 6. State transitions

```text
triage -> todo        operator/coordinator accepts the task for design
 todo -> ready        operator/coordinator confirms all parents and preflight
ready -> running      native dispatcher claims the exact assigned profile
running -> done       worker returns complete verifiable evidence
running -> blocked    any mismatch, missing authority, unsafe requirement, or failed check
blocked -> ready      operator resolves the named issue and explicitly unblocks
```

The bridge never treats `done` as approval for a later phase, another board, PR, merge, release, or deployment.

## 7. Skill lifecycle integration

The bridge accepts only manifest entries whose state is approved for the current phase and whose exact bundle hash matches the profile copy. Updating skills is a separate governed operation:

```text
inventory
  -> fetch exact candidate outside active profiles
  -> record source commit and hashes
  -> diff upstream and local overlays
  -> security and compatibility review
  -> isolated profile/session test
  -> routing preflight
  -> operator approval
  -> selective profile promotion
  -> new rollback copy and provenance
```

Candidate skills are never routable. A global installer or direct overwrite of active skills is prohibited. The `research/DESCRIPTION.md` local overlay must be preserved deliberately even though `research` is not approved for the first pilot.

## 8. Failure and stop conditions

The bridge blocks rather than guessing when:

- a profile, bank, skill, model, project overlay, guard, path, branch, commit, parent report, or required evidence is missing or mismatched;
- the reviewer can write or shares the implementation workspace;
- an expert model is unavailable;
- automatic decomposition/fallback or concurrency differs from policy;
- an operation needs credentials in prompts/cards/logs, sudo, production access, PR/merge/release/signing/sideload/deployment, or physical-device claims;
- a worker requests scope expansion or a destructive Git/filesystem command;
- an external engine returns missing, malformed, stale, or unverifiable output.

## 9. Phase boundary

Phase 1 approves this design for review only. Creating the local `matt-kanban-development` skill, profiles, board, workspaces, adapters, or cards requires a separately accepted later phase. Phase 2 may use this document to construct no-op routing tests but may not dispatch development.
