# Matt Pocock skills in the Jellyberry → Jellybase workflow

## Installation location

Matt Pocock skills are loaded by Hermes on Jellyberry, not copied to Jellybase.

Current copies exist in:

```text
/home/jellybot/.hermes/skills/
/home/jellybot/.hermes/profiles/jellybase_hermes/skills/
```

Jellybase receives only ordinary remote terminal/file operations against application repositories. Its durable `~/.hermes` directory is outside this workflow and must not be synchronized.

## Current upstream snapshot

The official source is `https://github.com/mattpocock/skills`. The current full collection contains 35 skills. The Jellybase worker profile has a matching copy of this collection.

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

Phase 0 does not authorize fetching, installing, updating, synchronizing, or promoting skills. Phase 1 must first approve a manifest containing each skill's source, pinned version or commit, integrity/provenance record, local overlay path, target profiles, compatibility evidence, promotion state, and rollback location.

After that gate, use the lifecycle defined by V3: inventory the active copy, fetch upstream into an isolated candidate area, diff it against upstream and local overlays, run security and compatibility review, test it in an isolated profile/session, obtain operator approval, promote it only to the named profiles, and retain the rollback copy. Never run a global install/update command directly against active skills, and never overwrite local expert or project assets silently.

Treat install-scanner output as a signal, not proof: broad workflow skills can mention subagents, Git, or long-running coordination and produce heuristic findings.

## Hermes compatibility

Hermes reserves `/handoff` for its built-in session transport. For document-based context transfer in this workflow, use `/context-handoff` instead.
