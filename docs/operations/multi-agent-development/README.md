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

1. [Jellyberry Kanban orchestration design V2](jellyberry-kanban-orchestration-design-v2.md) — expanded decision candidate covering the live Hermes setup and Hindsight banks
2. [Jellyberry Kanban orchestration design V1](jellyberry-kanban-orchestration-design.md) — preserved original decision candidate
3. [Architecture and safety boundaries](architecture-and-safety-boundaries.md)
4. [Feature lifecycle](feature-lifecycle.md)
5. [Matt Pocock skills](matt-pocock-skills.md)
6. [Kanban card templates](kanban-card-templates.md)
7. [Operator checklist](operator-checklist.md)

## Quick start for a new feature

1. Identify the Git remote or existing Jellybase repository path.
2. Use a dedicated development clone owned by `jellydev`, normally `/home/jellydev/src/<repo>`.
3. Create a feature branch such as `feat/report-csv-export`; never edit `main` for normal repository work.
4. Run the one-time Matt workflow setup for a repository if it is not already configured.
5. Design with `grill-with-docs`, then produce a spec and dependency-aware tickets.
6. Create a dedicated board for the project; do not mix unrelated application work into `Spawner`.
7. Dispatch one bounded implementation card at a time to `jellybase_hermes`.
8. Require tests, independent review, commit, and push before calling a feature ready.
9. Create a pull request or merge only after explicit operator approval.

## Completion standard

A feature is ready for human decision only when its feature branch is pushed and all of the following exist:

- a design/spec and accepted scope;
- an implementation ticket with recorded acceptance criteria;
- relevant test and verification output;
- an independent diff/spec review;
- current documentation where the behaviour, setup, API, or operations changed;
- the branch name and commit recorded on the Kanban card.

## Scope and change control

This guide describes an operating approach. It does not authorize production deployment, privileged operations, opening pull requests, or merging branches. Those remain explicit operator decisions.
