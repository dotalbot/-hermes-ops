# Jellyberry Kanban orchestration design

> **Status:** Decision candidate for operator review  
> **Implementation state:** Proposed; this document does not authorize profile, board, dispatcher, repository, deployment, or privilege changes.

## Executive decision

Adopt a **Kanban-centred, repository-backed development system** with these boundaries:

1. Jellyberry is the single orchestration control plane.
2. Hermes Kanban owns live execution state, dependencies, assignees, attempts, blocked reasons, and handoffs.
3. Git repositories own specifications, ticket definitions, decisions, implementation, tests, and durable review evidence.
4. A Kanban assignee is always a real Hermes profile on Jellyberry.
5. Matt Pocock skills define **how** an assigned profile performs a development phase.
6. Remote Hermes, OpenCode, Claude Code, or other execution engines sit behind a Jellyberry Hermes profile or reviewed adapter.
7. Start with manual decomposition and one executable card at a time. Add automation only after a complete implementation-and-review pipeline is repeatable.

The governing rule is:

> **The board owns the task. A worker owns one execution attempt. Git and repository documents preserve the durable result.**

---

## 1. System architecture

### 1.1 Control plane and execution plane

```mermaid
flowchart LR
    U[Operator] --> D[Hermes default profile<br/>Jellyberry]
    D --> K[(Hermes Kanban<br/>Jellyberry-local boards)]

    subgraph CP[Control plane: Jellyberry]
        K --> X[Local dispatcher]
        X --> P1[jellybase_hermes]
        X --> P2[homenetworkworker]
        X --> P3[jellybase_reviewer<br/>proposed]
        X --> P4[logk_opencode<br/>possible later]
    end

    P1 -->|SSH-backed tools| JB[Jellybase development checkout]
    P2 -->|bounded operations| HN[Home-network targets]
    P3 -->|fresh read-only context| JR[Review checkout or worktree]
    P4 -.->|reviewed adapter| JH[OpenCode on Jellyhome]

    JB --> G[(Git remote)]
    JR --> G
    JH --> G
    G --> D
```

The dispatcher, board database, card claims, heartbeats, logs, and worker processes remain local to Jellyberry. A worker profile may execute tools through SSH, but remote hosts do not become members of one shared SQLite board.

### 1.2 Compact mental model

```text
Operator
  │
  ▼
Hermes default profile
  │ creates/approves cards
  ▼
Jellyberry Kanban board
  │ dispatches a real local profile
  ▼
Hermes worker profile
  │ may execute locally, over SSH, or through an adapter
  ▼
Git branch/worktree + repository evidence
  │
  ▼
Independent review and operator decision
```

---

## 2. Authority and ownership

Each concern has one authoritative home. Do not duplicate live state across systems.

```mermaid
flowchart TB
    S[Feature or operational goal]
    S --> B[Kanban<br/>execution authority]
    S --> R[Repository files<br/>requirements authority]
    S --> G[Git<br/>change-history authority]
    S --> O[Operator<br/>approval authority]

    B --> B1[status and assignee]
    B --> B2[dependencies and attempts]
    B --> B3[blocked reasons and comments]

    R --> R1[specifications and tickets]
    R --> R2[ADRs and domain context]
    R --> R3[plans and review reports]

    G --> G1[branches and commits]
    G --> G2[tests and implementation]
    G --> G3[rollback and audit trail]

    O --> O1[scope approval]
    O --> O2[privilege and secret decisions]
    O --> O3[PR, merge, release, deployment]
```

### 2.1 Hermes Kanban owns

- Current task status.
- Current assignee.
- Dependency edges.
- Execution attempts, retries, and worker logs.
- Blocked reasons and human responses.
- Concise handoff comments.
- Reported branch, commit, tests, and review outcome.

### 2.2 Repository files own

Recommended convention, adapted to each repository's existing structure:

```text
CONTEXT.md

docs/
├── adr/
├── specs/
├── tickets/
├── plans/
├── reviews/
├── runbooks/
└── agents/
```

These files preserve:

