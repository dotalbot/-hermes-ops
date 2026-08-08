# Hermes Desktop, Projects, Profiles, and Sessions

A practical offline guide to the Hermes setup running on **Jellyberry**.

**Snapshot checked:** 2026-08-08 01:30 BST  
**Hermes host:** `jellyberry`  
**Linux account:** `jellybot`

> The shortest useful mental model is:
>
> - **Host** = the computer running Hermes.
> - **OS user** = the security identity under which Hermes runs.
> - **Profile** = a persistent Hermes identity, role, configuration, memory, and session store.
> - **Desktop Project** = a named local workspace anchored to a folder or repository.
> - **Session** = one persisted conversation within a profile.
> - **Model** = the reasoning engine selected for a profile, session, or task.
> - **Worker** = a running Hermes process that performs work.
> - **Kanban** = a durable work queue that assigns tasks to profiles.
> - **Git repository** = the durable source-controlled files and history.

---

## 1. The complete conceptual stack

```text
Interaction device and interface
    Mac Hermes Desktop / Discord / SSH terminal
        ↓
Hermes service on Jellyberry
    Dashboard backend / messaging gateway / CLI
        ↓
Linux account
    jellybot
        ↓
Hermes profile
    default / homenetworkworker / jellybase_hermes
        ↓
Desktop Project or explicit workspace
    named pointer to a folder or Git checkout
        ↓
Session or Kanban worker run
    one conversation or one executing task
        ↓
Model and tools
    OpenAI Codex model, terminal, files, web, SSH, APIs, etc.
        ↓
Files and managed systems
    repositories, Jellybase, Jellyhome, Macs, Home Assistant, GitHub, Azure DevOps
```

These are related layers, but they are not interchangeable names.

```text
Host ≠ OS user ≠ profile ≠ Project ≠ session ≠ model ≠ worker
```

---

## 2. Interfaces are not persistent agents

### Hermes Desktop

Hermes Desktop is the graphical client running on the Mac. In this setup it connects to the remote Hermes dashboard backend on Jellyberry.

The Desktop window is on the Mac, but file and terminal tools run where the selected backend/profile says they run.

### Discord

Discord messages arrive through the Hermes messaging gateway. The gateway is a separate service from the Desktop/dashboard backend.

### SSH terminal

An SSH terminal is a normal Linux shell. It only becomes a Hermes interface after a Hermes command is started, for example:

```bash
hermes
hermes -p homenetworkworker
```

### Important distinction

```text
Hermes Desktop → dashboard backend
Discord       → messaging gateway
SSH terminal  → Linux shell; optionally starts Hermes CLI
```

They can reach related Hermes state, but they are not three permanent agents.

---

## 3. Host, OS user, and profile

### Host

A host is a physical or virtual computer where software executes.

Examples in this environment include:

- Jellyberry
- Jellybase
- Jellyhome
- Macworklaptop
- Homelap

Hermes is currently running centrally on Jellyberry.

### OS user

Hermes on Jellyberry runs as Linux account:

```text
jellybot
```

This account determines access to:

- Files and directories
- SSH keys
- Git configuration
- Programs
- Network credentials
- Local services

### Hermes profile

A profile is a persistent Hermes identity and state directory. It can define:

- Role and personality
- Default model/provider
- Tools
- Skills
- Memory configuration
- Sessions
- Terminal backend
- Working-directory defaults
- Gateway state
- Cron jobs
- Security and approval settings

A profile is best thought of as an employee with a filing cabinet and working style. It is not a host, Linux account, repository, model, or security sandbox.

---

## 4. Current profiles on Jellyberry

The live installation currently reports:

| Profile | Model default | Terminal backend | Gateway | Location |
|---|---|---|---|---|
| `default` | `gpt-5.5` via OpenAI Codex | local | running | `/home/jellybot/.hermes` |
| `homenetworkworker` | `gpt-5.5` via OpenAI Codex | local | stopped | `/home/jellybot/.hermes/profiles/homenetworkworker` |
| `jellybase_hermes` | `gpt-5.6-terra` via OpenAI Codex | SSH | stopped | `/home/jellybot/.hermes/profiles/jellybase_hermes` |

