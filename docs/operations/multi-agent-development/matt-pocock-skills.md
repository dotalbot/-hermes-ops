# Matt Pocock skills in the Jellyberry → Jellybase workflow

## Installation location

Matt Pocock skills are loaded by Hermes on Jellyberry, not copied to Jellybase.

Current copies exist in:

```text
/home/jellybot/.hermes/skills/
/home/jellybot/.hermes/profiles/jellybase_hermes/skills/
```

Jellybase receives only ordinary remote terminal/file operations against application repositories. Its durable `~/.hermes` directory is outside this workflow and must not be synchronized.

## Current managed snapshot

The official source is `https://github.com/mattpocock/skills`. The managed Jellyberry snapshot contains 35 selected skills in both the default and `jellybase_hermes` profiles. Phase 1 verified that all 35 profile copies match each other, 34 match upstream commit `84fdeffd12f2ee307994d1eb6feb48173b6e0502` exactly, and `research` matches that commit plus the local `DESCRIPTION.md` overlay. The exact hashes, target profiles, approval states, and rollback path are recorded in [the JellySSH Phase 1 skill manifest](manifests/jellyssh-phase1-skill-manifest.json).

The upstream repository contained 41 skill directories at that observed commit; the extra upstream skills are not implicitly installed or approved. Some existing Hermes hub lock entries still describe an older revision, so active-content hashes and the Phase 1 manifest govern the pilot until a later controlled promotion refreshes provenance.

### Engineering

```text
ask-matt
code-review
codebase-design
diagnosing-bugs
domain-modeling
grill-with-docs
implement
improve-codebase-architecture
prototype
research
resolving-merge-conflicts
setup-matt-pocock-skills
tdd
to-spec
to-tickets
triage
wayfinder
wizard
```

### Productivity and agent-writing

```text
grill-me
grilling
handoff
teach
to-questionnaire
wait-what
writing-for-agents
```

### General tools

```text
claude-handoff
loop-me
setup-ts-deep-modules
writing-beats
writing-fragments
writing-shape
git-guardrails-claude-code
migrate-to-shoehorn
scaffold-exercises
setup-pre-commit
```

## Normal engineering path

For a normal feature in an existing repository:

```text
setup-matt-pocock-skills   once per repository
→ grill-with-docs          design with codebase context
→ to-spec                  durable feature specification
→ to-tickets               small, dependency-aware vertical slices
→ implement + tdd          one fresh implementation worker per ticket
→ code-review              standards and spec review of the exact diff
```

Use `ask-matt` when uncertain which flow fits. Use `grill-me` only when no codebase exists; use `grill-with-docs` for repository work.

Use `wayfinder` only for genuinely large, unclear work that cannot be settled in a normal feature-design session. Use `diagnosing-bugs` for a hard defect or regression, not a routine feature request.

## How to load skills

### Interactive design session

Run from Jellyberry:

```bash
hermes --profile <approved-design-profile> chat -s grill-with-docs
```

State the exact remote repository path at the start of the session:

```text
Repository: /home/jellydev/dev_projects/<repo>
```

Use an interactive session for `setup-matt-pocock-skills`, `grill-with-docs`, `to-spec`, and `to-tickets` because they require ongoing design context and may ask operator questions.

### Kanban worker card

Force-load only the skills required by a bounded card:

```bash
hermes kanban --board <project-board> create "Implement <ticket>" \
  --assignee <approved-project-profile> \
  --skill implement \
  --skill tdd \
  --skill code-review \
  --body "Repository: /home/jellydev/dev_projects/<repo>
Branch: feat/<feature>
Ticket: <issue URL or local ticket path>"
```

`--skill` is repeatable. The card must still describe the exact task; a skill is a workflow aid, not a replacement for a complete task brief.

## Controlled update procedure

Phase 1 produced a proposed manifest containing each managed skill's source, pinned commit, integrity/provenance record, local overlay path, target profiles, compatibility state, promotion state, and rollback location. Phase 1 does not authorize installing, updating, synchronizing, or promoting skills; those actions remain gated on acceptance of the Phase 1 report and the Phase 2 isolated profile tests.

After that gate, use the lifecycle defined by V3 and the [Skill Control Plane](skill-control-plane-and-project-initialization.md): inventory the active copy, fetch upstream into an isolated candidate area, diff it against upstream and local overlays, run security and compatibility review, test it in an isolated profile/session, obtain operator approval, promote it only to the named profiles, and retain the rollback copy. Never run a global install/update command directly against active skills, and never overwrite local expert or project assets silently.

Core procedures are immutable versioned releases; optional database/data, Flutter, security, and other capability packs are globally governed but enabled per project; project-only procedures use project-prefixed overlay names in the project repository. Native Hermes bundles are convenience aliases and skip missing members, so Kanban preflight must resolve and hash-check every member before dispatch.

Treat install-scanner output as a signal, not proof: broad workflow skills can mention subagents, Git, or long-running coordination and produce heuristic findings.

## Hermes compatibility

Hermes reserves `/handoff` for its built-in session transport. For document-based context transfer in this workflow, use `/context-handoff` instead.