- Domain language and project constraints.
- Architectural decisions.
- Feature specifications and non-goals.
- Durable ticket definitions and acceptance criteria.
- Test and verification plans.
- Independent review reports where the decision merits a durable record.
- Project-specific agent and operator conventions.

### 2.3 Git owns

- Code and documentation.
- Branches, worktrees, and commits.
- Durable change history.
- Rollback points.
- Pull requests where they add value.

### 2.4 Operator owns

- Scope and product decisions.
- Moving selected work into executable state.
- Sudo, credentials, secrets, and production approvals.
- Pull-request creation, merge, release, and deployment decisions.

### 2.5 Avoid dual-source drift

Do not mirror live Kanban status into Markdown checkboxes.

Example:

```text
docs/tickets/export/03-stream-results.md
    └── defines the work and acceptance criteria

Hermes Kanban card t_...
    └── owns todo / ready / running / blocked / done
```

Kanban SQLite data is protected through the separate `~/.hermes` backup practice. Live board databases should not be copied into individual project repositories.

---

## 3. Board topology

Use one board per persistent repository or durable operational workstream, not one board per idea.

```mermaid
flowchart LR
    K[(Jellyberry Kanban)]
    K --> CHI[continuous-hermes-improvement]
    K --> LOGK[logk<br/>planned]
    K --> HN[home-network]
    K --> PI[portfolio]
    K --> PL[3dprint-loader]
    K --> SP[spawner<br/>transport validation only]
    K --> DEF[default<br/>small ad-hoc work]

    CHI --> R1["/home/jellybot/dev_projects/hermes-ops"]
    LOGK --> R2["/home/jellybot/dev_projects/logk"]
    HN --> R3["/home/jellybot/dev_projects/home-network"]
    PI --> R4["/home/jellybot/dev_projects/portfolio-intel"]
```

### 3.1 Recommended board decisions

- Keep `continuous-hermes-improvement` as the Hermes control-plane and infrastructure board. Do not create a duplicate `hermes-infra` board.
- Add `logk` for LogK development.
- Keep `home-network` for homelab and network work.
- Keep `portfolio` for the existing portfolio workstream.
- Keep `3dprint-loader` for that repository.
- Keep `spawner` only for transport, profile, and dispatch acceptance tests.
- Reserve `default` for bounded ad-hoc work that does not justify a persistent board.
- Add another board only when the workstream has independent scope, backlog, repository context, and lifecycle.

### 3.2 Cross-board work

Hermes does not provide cross-board dependency edges. Coordinate cross-project work with:

- A parent orchestration record in one selected board.
- Links to durable specifications in the affected repositories.
- Explicit card references in comments.
- A final operator reconciliation step.

Do not pretend independent boards form one distributed dependency graph.

---

## 4. Current live-state corrections

These corrections are prerequisites, not approved changes merely because they appear in this document.

### 4.1 Stale board project directories

The directory migration left these board metadata paths behind:

```text
Current board metadata                  Required path
─────────────────────────────────────   ───────────────────────────────────────────────
/home/jellybot/hermes-ops               /home/jellybot/dev_projects/hermes-ops
/home/jellybot/home-network             /home/jellybot/dev_projects/home-network
/home/jellybot/portfolio-intel          /home/jellybot/dev_projects/portfolio-intel
```

The current paths no longer exist and must be corrected before dispatching repository work.

### 4.2 Invalid ready-card assignee

A ready card currently exists on `continuous-hermes-improvement` with:

```text
Title:    Check Docker health on Jellybase
ID:       t_dbcf7e2c
Assignee: jellybase
Status:   ready
```

`jellybase` is not an installed profile. The real execution profile is `jellybase_hermes`. The card must be reassigned, blocked, archived, or otherwise reconciled before normal dispatch resumes.

### 4.3 Current automation is too aggressive for the pilot

Observed configuration:

```yaml
kanban:
  auto_decompose: true
  auto_decompose_per_tick: 3
  orchestrator_profile: jellybase_hermes
  default_assignee: jellybase_hermes
  max_in_progress: 2
  max_spawn: 2
```

Recommended pilot policy:

