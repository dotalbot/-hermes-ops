# JellySSH Phase 1 expert and model bindings

> **Status:** Proposed Phase 1 binding set; no profile, skill, board, checkout, or runtime route has been created
>
> **JellySSH intake:** `git@github.com:dotalbot/jellyssh.git` at `7f612d96bd35fcaa336956d7922a82513d2e9e0d`
>
> **Inventory:** [expert inventory](manifests/jellyssh-phase1-expert-inventory.json) and [skill manifest](manifests/jellyssh-phase1-skill-manifest.json)

## 1. Binding rules

The pilot keeps these dimensions separate:

```text
skill = reusable procedure
expert = specialist judgement and output contract
profile = stable Hermes execution identity and safety boundary
model = explicitly selected reasoning engine
project overlay = JellySSH-local authority at an exact commit
worker = one disposable execution attempt
```

A JellySSH OpenCode agent is reference material, not automatically a Hermes skill, profile, or approved model binding. Project context remains in the JellySSH repository and is read at an exact commit rather than copied into global skills.

## 2. Inventory conclusions

### 2.1 Shared workflow skills

The current default and `jellybase_hermes` profiles each contain the same 35-skill Matt collection. The copies match each other exactly. Thirty-four skill bundles match upstream commit `84fdeffd12f2ee307994d1eb6feb48173b6e0502`; `research` matches that commit plus the local `DESCRIPTION.md` overlay.

Some existing Hermes hub lock records still name the older revision `ed37663cc5fbef691ddfecd080dff42f7e7e350d` even though active content matches the newer commit. Therefore the Phase 1 manifest's full content hashes and pinned upstream commit are authoritative for this pilot; stale lock metadata is not sufficient provenance. No lock file or active skill was changed during Phase 1.

Approved for a Phase 2 isolated load test, not promotion during Phase 1:

- Core: `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`.
- Conditional: `codebase-design` for architecture review and `diagnosing-bugs` only for a bounded fix investigation.
- The remaining 27 skills are inventory-only and are not approved for the first pilot route.

### 2.2 Shared expert assets

Useful shared assets exist for repository governance, governed workflow adoption, architecture, code quality, and code review. The inventory found no shared local skill that by itself is a complete Flutter/SSH credential-security expert or Flutter/mobile UX expert.

Consequences:

- Do not use `godmode` or a self-hosted deployment-security skill as a substitute for application security review.
- Do not use a web-page design skill as a substitute for Flutter/mobile UX review.
- Compose approved shared procedures with the exact JellySSH project overlays below.

### 2.3 JellySSH project overlays

The read-only bare intake found these project specialists:

- `flutter-architect`
- `ssh-terminal-engineer`
- `drift-riverpod-engineer`
- `mobile-ux-designer`
- `tester`
- `code-reviewer`
- `coder`
- `project-scribe`
- `jellyssh-orchestrator`

It also found seven project commands, `opencode.json`, repository authority files, and `.opencode/plugins/jellyssh-guard.js`. Exact hashes are in the expert inventory.

Only `.opencode/agents/code-reviewer.md` is read-only. The implementation specialists permit edits and broad shell commands and must not be reused as reviewer identities. Most project agents omit a model and inherit the OpenCode runtime default; `coder` and `tester` name `openai/gpt-5.3-codex`. Those are observations, not accepted Hermes model bindings.

The JellySSH guard is a useful project invariant source, but it is heuristic and OpenCode-specific. It does not prove Hermes profile routing, repository scope, reviewer read-only enforcement, bank correctness, or model independence. Phase 2 must test equivalent fail-closed controls rather than assuming the plugin protects Hermes.

## 3. Proposed phase routes

### Interactive design

```yaml
profile: default
provider: openai-codex
model: gpt-5.6-sol
skills: [grill-with-docs]
project_overlay:
  - CLAUDE.md
  - docs/ROADMAP.md
  - docs/DECISIONS.md
  - docs/ai/agent-routing.md
retention: hermes-main during Phase 1; jellyssh-main only after the Phase 2 route is verified
```

The coordinator may shape requirements and evidence but is not the implementation worker.

### Specification and tickets

```yaml
specification:
  profile: default
  provider: openai-codex
  model: gpt-5.6-sol
  skills: [to-spec]
  authority: docs/specifications/
ticketing:
  profile: default
  provider: openai-codex
  model: gpt-5.6-sol
  skills: [to-tickets]
  authority: repository tickets/specification plus Jellyberry Kanban for execution state
```

### Implementation

```yaml
profile: jellybase_jellyssh
profile_state: proposed-until-phase-2
provider: openai-codex
model: gpt-5.6-terra
skills: [implement, tdd]
conditional_skills: [diagnosing-bugs]
project_overlays:
  - .opencode/agents/coder.md
  - relevant implementation specialist selected by trigger
bank: jellyssh-main
retention: deliberate stable project facts only
```

There is no fallback to `jellybase_hermes`, another model, another bank, or an unreviewed skill copy.

### Independent testing and review

