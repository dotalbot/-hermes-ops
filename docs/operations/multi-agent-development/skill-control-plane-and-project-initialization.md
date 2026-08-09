# Skill Control Plane and project initialization design

> **Status:** Phase 1 design accepted; minimum Phase 2 control-plane/project-initialization implementation authorized and in progress. The Desktop plugin, scheduled audit, and automatic promotion remain unauthorized.
>
> **Project manifest schema:** [project-skill-profile.schema.json](manifests/project-skill-profile.schema.json)
>
> **JellySSH example:** [jellyssh-project-initialization.example.yaml](manifests/jellyssh-project-initialization.example.yaml)

## 1. Purpose

Provide one auditable place to manage reusable skills across projects while retaining project-only procedures, explicit expert/model bindings, safe long-running updates, repeatable project initialization, and a visual fleet view.

```text
central catalogue owns desired skill releases
project repository owns project-only overlays and authority
profile owns runtime identity and materialized approved skills
Kanban owns live execution state
Git owns versions, review history, and rollback
visual view renders facts; it is not authority
```

The central catalogue belongs in the private `hermes-ops` repository rather than the backup of live `~/.hermes`. Backups preserve runtime state; they must not become the release source.

## 2. Hermes constraints

Hermes profiles have independent homes and do not automatically inherit one global skill tree. Native external skill directories and bundles are useful composition mechanisms, but they are not fail-closed governance by themselves:

- an external directory can be modified by `skill_manage` when writable;
- a local skill with the same name shadows an external skill;
- a missing external directory is silently skipped;
- a bundle skips missing member skills and still loads the remainder;
- hub lock metadata may disagree with active bytes after direct copies or external installers.

Therefore project routing validates exact skill names and hashes before invocation. It does not rely on directory presence, lock labels, bundle resolution, or prompt instructions alone.

Hermes Curator supplies useful usage/staleness signals, reports, backups, and recoverable archival for skills in its jurisdiction. It is not the release manager for the control plane: hub-installed skills are outside its mutation scope, user-directed project skills are normally unmanaged, and usage telemetry does not cover every bundled/hub skill. Governed profiles should use staged skill writes and conservative curation; desired releases remain Git-controlled.

## 3. Managed layers

### Layer 1 — core releases

Small procedures used by most development projects, for example:

```text
grill-with-docs
to-spec
to-tickets
implement
tdd
code-review
```

Core is versioned as an immutable release. Projects pin an exact release rather than following a moving branch.

### Layer 2 — capability packs

Globally governed but opt-in sets, for example:

```text
database-data
flutter-mobile
secure-application
web-application
infrastructure-operations
```

The `database-data` pack exposes database-design, data-engineering, and data-governance expert contracts. A project can enable it without loading it on every card; the trigger policy decides when it is required.

### Layer 3 — project overlays

Project-only procedures live in the project repository under a dedicated namespace, for example:

```text
.hermes-project/skills/jellyssh-drift-data-review/
.hermes-project/skills/jellyssh-ssh-security-review/
.hermes-project/skills/jellyssh-mobile-ux-review/
```

Project overlays use a project-prefixed name. They do not reuse a core skill name, because local-name precedence could silently shadow the core procedure. They declare the core/pack release against which they were tested.

Project facts and repository rules that do not need a reusable procedure remain in `AGENTS.md`, `CLAUDE.md`, specifications, decisions, or project documentation rather than becoming skills.

### Layer 4 — runtime bindings

The project manifest binds procedures to real execution identities:

```text
profile + host/backend + model + tools + bank + retention
+ workspace + bundle + expert triggers + safety policy
```

An installed skill does not become routable until this binding passes live preflight.

## 4. Proposed source layout

```text
skills-control-plane/
├── catalog.yaml
├── releases/
│   ├── core-development/
│   │   ├── 1.0.0/
│   │   └── 1.1.0/
│   └── database-data/
│       └── 1.0.0/
├── packs/
│   ├── database-data.yaml
│   ├── flutter-mobile.yaml
│   └── secure-application.yaml
├── projects/
│   ├── jellyssh.yaml
│   ├── home-network.yaml
│   └── portfolio-intel.yaml
├── schemas/
├── scripts/
│   ├── projectctl
│   ├── skill-audit
│   └── skill-promote
└── reports/
```

The repository stores source, pins, hashes, compatibility evidence, target projects/profiles, promotion state, and rollback relationships. Active profile skill directories are materialized runtime copies. Direct edits to those copies are drift, not a new source version.

## 5. Version and composition rules

A project pins all layers:

```yaml
core_release: core-development@1.3.0
capability_packs:
  - flutter-mobile@1.1.0
  - database-data@1.0.0
project_overlays:
  - name: jellyssh-drift-data-review
    version: 0.3.0
    tested_against:
      core: core-development@1.3.0
      packs: [database-data@1.0.0]
```

Use semantic release meaning:

- patch — clarification or compatible procedure correction;
- minor — additive trigger, output, reference, or optional procedure;
- major — changed permissions, required output, tool behavior, safety boundary, or incompatible contract.

A project-specific tweak is a separate overlay release. It does not patch the core copy. If the same overlay is useful in multiple projects, it becomes a reviewed capability-pack candidate. A global fix changes the central core/pack source and creates a new release.

## 6. Controlled global update

```text
edit central source
  -> bump release
  -> compute deterministic hashes
  -> review source and supply-chain changes
  -> generate impacted-project and overlay-compatibility report
  -> isolated profile/session tests
  -> canary project
  -> operator approval
  -> controlled profile-by-profile promotion
  -> fresh sessions and live preflight
  -> retain previous release and rollback evidence
```