```yaml
kanban:
  auto_decompose: false
  orchestrator_profile: ""
  default_assignee: ""
  max_in_progress: 1
  max_spawn: 1
```

Reasons:

- `jellybase_hermes` is an implementation worker, not a restricted orchestration profile.
- Automatic decomposition can create and route work before the profile and skill map is mature.
- Concurrency limits apply per board, so several active boards can exceed the intended host-wide load.
- Explicit assignees make routing auditable.
- Moving only operator-approved cards to `ready` provides the initial execution gate.

### 4.4 Host path convention

Use the same home-relative convention on each agent host, while allowing usernames to differ:

```text
Jellyberry: /home/jellybot/dev_projects/<repo>
Jellybase:  /home/jellydev/dev_projects/<repo>
Jellyhome:  /home/jellydev/dev_projects/<repo>
```

Existing multi-agent documents still reference `/home/jellydev/src/<repo>`. Reconcile those references before using the new convention operationally.

A Jellyberry Desktop Project path must remain visible to Jellyberry. A remote execution path is separate and belongs in the card or routing manifest.

---

## 5. Profiles, agents, and specialists

### 5.1 Terms

```text
Profile       Stable Hermes identity and configuration on Jellyberry
Agent engine  Hermes, OpenCode, Claude Code, Codex, or another executable
Specialist    Stable domain or safety role represented by a profile or skill
Skill         Procedure/context loaded for one task or profile
Host          Machine on which tools ultimately execute
Attempt       One worker run against one Kanban card
```

A profile is not automatically a machine, OS user, or security sandbox. Its real authority is determined by the Jellyberry Linux account and the configured tool/backend boundaries.

### 5.2 Initial profile roster

#### `default`

Operator-facing control profile:

- Discuss requirements and decisions.
- Run interactive design flows.
- Create and inspect cards.
- Coordinate review and report results.
- Avoid unattended implementation when acting as orchestrator.

#### `jellybase_hermes`

Generic remote implementation worker:

- Uses the reviewed Jellybase SSH backend.
- Operates as non-privileged `jellydev`.
- Inspects repositories, changes code, runs tests, commits, and pushes only the specified branch.
- Blocks when sudo, credentials, production access, or unclear local changes are encountered.
- Uses the worker-specific memory policy rather than retaining transient task state as durable memory.

#### `homenetworkworker`

Home-network specialist:

- Handles bounded homelab documentation, monitoring, backups, runbooks, and approved maintenance.
- Carries domain-specific context and safety rules.
- Should receive Matt development skills only when it is expected to perform software-development cards.

#### `jellybase_reviewer` — proposed

Independent review specialist:

- Fresh profile and session context.
- Exact branch and commit supplied on the card.
- Separate checkout or worktree.
- Read-only review contract.
- No edit, commit, push, PR, merge, sudo, or deployment.
- Reports `PASS`, `BLOCKED`, or numbered findings.

#### `logk_opencode` — possible later

External-agent adapter profile:

- Is a real Jellyberry Hermes profile and therefore a valid Kanban assignee.
- Invokes OpenCode on Jellyhome through a reviewed adapter.
- Has a separate LogK checkout or worktree.
- Carries the `opencode` skill plus approved Matt workflow skills.
- Returns structured results and completes or blocks the card through Hermes.

### 5.3 When a new profile is justified

Create a profile only when at least one stable boundary differs:

- Host or SSH backend.
- OS user or credentials.
- Tool access.
- Memory bank and retention policy.
- Safety contract.
- Durable domain role.
- Independent-review boundary.

Use task-pinned skills when only the procedure changes. Avoid creating profiles named after every transient phase.

---

## 6. Matt Pocock skills as the development engine

### 6.1 Routing model

```mermaid
flowchart LR
    C[Kanban card] --> A[Assignee profile<br/>who and where]
    C --> S[Task-pinned skills<br/>how]
    C --> R[Repository references<br/>what and why]

    A --> W[Hermes worker attempt]
    S --> W
    R --> W

    W --> E[Tests, branch, commit,<br/>summary and evidence]
    E --> K[(Kanban result/comment)]
    E --> G[(Git repository)]
```