`hindsightpilot` was archived and removed on 2026-08-08 because it was writing experiment/pilot memory into `hermes-main`. The export is under `/home/jellybot/.hermes/backups/hindsight-bank-routing-20260808T001954Z/`.

Model selections can be overridden by individual sessions or tasks, so a current session may use a different model from the profile default.

The `jellybase_hermes` profile currently has:

```text
terminal.backend: ssh
terminal.ssh_file_sync: false
```

This means its terminal and file execution context is remote, and automatic copying of Jellyberry's Hermes files to that SSH host is disabled.

---

## 5. Where profile settings and state are stored

The default profile uses the main Hermes home:

```text
/home/jellybot/.hermes
```

Named profiles use:

```text
/home/jellybot/.hermes/profiles/<profile-name>
```

Conceptual layout:

```text
/home/jellybot/.hermes/
├── config.yaml                 # default profile settings
├── .env                        # default profile secrets
├── SOUL.md                     # default profile role/personality
├── state.db                    # default profile sessions/state
├── skills/                     # default profile skills
│
└── profiles/
    ├── homenetworkworker/
    │   ├── config.yaml
    │   ├── .env
    │   ├── SOUL.md
    │   ├── state.db
    │   └── skills/
    │
    └── jellybase_hermes/
        ├── config.yaml
        ├── .env
        ├── SOUL.md
        ├── state.db
        └── skills/
```

### `config.yaml`

The main non-secret profile configuration. It controls settings such as:

- Model/provider defaults
- Terminal backend
- SSH execution
- Working-directory behavior
- Tools
- Delegation
- Memory provider
- Compression
- Security and approvals
- Gateway behavior
- Kanban and cron behavior

### `.env`

Profile-specific secrets and environment variables, such as API keys, tokens, service URLs, and integration credentials.

This file is sensitive. Do not commit it to Git or copy its values into documentation.

### `SOUL.md`

The profile's role, personality, communication style, and operating boundaries.

Examples:

- `default`: orchestrator and general assistant
- `homenetworkworker`: home-network specialist
- `jellybase_hermes`: implementation worker using Jellybase through SSH
- `hindsightpilot`: memory/research experiments

### `state.db`

The profile's persisted state database, including its sessions.

A session under `default` is separate from a session under `homenetworkworker`, even if both sessions work on the same repository.

### `skills/`

Skills installed for the profile. Profiles can have different skill sets or versions.

Current reported skill counts:

```text
default:             126
hindsightpilot:      107
homenetworkworker:   110
jellybase_hermes:    126
```

### Other profile state

Depending on enabled features and Hermes version, a profile home may also contain:

- Cron definitions and scheduler state
- Logs
- Plugin state
- Local memory files
- Authentication state
- Cached data
- Scripts
- Gateway state

An external memory provider such as Hindsight may store the actual memories externally while the profile retains its provider configuration.

---

## 6. Profiles are not security boundaries

All Jellyberry profiles currently run as Linux user `jellybot`.

Therefore, profile separation does not prevent a profile from accessing resources available to that OS user, such as:

```text
/home/jellybot/.ssh/
/home/jellybot/.gitconfig
/home/jellybot/.config/
/home/jellybot/.local/
```

Profiles may consequently share access to:

- SSH keys
- GitHub and Azure DevOps credentials
- Git configuration
- External CLI logins
- Files readable by `jellybot`

Use separate Linux users, containers, virtual machines, or hosts when a strong security boundary is required.

The same profile name on another host is also not automatically the same identity. A `default` profile on Jellyberry and a `default` profile on a Mac are independent unless their state is deliberately copied or distributed.

---

## 7. What is a Hermes Desktop Project?

A Hermes Desktop Project is a named workspace anchored to a folder or repository checkout.

It helps Hermes Desktop determine:

- The folder being worked on
- Where terminal and file operations should begin
- Which files to show
- Which Git changes to review
- How to group related sessions
- Where worktrees may be created

A useful shorthand is:

```text
Desktop Project = friendly name + primary local folder + related sessions
```