No project follows `main`, a mutable symlink, or an automatically updated external directory. A project may remain deliberately pinned; its status becomes `PINNED`, not silently stale.

If a core update conflicts with a project overlay, promotion blocks with `OVERLAY_REBASE_REQUIRED`. The system never chooses which rule wins automatically.

## 7. Controlled project-only update

```text
edit project overlay in project repository
  -> bump overlay version
  -> verify project authority and exact base releases
  -> run project-only compatibility/security review
  -> operator approval
  -> promote only to named project profiles
  -> fresh session and route preflight
```

Other projects and global releases remain unchanged.

## 8. Project initialization

The proposed user entry point is:

```text
/project-init /absolute/path/to/repository
```

The skill would call a deterministic `projectctl` implementation with these stages:

```text
projectctl scan       read-only repository/profile/host discovery
projectctl plan       generate proposed manifest, profiles, packs, triggers, and diff
projectctl apply      create only the explicitly approved setup artifacts
projectctl verify     run profile/model/bank/skill/workspace negative and positive tests
projectctl reconcile  compare a long-running project with desired state
projectctl status     render one project without mutation
```

`scan` and `plan` are the defaults. `apply` is a separate operator action. Re-running initialization is idempotent reconciliation rather than duplicate creation.

### Scan

Inspect, without mutation:

- repository owner, remote, branch, worktree state, authority documents, language and framework;
- data stores, migrations, pipelines, PII/retention signals, backup/restore requirements;
- UI, security, external process, network, deployment, signing, and device boundaries;
- existing `AGENTS.md`, `CLAUDE.md`, `.opencode`, `.agents`, skills, CI, specs, and decisions;
- intended local/remote workspaces and toolchain;
- current profiles, model/provider availability, banks, retention, and skill hashes.

### Plan

Generate:

- `.hermes-project/project.yaml` proposal validated by the schema;
- core release and capability-pack selections;
- project overlay inventory and gaps;
- coordinator/implementation/reviewer profile proposals;
- model pairs, tools, banks, retention, and workspaces;
- risk-tier and expert-trigger matrix, including database/data;
- proposed task bundles with all members resolved;
- board metadata with no executable card;
- dry-run filesystem/config diff, rollback plan, and visual status entry.

Ask only for decisions the scan cannot safely infer. No secret value enters the manifest, prompt, report, or card.

### Apply and verify

A later authorized apply must back up affected profile/control-plane state, create only approved artifacts, and keep the board non-executable. Verification fails closed on missing bundle members, name shadowing, active-hash drift, wrong model/bank/retention, inaccessible or shared workspaces, write-capable reviewer boundaries, or unknown repository state.

Project initialization does not authorize implementation, PRs, merges, release, signing, sideloading, deployment, sudo, production data, or secrets.

## 9. Long-running project health

A non-mutating audit compares:

- desired versus active core/pack/overlay versions and hashes;
- upstream update availability and provenance;
- overlay base-release compatibility;
- missing, extra, shadowed, or locally modified skills;
- model/provider and required-tool availability;
- last isolated compatibility test and route preflight;
- project authority/remote/workspace drift;
- Curator usage and staleness signals where available.

Suggested states:

```text
GREEN   current, exact hashes, recent verification
BLUE    reviewed update available
AMBER   deliberately pinned or overlay rebase/test due
RED     missing, drifted, shadowed, incompatible, or unsafe
GREY    inventory-only or intentionally non-routable
```

The audit may propose a release/update plan. It never promotes automatically. A weekly scan and an operator-visible digest are the intended later runtime, but no cron is created in Phase 1.

## 10. Visual Skill Control Center

The first view should be generated Markdown/JSON from the manifests and live audit. A later read-only Hermes Desktop plugin may render the same data.

```text
SKILL CONTROL CENTER

Project       Core    Packs             Overlays  Experts        State
JellySSH      1.3.0   Flutter, Data     3         A/S/UI/DB/CQ   GREEN
Home Network  1.2.1   Infra, Security   4         A/S/DB/CQ      AMBER
Portfolio     1.3.0   Data              2         A/DB/CQ        GREEN

Pending
  core-development 1.4.0   3 projects affected
  database-data 1.1.0      2 overlays need compatibility tests
  JellySSH                    exact active state verified
```

Required views:

- fleet overview by project;
- skill × project/profile matrix;
- core → pack → overlay → bundle → profile dependency graph;
- expert triggers and model pairs;
- drift/update/rebase inbox;
- provenance, hashes, last test, promotion and rollback detail;
- project-initialization and `project-doctor` status.

The plugin is a renderer and dry-run launcher only. A “Plan update” action generates a reviewable plan; it does not apply changes. YAML/JSON plus Git history remain authoritative.

## 11. Safety defaults

- Governed profiles use `skills.write_approval: true`.
- Skill writes are reviewed as diffs before promotion.
- Curator consolidation remains off unless separately approved.
- Managed core/pack skills are never direct curator release candidates.
- Shared external directories, if used, are immutable release paths and still hash-checked.
- Local core-name shadowing is a preflight error.
- Missing bundle members are a preflight error despite Hermes's native skip behavior.
- Candidate releases are non-routable.
- Profile changes require fresh sessions.
- Model aliases such as `latest` are not accepted bindings.
- No generic profile, model, bank, or skill fallback is allowed.

## 12. Phase boundary

This is a Phase 1 control-plane design. Implementing `projectctl`, `/project-init`, the generated fleet report, the Desktop plugin, immutable release directories, scheduled audits, or profile materialization requires a later explicitly authorized phase and its own tests and review.
