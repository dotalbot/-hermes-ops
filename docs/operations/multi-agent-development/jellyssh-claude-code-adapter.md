# JellySSH Claude Code adapter

> **Status:** implementation specification for isolated validation
>
> **Scope:** Jellyberry-controlled execution through `jellyclaude@jellybase`

## Problem

JellySSH work may be implemented or advised on by Claude Code, but Claude Code is not a Hermes profile or Kanban authority. A bounded adapter is required so Jellyberry can validate the route, create an isolated Jellybase worktree, invoke Claude without putting task text in the process list, and return structured evidence. Missing, malformed, stale, wrong-commit, dirty-worktree, timeout, or unverifiable output must block.

## Fixed boundary

- Control plane: Jellyberry, OS user `jellybot`.
- SSH alias: `agent-claude`.
- Execution identity: `jellyclaude@jellybase`.
- Coordinator clone: `/home/jellyclaude/dev_projects/jellyssh`.
- Worktree root: `/home/jellyclaude/dev_projects/jellyssh-worktrees`.
- Git origin: `git@github-jellyssh:dotalbot/jellyssh.git`.
- Claude executable: `/home/jellyclaude/.local/bin/claude`.
- Toolchain file: `/home/jellyclaude/.config/jellyssh/toolchain.env`.
- The account has no `sudo` and no credentials from `jellydev`.
- Claude's repository-scoped GitHub deploy key is read-only. A pinned per-session settings policy denies the model's file tools access to SSH, Claude-authentication, GitHub-authentication, backup-authentication, and `.env` paths.
- Claude receives no Bash tool in either mode. The adapter alone runs fixed Git, formatting, analysis, and test commands; an account-level `PreToolUse` hook remains defense in depth for interactive account use.
- The adapter never mutates Kanban, opens a PR, merges, releases, deploys, signs, sideloads, or claims physical-device acceptance.

## Modes

### `preflight`

Read-only checks must verify:

- exact host and OS user;
- Claude Code installation and authentication;
- tmux, Git, Flutter and Dart versions;
- approved personal Matt skills and exact bundle hashes;
- repository origin, clean coordinator clone and requested base commit;
- repository-scoped GitHub read access and a dry-run proof that write access is denied;
- Git author and committer identity;
- no conflicting worktree or branch.

### `run implementation`

- Validate a schema-bound request with no unknown fields or secret-shaped values.
- Require a full lowercase base commit reachable from `origin/main`.
- Create one isolated worktree and one new feature/fix/docs/test/refactor/chore branch.
- Require exact file paths or segment-bounded directory prefixes for intended implementation changes, and block before checks or commit if any changed path is undeclared.
- Pass prompt text to Claude through stdin, not argv.
- Use non-interactive structured JSON output in Claude's guarded `auto` mode without `--dangerously-skip-permissions` or Bash access.
- Require Claude to use the repository specification/ticket and TDD where a public seam exists. The controller independently runs requested fixed-enum checks and creates the local commit with a fixed message; neither Claude nor the adapter pushes.
- Return evidence; never treat Claude prose as approval.
- Block if the process or a fixed check times out, output is malformed or secret-shaped, HEAD does not descend from the base, the pre-commit state has no changes, the committed tree has no net changes, or the branch/ref is wrong.

### `run review`

- Materialize a detached worktree at the exact target commit.
- Use Claude `plan` permission mode with no edit tools.
- Require an exact specification path and digest.
- Capture before/after commit, tree and status.
- Block on any workspace mutation or malformed verdict.
- The output is advisory unless a separately approved independent reviewer contract binds it. The same Claude account/session that implemented a candidate cannot independently approve it.

## Request contract

A JSON request binds:

- schema version and unique attempt ID;
- mode;
- exact base and optional target commits;
- branch and declared changed-path boundary for implementation;
- specification path and SHA-256;
- bounded task text;
- fixed-enum checks;
- model, effort, timeout and output path.

The adapter rejects paths outside the repository, arbitrary commands, caller-selected SSH targets/workspaces, secrets, control characters, symlinks and existing attempt paths.

## Result contract

The canonical JSON result includes:

- adapter version and attempt ID;
- mode, fixed route and timestamps;
- request digest;
- base, starting and final commit/tree;
- branch and worktree;
- Claude version/model/session and terminal reason;
- process exit/timeout;
- changed files and clean-state result;
- requested check results;
- verdict: `PASS`, `BLOCK`, or `TIMEOUT`;
- blockers;
- SHA-256 of retained raw Claude JSON.

A `PASS` means the adapter contract completed. It is implementation evidence or advisory review evidence, not product acceptance.

## Verification

Tests must prove:

- valid request acceptance;
- unknown field, secret-shaped text, bad commit/path/branch/check rejection;
- exact fixed SSH/repository/worktree route;
- prompt supplied over stdin;
- no bypass-permissions or push flags;
- implementation clean/commit/base checks;
- review before/after immutability checks;
- malformed JSON, timeout and nonzero exit fail closed;
- atomic result publication;
- live preflight against `agent-claude`;
- one no-edit Claude smoke in a disposable worktree.

## Rollback

- Remove only the adapter-created worktree and branch after confirming no unpushed work is needed.
- Remove `~/.claude/skills/<approved-name>` and the managed hook entry from the dedicated account if this lane is retired.
- Revoke GitHub deploy key `jellybase-jellyclaude` and remove the Jellyberry `agent-claude` SSH block/key to revoke access.
- Do not alter the existing `jellydev` implementation or reviewer profiles.