```yaml
profile: jellybase_jellyssh_reviewer
profile_state: proposed-until-phase-2
provider: openrouter
model: anthropic/claude-sonnet-4.6
skills: [code-review]
project_overlays:
  - .opencode/agents/tester.md
  - .opencode/agents/code-reviewer.md
bank: jellyssh-main
retention: auto_retain_false
context: fresh exact-commit card
workspace: separate from implementation
```

The reviewer model is a different provider/model family from the implementation model. If the exact model is unavailable, the review blocks; it does not fall back to the implementer's model.

### Expert bindings

```yaml
architecture:
  trigger: architecture_or_multi_module_change
  profile: jellybase_jellyssh_reviewer
  provider: openrouter
  model: anthropic/claude-sonnet-4.6
  shared_skills: [codebase-design]
  project_overlays: [.opencode/agents/flutter-architect.md]
security:
  trigger: credentials_auth_host_keys_network_forwarding_storage_external_process_or_logging
  profile: jellybase_jellyssh_reviewer
  provider: openrouter
  model: anthropic/claude-sonnet-4.6
  shared_skills: [code-review]
  project_overlays:
    - .opencode/agents/ssh-terminal-engineer.md
    - .opencode/agents/drift-riverpod-engineer.md
    - .opencode/agents/code-reviewer.md
ui:
  trigger: user_visible_or_interaction_change
  profile: jellybase_jellyssh_reviewer
  provider: openrouter
  model: google/gemini-3.1-pro-preview
  shared_skills: [code-review]
  project_overlays:
    - .opencode/agents/mobile-ux-designer.md
    - .opencode/agents/flutter-architect.md
code_quality:
  trigger: every_implementation
  profile: jellybase_jellyssh_reviewer
  provider: openrouter
  model: anthropic/claude-sonnet-4.6
  shared_skills: [code-review]
  project_overlays: [.opencode/agents/code-reviewer.md]
cross_model_final_review:
  trigger: every_implementation_after_all_required_reports
  profile: jellybase_jellyssh_reviewer
  provider: openrouter
  model: anthropic/claude-sonnet-4.6
  shared_skills: [code-review]
  context: fresh_fan_in_of_exact_commit_and_required_reports
```

`google/gemini-3.1-pro-preview` is accepted only as the Phase 2 UI-expert test candidate. Because it is a preview identifier, Phase 2 must recheck availability and block for operator replacement if it has disappeared or changed. It must not silently substitute another Gemini model.

## 4. Reviewer tool boundary

The intended reviewer surface is:

- read repository files and search text;
- inspect only the exact branch/commit and supplied specifications;
- run `git status`, `git diff`, `git log`, and `git show`;
- run `cd app && flutter analyze` and `cd app && flutter test` in a separate reviewer workspace;
- check formatting without rewriting source, using a non-writing format check;
- write only the structured review result to the Kanban task through the local Hermes adapter.

Denied:

- repository edits, patching, commits, pushes, branch changes, PRs, merges, releases, signing, sideloading, deployment, sudo, secret reads, web access, arbitrary network access, arbitrary shell, implementation-workspace access, and automatic memory retention.

Hermes's native `file` toolset contains both read and write tools, so selecting that toolset alone is not a hard read-only boundary. Phase 2 must implement and smoke-test an enforceable boundary, such as a dedicated restricted adapter/command allowlist plus an isolated reviewer workspace. A prompt-only instruction is insufficient. If `write_file`, `patch`, arbitrary terminal execution, or implementation-workspace writes remain reachable, reviewer setup fails and Phase 2 blocks.

Running Flutter analysis/tests may write disposable caches in the reviewer workspace. That does not authorize source edits. The workspace must be isolated and disposable, and a post-run Git status must show no tracked source changes.

## 5. Reviewer output contract

Every expert and reviewer returns:

```text
Verdict: PASS | BLOCKED
Exact repository, branch, and commit
Profile, provider, and model
Bank and retention mode
Scope/specification reviewed
Commands run and exact results
Findings ordered by Blocker/High/Medium/Low with file:line references
Missing tests or evidence
Residual risks
Write-boundary verification
```

The final reviewer blocks when any required report is missing, names another commit, lacks a model identity, reports a write-boundary failure, or has unresolved Blocker/High findings. Fixes require a bounded implementation card, triggered expert rechecks, and a fresh final rereview.

## 6. Stop conditions

Any worker or reviewer blocks on:

- missing or mismatched profile, provider, model, bank, retention mode, skill hash, repository, path, remote, branch, or commit;
- missing project authority, specification, acceptance criteria, expert report, test evidence, or JellySSH guard equivalent;
- unknown local changes or a shared implementation/review workspace;
- secret, credential, sudo, production, release, signing, sideloading, deployment, physical-device, or destructive-command requirements;
- an attempted reviewer write or tool outside the allowlist;
- an unavailable required cross-model reviewer;
- a request to fall back to `jellybase_hermes`, `jellybase-worker-main`, or the implementer's model.

## 7. Phase boundary

This document approves bindings for a Phase 2 no-op/isolated smoke test only after the Phase 1 report is accepted. It does not create profiles, install skills, clone JellySSH, create a board, dispatch development, or authorize Phase 2 automatically.