The key mechanism is:

```text
Kanban card
├── assignee = who and where executes
└── skills   = how the work is performed
```

A skill does not select or launch an external agent by itself. The orchestrator selects a real profile, and the card pins skills already installed for that profile.

### 6.2 Native task skill pinning

From an orchestrator:

```text
kanban_create(
    title="Implement structured export",
    assignee="jellybase_hermes",
    skills=["implement", "tdd"],
)
```

From the CLI:

```bash
hermes kanban --board logk create \
  "Implement structured export" \
  --assignee jellybase_hermes \
  --skill implement \
  --skill tdd
```

The dispatcher loads the listed skills when it starts the worker.

### 6.3 Skill availability constraint

The named skills must already be installed for the assignee profile.

Current availability relevant to this design:

- `default`: required Matt engineering skills are available.
- `jellybase_hermes`: required Matt engineering skills are available.
- `homenetworkworker`: Matt engineering skills are not currently installed.

A task assigned to `homenetworkworker` with `--skill implement` would therefore fail before useful work began.

### 6.4 Three skill layers

```mermaid
flowchart TB
    P[Profile baseline]
    T[Task phase skill]
    D[Project/domain overlay]
    W[Worker behavior]

    P --> W
    T --> W
    D --> W

    P1[Host, privilege, memory,<br/>tool and safety rules] --> P
    T1[implement, tdd, code-review,<br/>diagnosing-bugs] --> T
    D1[Repository conventions,<br/>domain procedures, specialist rules] --> D
```

#### Profile baseline

Stable safety and execution identity:

- SSH backend.
- No-sudo rule.
- Memory policy.
- Tool restrictions.
- Domain scope.

#### Task phase skill

Selected per card:

- `implement`
- `tdd`
- `code-review`
- `diagnosing-bugs`
- other bounded workflow skills

#### Project/domain overlay

Use repository context first:

- `AGENTS.md`
- `CLAUDE.md`
- `CONTEXT.md`
- `docs/agents/`
- `docs/adr/`

Create a project skill only when the project has a reusable procedure that is not adequately expressed by repository documentation. Install that skill on every profile expected to receive it.

### 6.5 Proposed bridge skill

After this architecture is approved, create a small `matt-kanban-development` orchestration skill for the operator/default profile.

It should:

1. Discover real profiles and their installed skills.
2. Resolve the project board and repository mappings.
3. Require an approved specification or explicitly invoke the interactive design flow.
4. Convert durable tickets into Kanban cards.
5. Pin phase skills explicitly.
6. Assign only real profiles.
7. Construct dependency edges.
8. Add an independent review and final acceptance gate.
9. Stop after creating the graph; it must not implement the cards itself.

Do not fork or rewrite the underlying Matt skills. The bridge should compose them and encode the local Kanban conventions.

---

## 7. Development lifecycle

### 7.1 Interactive and unattended boundaries

Interactive phases need user dialogue and should normally run in the operator-facing session:

```text
setup-matt-pocock-skills  # once per repository
        ↓
grill-with-docs
        ↓
to-spec
        ↓
to-tickets
```

Unattended worker phases operate on approved, bounded cards:

```text
implement + tdd
        ↓
code-review
        ↓
fix card if required
        ↓
fresh code-review
        ↓
final acceptance
```

### 7.2 Dependency graph

Hermes dependency links mean a child waits for its parent to become `done`. They are execution edges, not a general visual hierarchy.

```mermaid
flowchart LR
    IDEA[Interactive design] --> SPEC[Publish durable spec]
    SPEC --> T1[Implementation ticket A]
    SPEC --> T2[Implementation ticket B]
    T1 --> R1[Independent review A]
    T2 --> R2[Independent review B]
    R1 --> V[Integration verification]
    R2 --> V
    V --> A[Feature acceptance]
    A --> H{Operator decision}
    H -->|approved| PR[PR, merge, release,<br/>or deployment as separately authorized]
    H -->|changes needed| F[New fix ticket]
    F --> RR[Fresh review]
    RR --> A
```

