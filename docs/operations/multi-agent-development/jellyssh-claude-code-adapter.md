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
- Claude receives no Bash tool in either mode. `--tools` restricts the built-in inventory to `Read,Glob,Grep,Edit,Write,Skill` for implementation and `Read,Glob,Grep,Skill` for review. `--allowedTools` only pre-approves the same bounded set; it is not treated as an inventory restriction. Strict MCP configuration plus an explicit `mcp__*` deny prevents MCP tools from bypassing that boundary. The adapter alone runs fixed Git, formatting, analysis, and test commands; an account-level `PreToolUse` hook remains defense in depth for interactive account use.
- The adapter never mutates Kanban, opens a PR, merges, releases, deploys, signs, sideloads, or claims physical-device acceptance.
- The controller must run from a clean Git checkout. Before any attempt it records the exact 40-character controller commit and verifies that every governed adapter/schema/hook/settings byte matches the blob at that revision; a dirty or unidentifiable controller blocks before remote execution.

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

The current result contract is schema version `2` and adapter version `0.2.0`; it is intentionally incompatible with the historical two-artifact `0.1.0` result shape.

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
- exact verified controller commit and controller-asset SHA-256 values;
- SHA-256 and base64 encoding of non-secret raw Claude JSON when Claude was invoked.

Raw Claude output is retained inside the canonical result rather than published as a separate sidecar. This gives an attempt one publication commit point: validation stages the complete evidence object first, then an exclusive atomic hard link publishes that one immutable file. Malformed worker JSON therefore produces one canonical `BLOCK` result rather than an orphaned raw artifact that prevents retry.

Evidence paths are direct filenames below the fixed evidence root. Publication opens every existing directory component with `O_NOFOLLOW`, retains the trusted parent directory descriptor, and creates/links the temporary and final names relative to that descriptor. A symlinked ancestor is rejected, while replacement of a validated pathname cannot redirect publication. Errors before the hard link fail publication. Temporary-file cleanup and directory synchronization after valid immutable evidence becomes visible are best-effort and cannot make the controller report failure after publication.

A `PASS` means the adapter contract completed. It is implementation evidence or advisory review evidence, not product acceptance.

## Verification

Tests must prove:

- valid request acceptance;
- unknown field, secret-shaped text, bad commit/path/branch/check rejection;
- exact fixed SSH/repository/worktree route;
- prompt supplied over stdin;
- no bypass-permissions or push flags;
- exact mode-specific built-in tool inventory restriction and MCP denial;
- implementation clean/commit/base checks;
- review before/after immutability checks;
- malformed JSON, timeout and nonzero exit fail closed;
- structurally valid synthetic credential shapes are rejected in worker output and changed-file content;
- exact controller-commit/byte binding and dirty-controller rejection;
- one-artifact atomic result publication, including malformed-output retention;
- symlink-ancestor rejection and path-swap confinement through a retained directory descriptor;
- no reported failure after the atomic publication commit point;
- live preflight against `agent-claude`;
- one no-edit Claude smoke in a disposable worktree.

## Rollback

- Remove only the adapter-created worktree and branch after confirming no unpushed work is needed.
- Remove `~/.claude/skills/<approved-name>` and the managed hook entry from the dedicated account if this lane is retired.
- Revoke GitHub deploy key `jellybase-jellyclaude` and remove the Jellyberry `agent-claude` SSH block/key to revoke access.
- Do not alter the existing `jellydev` implementation or reviewer profiles.
