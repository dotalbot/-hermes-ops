# Project execution routing policy

> **Status:** Operating policy
> **Control plane:** Hermes on Jellyberry
> **Scope:** Every project and work item that Hermes orchestrates

## Decision

Hermes on Jellyberry is always the orchestration and Kanban authority. It is not the rule that one coding engine, model, or host is globally primary.

For every project and work item, select the execution route that best fits the task, approved skills, available host/toolchain, risk, and evidence needs. The selection is a declared, reviewable part of project setup and the individual card—not an informal model preference or a fallback.

Matt Pocock workflows are the default development method:

```text
gather/project context
  → grill-with-docs or equivalent design flow
  → specification
  → dependency-aware tickets
  → implement + TDD
  → independent standards/spec review
  → operator promotion decisions
```

Approved local skills, project overlays, and conditional expert skills extend that method. They do not create workers or select a host by themselves.

## The stable interface

Every route must satisfy this interface, whether it uses a Hermes worker, local Claude, Jellybase Claude, OpenCode, Codex, or another later engine:

```text
Hermes Kanban card
  → declared route preflight
  → bounded execution attempt
  → structured evidence and exact Git state
  → independent review where required
  → Hermes/operator completion decision
```

The engine is an adapter behind that interface. It is never the Kanban assignee, acceptance authority, or release authority.

## Route contract

Project setup declares approved route candidates by role. A selected work item binds one candidate with:

| Contract field | Required meaning |
|---|---|
| Role | Design advisor, researcher, implementation, testing, review, or specialist expert. |
| Hermes owner | The real Jellyberry profile/board identity accountable for the card. |
| Engine and host | The selected tool/program and its actual execution host/account. |
| Model/provider | Exact selected model/provider when the route calls an LLM. |
| Workflow skills | Matt core flow plus approved local/project/expert skills for the role. |
| Workspace | Isolated checkout/worktree or read-only exact-commit materialization. |
| Permissions | Read/write/network/Git/publish limits. |
| Memory | Approved bank and recall/retention policy. |
| Preflight | Route-specific proof of profile, toolchain, checkout, auth, clean state, and model availability. |
| Evidence | Required tests, checks, Git identity, structured result, and independent-review requirements. |
| Failure behavior | Block; no silent engine, model, host, skill, or permission fallback. |

A route change after a card is approved is a material change: write a card comment, rerun the relevant preflight, and obtain any affected review/approval again.

## Role selection

### Design, grilling, and ideas

Use the skills first. `grill-with-docs`, domain modelling, prototypes, and project documentation define the method. Hermes may ask a local Claude session or a remote Claude route for read-only advice, alternative designs, critique, or research when that provides useful independent perspective.

Advice is evidence input. It does not modify the project or replace the final decision, specification, or review gate.

### Implementation

Choose the implementation route per project and ticket:

- a Jellyberry Hermes profile using an SSH backend when the target host/toolchain is available;
- a local coding agent where the project and checkout are local and its route contract permits it;
- a reviewed remote Claude adapter when its constrained isolated route is appropriate;
- an existing OpenCode route while a project remains on that legacy method;
- another approved route created through project setup.

The implementation route must have an isolated checkout, exact allowed scope, tests, commit/push contract, and separate review route. The implementer never accepts its own work.

### Review and experts

Use a fresh reviewer or specialist selected for the required axis: standards/specification, architecture, security, UI, data, performance, or operations. A reviewer must have the exact commit and a suitable read-only interface. Different model families are useful when available, but model difference is not a substitute for a real independent evidence boundary.

## Current examples

| Project/workstream | Orchestration | Execution selection |
|---|---|---|
| JellySSH | Hermes/Kanban on Jellyberry | Select per work item among approved Hermes/Jellybase and Claude routes; bind the exact route on the card. |
| Jellyfish | Hermes/Kanban on Jellyberry | Reinspect its project setup and choose the declared Jellybase route; do not infer a permanent engine from prior work. |
| LogK | Hermes/Kanban on Jellyberry | Current OpenCode/Jellyhome method remains a legacy route until a separate project decision approves migration to Hermes, Claude, or another route. |
| New project | Hermes/Kanban on Jellyberry | Use project setup to declare routes, skills, model/host bindings, and evidence before dispatch. |

## Project-setup requirement

The Skill Control Plane is the mechanism for this policy. A project setup must produce a reviewed manifest that makes the selected execution routes explicit. It should not encode an unreviewed universal default.

For a new route, use a small capability proof before product dispatch:

1. inspect the project, host, account, checkout, and toolchain;
2. materialize approved skills and model/provider binding;
3. prove read-only and failure behavior;
4. prove a bounded no-product-change route invocation where appropriate;
5. review the evidence;
6. add the route candidate to the project manifest;
7. select it explicitly only on matching cards.

## Non-negotiable invariants

- Hermes on Jellyberry owns the board, task state, handoffs, and completion decision.
- Git and repository documents remain product authority.
- Skills define method; profiles/adapters define execution identity; neither substitutes for the other.
- Every route is project- and work-item-scoped.
- Missing route requirements block; there is no silent fallback.
- PRs, merges, releases, signing, deployment, secrets, and privilege stay operator-controlled.
- LogK migration is a separate project decision, not an implication of this policy.