A feature umbrella card can index the specification and related card IDs, but it should not be used as a blocking dependency parent unless completing it is intentionally the prerequisite for all children.

### 7.3 Implementation card

```text
Assignee: jellybase_hermes
Skills: implement, tdd

Required references:
- Board and repository.
- Local and remote repository paths.
- Exact branch.
- Specification path.
- Ticket path.
- Acceptance criteria.
- Required tests and checks.
- Final report fields.
```

The implementation worker performs a self-review, but that does not replace independent review.

### 7.4 Hard-bug card

```text
Assignee: jellybase_hermes
Skills: diagnosing-bugs, tdd
```

The card should include the observed failure, reproduction command, expected behavior, scope boundary, and stop conditions.

### 7.5 Independent review card

```text
Assignee: jellybase_reviewer
Skills: code-review
Parents: implementation card

Read-only inputs:
- Exact pushed branch.
- Expected commit.
- Specification and ticket.
- Required non-mutating checks.
```

### 7.6 Review-fix loop

Create a new fix card for real findings. Do not simply rerun or reassign the original implementation card.

```mermaid
flowchart LR
    I[Implementation done] --> R[Independent review]
    R -->|PASS| A[Acceptance]
    R -->|findings| F[New fix card]
    F --> R2[Fresh review card]
    R2 -->|PASS| A
    R2 -->|findings| F2[Another bounded fix card]
```

### 7.7 Meaning of `done`

A stage card may be `done` when that stage has produced and verified its declared result. It does not mean the whole feature is approved.

The final acceptance card should require:

- Required implementation cards completed.
- Focused and project-level checks passed.
- `git diff --check` passed where applicable.
- Branch and exact commit recorded.
- Independent review passed.
- Review fixes received a fresh review.
- Required repository documents exist.
- The operator's approval requirements are satisfied.

---

## 8. Remote execution boundary

### 8.1 Supported pattern

```mermaid
sequenceDiagram
    actor U as Operator
    participant D as Default profile
    participant K as Jellyberry Kanban
    participant X as Jellyberry dispatcher
    participant P as Assigned Hermes profile
    participant H as Remote host or adapter
    participant G as Git remote

    U->>D: Approve bounded ticket
    D->>K: Create card with assignee and skills
    U->>K: Move selected card to ready
    X->>K: Claim card
    X->>P: Start local Hermes worker
    P->>H: Execute through SSH or reviewed adapter
    H->>G: Push specified branch/commit
    H-->>P: Tests and execution result
    P->>K: Comment with evidence
    P->>K: Complete or block card
    K-->>D: Durable state and result
    D-->>U: Report verified outcome
```

### 8.2 Why direct remote assignees are rejected

OpenCode, Claude Code, Codex, and a separate Hermes installation do not automatically become Hermes profiles.

A separate Hermes installation on another host has its own:

- Profiles.
- Sessions.
- Gateway.
- Kanban database.
- Cron jobs.
- Local state.

It does not automatically join Jellyberry's board fleet.

### 8.3 External-agent adapter

The supported later pattern is:

```text
Jellyberry Kanban
  → local Hermes adapter profile
  → SSH or authenticated agent service
  → remote OpenCode/Claude/Codex process
  → result returned to local Hermes profile
  → local profile updates the Jellyberry card
```

The adapter must provide:

- Stable invocation.
- Explicit repository and branch.
- Timeout and cancellation.
- Liveness and failure reporting.
- Structured result extraction.
- No secret values in logs or card comments.
- One writer per checkout/worktree.

Tmux may be an implementation detail for an external long-running CLI. It is not the primary state store, and it is not needed to replace the native Kanban worker lifecycle.

---

## 9. Repository and workspace policy

### 9.1 Project mapping

Maintain a reviewed mapping rather than assuming one absolute path exists on every host.

Conceptual example:

```yaml
projects:
  logk:
    board: logk
    jellyberry_repo: /home/jellybot/dev_projects/logk
    execution_targets:
      jellybase: /home/jellydev/dev_projects/logk
      jellyhome: /home/jellydev/dev_projects/logk
    durable_paths:
      specs: docs/specs
      tickets: docs/tickets
      decisions: docs/adr
      reviews: docs/reviews
```