A Desktop Project does not automatically:

- Create a GitHub repository
- Clone a repository
- Create a Git branch
- Push changes
- Create GitHub issues
- Deploy software
- Synchronize sessions or profile memory

### Current example

```text
Hermes Desktop Project: Diagram_creator
Primary path: /home/jellybot/dev_projects/diagram_creator/DominicTalbot
```

Current Jellyberry convention: Git-backed coding projects live under `/home/jellybot/dev_projects/`; non-git project activity lives under `/home/jellybot/projects/`. See `docs/operations/home-directory-project-layout.md` for the migration record, current mappings, verification evidence, and promotion rule.

Because the Desktop client is connected to Jellyberry's backend, its Project path must be visible to Jellyberry. A Mac-only path such as the following is not the same workspace:

```text
/Users/dominic/dev/Inform_devs/diagram_creator/DominicTalbot
```

The Jellyberry and Mac folders can be separate checkouts connected to the same remote Git repository.

---

## 8. Desktop Project versus Git repository

The simplest distinction is:

```text
Git repository = durable, shared, version-controlled work
Desktop Project = Hermes's local doorway into that work
```

### Git repository owns

- Source code
- Tests
- Documentation
- Branches
- Commits
- Tags and releases
- Pull requests
- CI/CD definitions
- Shared history

### Desktop Project owns or organizes

- The active local workspace path
- Desktop file/review context
- Related Hermes sessions
- Project-specific interaction context

### GitHub Project is a third concept

GitHub also has a planning feature called **GitHub Projects**. It can organize:

- Issues
- Pull requests
- Roadmaps
- Status fields
- Work across repositories

That planning board is neither the Git repository nor the Hermes Desktop Project.

### Typical relationship

```text
Software initiative: Diagram Creator
│
├── GitHub or Azure DevOps repository
│   └── source, commits, branches, PRs, CI and documentation
│
├── Jellyberry checkout
│   └── /home/jellybot/dev_projects/diagram_creator/DominicTalbot
│       └── Hermes Desktop Project: Diagram_creator
│           ├── design session
│           ├── implementation session
│           └── review session
│
└── Mac checkout
    └── /Users/dominic/dev/Inform_devs/diagram_creator/DominicTalbot
        └── Codex Desktop or other local development tooling
```

Git synchronizes committed files. It does not automatically synchronize:

- Hermes profiles
- Sessions
- Memory
- Cron jobs
- Kanban databases
- Uncommitted changes
- External coding-agent conversations

---

## 9. Profiles and Projects are independent dimensions

A profile answers:

```text
Who or what role is working?
```

A Project answers:

```text
Which folder or repository is being worked on?
```

The relationship is many-to-many:

```text
One profile can work on many Projects.
One Project can be worked on by many profiles.
```

A Project created while using `default` is not permanently owned by that profile. Another profile can work on the same repository if its execution backend can access the files.

What remains profile-specific:

- Sessions
- Memory
- Skills
- Model defaults
- `SOUL.md`
- Tool configuration
- Terminal backend
- Cron and gateway state

The repository files remain normal filesystem resources.

---

## 10. Giving another profile work on the same Project

### Sequential handoff using one checkout

Use this when only one profile edits at a time:

```text
default
    ↓ writes specification and leaves clean repository state
specialist profile
    ↓ implements and commits

default
    ↓ reviews the committed result
```

Both profiles can use the same checkout if their backends can access it.

### Parallel work using Git worktrees

Use separate worktrees when profiles or processes may edit concurrently:

```text
Main checkout:
/home/jellybot/example-project

Worker worktree:
/home/jellybot/example-project/.worktrees/feature-x
```

Then assign each worker a specific branch/worktree. This prevents conflicting edits, branch switches, lock files, and overwritten uncommitted changes.

For `jellybase_hermes`, prepare the remote checkout or worktree explicitly. Do not currently rely on Hermes Kanban's automatic local `worktree` workspace mode for that profile.

### SSH backend caveat

`jellybase_hermes` uses an SSH terminal backend. A Jellyberry path may not exist on the SSH target.

Example:

```text
Jellyberry checkout:
/home/jellybot/example-project

Jellybase checkout:
/home/jellydev/repos/example-project
```

They can point to the same Git remote, but they are separate filesystem copies. Git commits and pushes become the transfer mechanism.

A profile's name does not choose a physical host. Its terminal backend and workspace configuration determine where tools run.

---

## 11. Sessions

A session is a persisted conversation under one profile.

It is not a permanent running agent. It can be opened, resumed, branched, searched, or deleted.

A session records conversational state and workspace context such as:

- Messages
- Tool calls and results
- Project/workspace association
- Working directory
- Model choice
- Source interface

Use one coherent session per investigation, feature, review, or operational change.

Examples:

```text
Diagram Creator — define requirements
Diagram Creator — implement renderer change
Diagram Creator — independent review
Home network — diagnose scrape failure
LogK — prepare release
```

Desktop, CLI, and gateway surfaces can resume the same session when they target the same backend and profile.

Another profile should normally start its own session rather than silently inheriting the original conversation. Transfer context through:

- A committed specification
- A GitHub issue
- A Kanban task
- A handoff document
- Repository documentation
- A precise prompt

---

## 12. Models and external coding agents

A model is the reasoning engine used by a session or task. It is not a profile or a permanent agent.

A profile has a default model, but a session or Kanban task may override it.

External coding applications are another layer:

- Claude Code
- Codex CLI/Desktop
- OpenCode

These applications can themselves use different models. Therefore:

```text
Hermes profile ≠ Hermes worker process ≠ coding application ≠ model
```

---

## 13. Hermes Kanban

Kanban is a durable shared work queue. It is separate from Desktop Projects and GitHub Projects.

A typical flow is:

```text
default profile
    ↓ creates task
Hermes Kanban card
    assignee: specialist profile
    workspace: explicit repository/worktree
    requirements and verification criteria
    ↓ dispatcher
worker process using assigned profile
    ↓ implements, verifies, commits or blocks
Kanban result
    ↓
default independently reviews
```

A Kanban task should specify:

- Repository
- Exact workspace
- Branch or worktree
- Assignee profile
- Requirements
- Allowed files
- Tests and verification
- Commit/push expectations
- Completion evidence

Kanban transfers the task; it does not transfer the original session's unspoken context.

The board is on Jellyberry unless a separate Hermes installation is deliberately configured elsewhere. A remote host does not automatically join Jellyberry's Kanban fleet merely because a profile uses SSH to manage it.

---

## 14. Recommended role arrangement

### `default`

Primary role:

- Chuck/orchestrator
- Interactive Desktop and Discord work
- Requirements and design
- Coordination
- Independent review
- Release decisions

### `homenetworkworker`

Primary role:

- Home-network repository work
- Infrastructure diagnostics
- Monitoring changes
- Home Assistant and related operations

Typical local workspace:

```text
/home/jellybot/dev_projects/home-network
```

### `jellybase_hermes`

Primary role:

- Implementation and testing through Jellybase
- Work against an explicitly prepared remote checkout
- No automatic Hermes-home SSH synchronization

### `hindsightpilot`

Primary role:

- Memory-provider and recall experiments
- Research and validation of retained context

### Possible future profile

A separate `jellybase_reviewer` profile could provide stronger role separation for independent read-only reviews.

---

## 15. Recommended development workflow

For a new application:

1. Create a GitHub or Azure DevOps repository.
2. Clone it onto the host where the relevant Hermes profile executes.
3. Create a Hermes Desktop Project pointing to the local checkout.
4. Start a focused session for requirements or design.
5. Create a feature branch or worktree for implementation.
6. Hand implementation to the appropriate specialist profile when useful.
7. Run tests and live verification.
8. Commit and push durable artifacts.
9. Review the exact diff independently.
10. Merge or release only after the required evidence passes.

Use the following source-of-truth rules:

| Information | Best source of truth |
|---|---|
| Source code and documentation | Git repository |
| Shared development planning | GitHub Issues/Projects or Azure DevOps |
| Durable Hermes worker assignment | Hermes Kanban |
| Interactive investigation | Hermes session |
| Agent role and defaults | Hermes profile |
| Local workspace association | Hermes Desktop Project |
| Parallel code-change isolation | Git branch/worktree |
| Secrets | Profile `.env` or dedicated secret store |

