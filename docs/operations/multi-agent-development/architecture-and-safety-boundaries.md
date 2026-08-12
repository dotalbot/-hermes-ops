# Architecture and safety boundaries

## The four planes

### 1. Git remote: shared source of truth

The Git server holds `main`, feature branches, commits, and reviews. Treat it as the handoff boundary between machines. Do not use SSH file synchronization as a substitute for Git.

### 2. Jellybase: development workspace

Remote code work runs as `jellydev` through LAN SSH at `192.168.1.2`.

Use a dedicated, non-production clone for each repository:

```text
/home/jellydev/dev_projects/<repo>
```

Do not develop in a deployment checkout, `/opt/...`, a different user's home directory, or a live service bind mount unless that exact location has been reviewed and approved for development.

### 3. Jellyberry: Hermes control plane

Jellyberry owns:

- Hermes profiles and their local skill files;
- Kanban board databases, card history, and worker logs;
- orchestration and review coordination;
- the local SSH configuration used to reach Jellybase.

The current generic remote implementation baseline is `jellybase_hermes`. It is not a silent fallback for project work. Use the project-specific profile named by the approved routing manifest. Phase 2 installed and verified `jellybase_jellyssh` and `jellybase_jellyssh_reviewer`; each product ticket still requires an exact lifecycle preflight and explicit assignment rather than fallback routing.

### 4. Kanban: queue and audit trail

A Kanban card describes work and retains evidence. Its body must name the exact remote repository path, branch, acceptance criteria, required commands, and final reporting requirements.

For Jellybase work, the remote repository is the durable workspace. Do not use local Kanban `worktree` mode as if it created a remote Jellybase worktree; it creates a different checkout on Jellyberry. Use the normal scratch card workspace and state the remote path explicitly.

## Required SSH boundary

All normal Jellybase worker traffic uses:

```text
jellydev@192.168.1.2:22
```

Use the local `jellybase-lan` SSH alias where direct SSH is needed. Do not make operational work depend on Tailscale SSH because interactive reauthentication can interrupt workers.

Every approved Jellybase implementation profile inherits the non-privileged `jellybase_hermes` baseline:

- no sudo by default;
- stop and request approval if privileged work is required;
- no stored password or secret material in cards, docs, or repository files.

## Hermes-state boundary

The Jellybase worker profile has `terminal.ssh_file_sync: false`.

This means the agent still runs on Jellyberry and executes normal repository commands remotely, but it must not provision, upload, read, tar, download, or synchronize the existing remote `~/.hermes` directory. That remote state is durable and outside the application source workspace.

## Role boundaries

### `default`

The operator-facing coordinator: clarify the feature, create and inspect cards, coordinate reviews, and report status.

### `jellybase_hermes`

The generic remote implementation baseline: inspect only the approved repository, create feature branches, change code, run tests, commit, and push only when the card and project policy authorize it. Do not route project work here when an approved project-specific profile is required.

### Other profiles

Use `homenetworkworker` only for home-network work. Do not assign ordinary app development to it. Create project-specific implementation and read-only reviewer profiles only in the phase authorized by the operator; until then, block rather than substituting another profile.

## Concurrency policy

One profile can safely own one remote repository/branch at a time. Parallelize planning, source discovery, research, or review. Do not dispatch simultaneous editing cards against the same Jellybase checkout or feature branch.

For unrelated repositories, use separate boards and separate remote clones. If parallel edits are eventually needed for one repository, create explicit Git worktrees on Jellybase and assign one branch/worktree per worker after a deliberate concurrency review.