This is a design example, not an implemented configuration file.

### 9.2 Workspace rules

- A Desktop Project path must exist on Jellyberry for a Jellyberry-backed session.
- A remote execution profile needs a repository checkout on its execution host.
- Do not use Hermes local Kanban worktree mode for `jellybase_hermes` until remote workspace mapping is deliberately implemented and verified.
- State the exact remote path and branch in every remote implementation card.
- Use one editing worker per checkout and branch.
- Use separate worktrees or clones for independent review and parallel work.
- Preserve existing uncommitted and untracked files; block rather than overwrite unknown work.

### 9.3 Durable card references

Each implementation or review card should link to repository files instead of carrying a giant duplicated prompt:

```text
Specification: docs/specs/structured-export.md
Ticket:        docs/tickets/structured-export/03-stream-results.md
Decision:      docs/adr/0012-export-format.md
Review output: docs/reviews/structured-export-commit-<short-sha>.md
```

Comments should summarize the handoff and record exact evidence, not replace the durable artifacts.

---

## 10. Routing policy

### 10.1 Deterministic selection order

```mermaid
flowchart TB
    T[Read card metadata] --> P[Resolve project and repository policy]
    P --> F[Select phase skills]
    F --> D[Add project/domain overlay]
    D --> C[Filter profiles by capability and host]
    C --> S[Select one real assignee]
    S --> V{Skills installed<br/>for assignee?}
    V -->|no| B[Block before dispatch]
    V -->|yes| W{Workspace and branch<br/>safe?}
    W -->|no| B
    W -->|yes| R[Move approved card to ready]
    R --> E[One worker attempt]
```

### 10.2 Suggested routes

```yaml
routes:
  interactive_design:
    profile: default
    skills: [grill-with-docs]

  specification:
    profile: default
    skills: [to-spec]

  ticketing:
    profile: default
    skills: [to-tickets]

  application_implementation:
    profile: jellybase_hermes
    skills: [implement, tdd]

  hard_bug:
    profile: jellybase_hermes
    skills: [diagnosing-bugs, tdd]

  home_network_operations:
    profile: homenetworkworker
    skills: []

  independent_review:
    profile: jellybase_reviewer
    skills: [code-review]
```

This is the proposed policy, not current runtime configuration.

### 10.3 Profile descriptions

Hermes's decomposer uses profile descriptions for routing. Keep descriptions short, capability-based, and explicit about boundaries.

Do not enable automatic decomposition until:

- Every routable profile exists.
- Descriptions are reviewed.
- Required skills are installed on those profiles.
- The routing policy has passed manual pilot cards.
- Unknown-profile and missing-skill behavior is proven fail-closed.

---

## 11. Critical review of the source proposal

### 11.1 Accepted

- Jellyberry as the single control plane.
- Kanban as the central execution queue.
- One board per durable project or workstream.
- The board owns the task; the worker owns an attempt.
- Git as the code handoff and durable change history.
- Persistent comments and structured result summaries.
- Explicit blocked states for human decisions.
- Separate implementation and review stages.
- Role- and capability-based routing.
- Incremental rollout before autonomous pipelines.
- The principle of **jobs + Git + results**, rather than agents holding endless unstructured conversations.

### 11.2 Modified

#### Agent engines as assignees

The assignee must be a real Hermes profile. The underlying engine is an implementation detail behind that profile.

```text
Correct:
  assignee = logk_opencode
  engine   = OpenCode on Jellyhome

Incorrect:
  assignee = arbitrary remote OpenCode process
```

#### Remote-host semantics

The board remains local to Jellyberry. Remote tools are reached from a local Hermes worker through SSH or an adapter.

#### Comments as agent communication

Comments are concise handoff and evidence records. Specifications, detailed tickets, decisions, and substantial review reports belong in repository files.

#### Shared project paths

Standardize `~/dev_projects/<repo>` conceptually, but keep an explicit host mapping because usernames and filesystems differ.

#### Feature parent cards