---

## 16. Common gotchas

### Project selection is not a security sandbox

Selecting a Project sets working context. It does not prevent tools from accessing other files allowed to the executing OS user.

### A profile is not a machine

`jellybase_hermes` does not execute on Jellybase merely because of its name. It executes there because its terminal backend is configured for SSH.

### Desktop location is not execution location

The Desktop application is on the Mac, but the remote Jellyberry backend controls the workspace unless a profile's backend redirects execution elsewhere.

### Same repository does not imply shared session

Two profiles can edit the same repository while retaining completely separate sessions and memories.

### Same profile name does not imply shared state across hosts

Profiles on Jellyberry and Mac are independent unless deliberately copied or synchronized.

### Concurrent use of one checkout is risky

Separate worktrees or clones are safer when multiple profiles or coding agents may write at the same time.

### Configuration changes may require a fresh session

After changing `config.yaml`, `SOUL.md`, tools, skills, model defaults, or memory settings, start a new session. Existing sessions may retain earlier system-prompt or configuration state.

For a running gateway, configuration changes may also require:

```bash
hermes gateway restart
```

### Do not commit secrets

Never commit:

- Profile `.env` files
- OAuth tokens
- `auth.json`
- Private SSH keys
- Credential-bearing logs

---

## 17. Useful commands

### Profiles

```bash
hermes profile list
hermes profile show default
hermes profile show homenetworkworker
hermes profile show jellybase_hermes
```

### Start a named profile

```bash
hermes -p homenetworkworker
```

Or from a selected repository:

```bash
cd /home/jellybot/dev_projects/home-network
hermes -p homenetworkworker
```

### Configuration paths

```bash
hermes -p homenetworkworker config path
hermes -p homenetworkworker config env-path
```

### Inspect settings

```bash
hermes -p homenetworkworker config get terminal.backend
hermes -p jellybase_hermes config get terminal.backend
hermes -p jellybase_hermes config get terminal.ssh_file_sync
```

### Edit configuration

```bash
hermes -p homenetworkworker config edit
```

### Change one setting

```bash
hermes -p homenetworkworker config set terminal.cwd /home/jellybot/dev_projects/home-network
```

### Sessions

```bash
hermes sessions list
hermes sessions browse
hermes sessions stats
```

Use `-p <profile>` to inspect another profile's session store:

```bash
hermes -p homenetworkworker sessions list
```

### Profile aliases installed on Jellyberry

```text
hindsightpilot
homenetworkworker
jellybase_hermes
```

These wrappers are under:

```text
/home/jellybot/.local/bin/
```

---

## 18. Related visual diagram

Editable Excalidraw source:

```text
/home/jellybot/dev_projects/diagram_creator/DominicTalbot/diagram_creator/artifacts/source/hermes-concepts-jellyberry.excalidraw
```

PNG preview:

```text
/home/jellybot/dev_projects/diagram_creator/DominicTalbot/diagram_creator/artifacts/preview/hermes-concepts-jellyberry.png
```

SVG preview:

```text
/home/jellybot/dev_projects/diagram_creator/DominicTalbot/diagram_creator/artifacts/preview/hermes-concepts-jellyberry.svg
```

---

## 19. Final mental model

```text
Jellyberry
    = central Hermes host

jellybot
    = shared Linux security identity

profile
    = persistent Hermes role and filing cabinet

Desktop Project
    = named local workspace pointing at a folder or checkout

session
    = one profile's persisted conversation about work

model
    = reasoning engine selected for a profile/session/task

worker
    = running process executing a task

Kanban
    = durable queue assigning work to profiles

Git repository
    = durable source code, documentation and history

Git branch/worktree
    = isolated code-change lane
```

The most important operational rule is:

> Keep profiles distinct for genuinely distinct roles, keep sessions focused, use Projects as workspace doorways, use Git as the durable source of truth, and use branches/worktrees whenever multiple workers may modify the same repository.
