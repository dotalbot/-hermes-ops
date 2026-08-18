# Jellyberry → Jellybase multi-agent development

This folder is the operator guide for developing repository features with Hermes running on Jellyberry and code work executed on Jellybase.

## Purpose

Use this approach when a feature needs a durable Git branch, a clear design, bounded remote execution, tests, review, and an auditable result.

The control plane and the code workspace are deliberately separate:

- Jellyberry hosts Hermes profiles, skills, Kanban boards, task logs, and coordination.
- Jellybase hosts non-production development clones, feature branches, builds, tests, and Git commits.
- The Git remote is the source of truth shared between machines and people.
- A Kanban board is the audit trail and work queue; it is not the source-code workspace.

## Read in this order

1. [Jellyberry Kanban orchestration design V3](jellyberry-kanban-orchestration-design-v3.md) — approved design using JellySSH for the Jellybase pilot, deferring LogK to a later Jellyhome/OpenCode lane, and governing skills, experts, profiles, and evidence
2. [JellySSH Phase 3.5 consolidation report](../../reports/jellyssh-phase35-consolidation-2026-08-17.md) — current board/Git reconciliation after BUG-011; read this before interpreting old cards or Phase 2 status projections
3. [Jellyberry Kanban orchestration design V2](jellyberry-kanban-orchestration-design-v2.md) — preserved expanded candidate covering the live Hermes setup and Hindsight banks
4. [Jellyberry Kanban orchestration design V1](jellyberry-kanban-orchestration-design.md) — preserved original decision candidate
5. [Architecture and safety boundaries](architecture-and-safety-boundaries.md)
6. [Feature lifecycle](feature-lifecycle.md)
7. [Project execution routing policy](project-execution-routing-policy.md) — generic project/work-item selection of skills, agent, host, model, and evidence route while Hermes remains the control plane
8. [Matt Pocock skills](matt-pocock-skills.md)
9. [Skill Control Plane and project initialization](skill-control-plane-and-project-initialization.md)
10. [Kanban card templates](kanban-card-templates.md)
11. [JellySSH Claude Code adapter](jellyssh-claude-code-adapter.md) — project-selectable bounded implementation or advisory-review lane through the dedicated `jellyclaude@jellybase` account
12. [Operator checklist](operator-checklist.md)

## Quick start for a new feature

1. Identify the Git remote and the intended Jellyberry/Jellybase repository paths.
2. Use a dedicated development clone owned by `jellydev`, normally `/home/jellydev/dev_projects/<repo>`.
3. Create a feature branch such as `feat/report-csv-export`; never edit `main` for normal repository work.
4. Run the proposed `/project-init` scan/plan dry run and review the core release, capability packs, project overlays, profiles, models, banks, workspaces, and expert triggers before applying setup.
5. Inventory and approve the repository's workflow skills and expert bindings before dispatch.
6. Design with `grill-with-docs`, then produce a spec and dependency-aware tickets.
7. Run required architecture, security, UI, and database/data expert reviews before implementation.
8. Create a dedicated board for the project; do not mix application work into `spawner`.
9. Dispatch one bounded implementation card at a time to the approved project-specific profile.
   That Hermes profile may invoke the reviewed Claude adapter; Claude Code is never itself the Kanban assignee or result authority.
10. Require tests, independent review, commit evidence, and the project's push gate before calling a feature ready.
11. Create a pull request or merge only after explicit operator approval.

## Completion standard

A feature is ready for human decision only when its exact commit exists, its push state is recorded, the project's push policy is satisfied, and all of the following exist:

- a design/spec and accepted scope;
- an implementation ticket with recorded acceptance criteria;
- relevant test and verification output;
- an independent diff/spec review;
- current documentation where the behaviour, setup, API, or operations changed;
- the branch name and commit recorded on the Kanban card.

## Scope and change control

This guide describes an operating approach. It does not authorize production deployment, privileged operations, opening pull requests, or merging branches. Those remain explicit operator decisions.