Dependency links are execution prerequisites, not merely hierarchy. Use a final acceptance fan-in card rather than assuming an umbrella parent will automatically represent feature completion.

#### `done` semantics

A stage card being done proves only that stage's declared completion criteria. Feature acceptance requires the full gate.

### 11.3 Rejected for the initial system

- A custom job registry duplicating Kanban IDs, state, logs, retries, and results.
- Direct arbitrary SSH strings as the public orchestration interface.
- Tmux as the primary state store.
- Automatic planner → developer → reviewer pipelines before a manual pilot.
- Naming profiles after transient phases when a task-pinned skill is sufficient.
- Treating independent host-local Kanban databases as one distributed board.
- Assuming a card's `done` state is independent proof of a branch, commit, push, or test result.
- Automatic PR creation, merging, release, deployment, sudo, or secret use.

---

## 12. Safety and failure handling

### 12.1 Required safety rules

- No sudo by default for development workers.
- Treat Docker access as privileged because it is effectively root-equivalent.
- Keep credentials out of card bodies, comments, result files, and repository documents.
- Use dedicated development checkouts, not production runtime trees.
- Preserve unknown local changes and block for operator direction.
- Permit only the repository, branch, host, and operations named by the card.
- Require explicit approval for PRs, merge, release, deployment, privileged changes, or new credentials.

### 12.2 Card lifecycle on failure

```mermaid
stateDiagram-v2
    [*] --> Todo
    Todo --> Ready: operator approves
    Ready --> Running: dispatcher claims
    Running --> Done: evidence satisfies card
    Running --> Blocked: decision or prerequisite missing
    Running --> Ready: safe retry or reclaim
    Blocked --> Ready: operator resolves blocker
    Done --> [*]
```

A retry is a new attempt against the same task when scope and acceptance criteria remain unchanged. Create a new card when the work itself changes, such as a review finding requiring a bounded fix.

### 12.3 Evidence required from a worker

A completion comment or result should include:

```text
Status: completed | blocked
Repository:
Branch:
Commit:
Push result:
Files changed:
Checks run:
Exact results:
Review required:
Durable artifact paths:
Limitations or blockers:
```

The operator or reviewer must independently verify material claims when promotion, release, comparison, or deployment depends on them. Card state alone is not proof.

---

## 13. Phased implementation plan

### Phase 0 — repair the current control plane

Actions:

1. Correct the three stale board project directories.
2. Reconcile the invalid ready-card assignee.
3. Disable automatic decomposition for the pilot.
4. Reduce per-board concurrency to one.
5. Remove `jellybase_hermes` as the automatic orchestration owner/fallback.
6. Reconcile `/home/jellydev/src` documentation with the `~/dev_projects` convention.

Completion criteria:

- Every active board points to an existing intended path or intentionally has no default project directory.
- Every ready/running card names an installed profile.
- No card is dispatched automatically during the manual pilot.
- One approved card results in at most one active worker on its board.

### Phase 1 — finalize the repository contract

Actions:

1. Update this multi-agent guide to make the authority boundaries normative.
2. Define the repository artifact convention.
3. Configure each participating repository's Matt workflow.
4. Use a custom tracker policy: Hermes Kanban for execution state plus versioned repository files for durable specifications and tickets.
5. Create the `matt-kanban-development` bridge skill after approval.

Completion criteria:

- Each pilot repository contains or links to its project context, specification path, ticket path, and agent rules.
- The bridge skill creates valid cards only for installed profiles and installed skills.
- The skill stops after orchestration and does not implement work itself.

### Phase 2 — introduce independent review

Actions:

1. Create `jellybase_reviewer`.
2. Give it a read-only review SOUL and narrowly scoped tools.
3. Provide a separate checkout or worktree.
4. Install `code-review` and required repository context.
5. Test it on an exact commit without edits.

Completion criteria:

- The reviewer cannot accidentally share the implementer's active working tree.
- It reports against an exact branch and commit.
- It produces `PASS`, `BLOCKED`, or numbered findings.
- A fresh rereview is used after fixes.

### Phase 3 — pilot LogK through native Hermes profiles

Actions:

1. Create the `logk` board.
2. Associate it with `/home/jellybot/dev_projects/logk` for Jellyberry-visible context.
3. Prepare the Jellybase checkout under the agreed remote root.
4. Select one small, reversible feature or bug.
5. Run the interactive Matt design/spec/ticket flow.
6. Create one implementation card assigned to `jellybase_hermes` with explicit skills.
7. Move only that card to `ready`.
8. Create and run one dependent reviewer card.
9. Verify branch, commit, push, tests, review, comments, and durable documents.
10. Stop before PR creation or merge.

Completion criteria:

- One approved ticket travels from repository specification to implementation, independent review, and final acceptance.
- Failure, block, and retry behavior are understood.
- No unrelated checkout or branch is modified.
- Reported Git and test evidence is independently verified.

### Phase 4 — add OpenCode as an adapter-backed lane

Actions:

1. Create a real Jellyberry Hermes adapter profile.
2. Connect it to the reviewed OpenCode service or CLI on Jellyhome.
3. Install `opencode` and the approved Matt/project skills for that profile.
4. Use a separate LogK checkout or worktree.
5. Run one bounded implementation card.
6. Test completion, block, timeout, cancellation, and malformed-result behavior.

Completion criteria:

- The local Hermes profile remains the sole Kanban assignee and result writer.
- OpenCode receives only the approved repository, branch, ticket, and tools.
- Cancellation and failure return the card to a safe, inspectable state.
- No secret is exposed in logs or card history.

### Phase 5 — consider controlled automation

Only after several successful manual pipelines:

1. Add a restricted orchestrator profile with board-oriented tools.
2. Test manual decomposition through that profile.
3. Review profile descriptions and capability routing.
4. Test missing-profile, missing-skill, and cross-board failure cases.
5. Consider enabling automatic decomposition with strict limits.

Completion criteria:

- Generated graphs are predictable and small.
- Every assignee and skill is validated before dispatch.
- Automatic work cannot bypass the operator's ready gate, privilege rules, or review gate.
- Concurrency remains bounded across active boards.

---

## 14. Decision package

The proposed final design is:

> **Jellyberry-hosted, multi-board Hermes Kanban; repository-backed specifications, tickets, decisions, and evidence; manually approved Matt Pocock development flows; real Hermes profiles as assignees; task-pinned workflow skills; SSH-backed remote execution; one independent reviewer profile; and external coding agents added later through profile-owned adapters.**

### Decisions to approve

- [ ] Jellyberry remains the sole Kanban control plane.
- [ ] Repository files are authoritative for specs, tickets, ADRs, and durable review evidence.
- [ ] Kanban is authoritative for status, dependencies, assignees, attempts, comments, and blocked reasons.
- [ ] Initial orchestration is manual with one executable card at a time.
- [ ] `continuous-hermes-improvement` remains the Hermes infrastructure board.
- [ ] A dedicated `logk` board is added for the first pilot.
- [ ] Skills are pinned explicitly to cards and must exist on the assignee profile.
- [ ] Project specialists are added only for stable host, tool, domain, memory, or safety boundaries.
- [ ] `jellybase_reviewer` is the first new specialist profile.
- [ ] External OpenCode integration is deferred until the native Hermes pipeline passes.
- [ ] PR creation, merge, release, deployment, sudo, and secret use remain operator-controlled.

### First practical action after approval

Execute **Phase 0 only**, verify the corrected board/profile state, and report the exact changes before creating the LogK pilot board or dispatching development work.

---

## 15. Authoritative references

- Hermes Kanban documentation: <https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban>
- Local multi-agent guide index: [README.md](README.md)
- Safety and architecture: [architecture-and-safety-boundaries.md](architecture-and-safety-boundaries.md)
- Feature lifecycle: [feature-lifecycle.md](feature-lifecycle.md)
- Matt Pocock skills: [matt-pocock-skills.md](matt-pocock-skills.md)
- Kanban templates: [kanban-card-templates.md](kanban-card-templates.md)
- Operator checklist: [operator-checklist.md](operator-checklist.md)
