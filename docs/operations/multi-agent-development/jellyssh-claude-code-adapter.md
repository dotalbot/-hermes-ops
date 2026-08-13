# JellySSH Claude Code adapter

> **Status:** implementation specification for isolated validation
>
> **Scope:** Jellyberry-controlled execution through `jellyclaude@jellybase`

## Problem

JellySSH work may be implemented or advised on by Claude Code, but Claude Code is not a Hermes profile or Kanban authority. A bounded adapter is required so Jellyberry can validate the route, create a disposable Jellybase clone, invoke Claude without putting task text in the process list, and return structured evidence. Missing, malformed, stale, wrong-commit, dirty-workspace, timeout, or unverifiable output must block.

## Fixed boundary

- Control plane: Jellyberry, OS user `jellybot`.
- SSH alias: `agent-claude`.
- Execution identity: `jellyclaude@jellybase`.
- Coordinator clone: `/home/jellyclaude/dev_projects/jellyssh`.
- Disposable sandbox root: `/home/jellyclaude/.cache/jellyssh-claude-sandboxes`.
- Git origin: `git@github-jellyssh:dotalbot/jellyssh.git`.
- Claude executable: `/home/jellyclaude/.local/bin/claude`.
- Fixed executables: Claude, the Flutter inventory wrapper, the versioned Dart ELF, and the exact `flutter_tools.snapshot` are authenticated by committed expected SHA-256 values and rechecked before/after execution; no mutable toolchain file is sourced.
- The account has no `sudo` and no credentials from `jellydev`.
- Claude's repository-scoped GitHub deploy key is read-only. A pinned per-session settings policy denies the model's file tools access to SSH, Claude-authentication, GitHub-authentication, backup-authentication, and `.env` paths.
- Claude receives no Bash tool in either mode. `--tools` restricts the built-in inventory to `Read,Glob,Grep,Edit,Write,Skill` for implementation and `Read,Glob,Grep,Skill` for review. `--allowedTools` only pre-approves the same bounded set; it is not treated as an inventory restriction. `--setting-sources user` resolves against the disposable `$HOME`, preserving authenticated copied skills while excluding repository project/local settings and hooks; no user settings file is copied or writable. Strict MCP configuration plus an explicit `mcp__*` deny prevents MCP tools from bypassing that boundary. The adapter alone runs fixed Git, formatting, analysis, and test commands; an account-level `PreToolUse` hook remains defense in depth for interactive account use.
- Every attempt uses a `--no-hardlinks` disposable clone with a separate Git directory. Before Claude starts, the controller moves the source `.git` pointer outside the source and restores it only after Claude exits. A Landlock ABI 4 policy gives Claude read access only to required system runtime paths, read-only `/proc` and `/sys` metadata, its exact executable, and the `.git`-free disposable source/home. Implementation writes are limited to exact declared file inodes or declared directory prefixes plus disposable Claude cache/session paths. The original account home, shared repository, SSH/GitHub files, toolchain, controller assets, and disposable Git metadata are outside the kernel read/write allowlist. `env -i` removes inherited credentials and agent variables. Read-only procfs/sysfs are required by the native Claude runtime; the dedicated account must not host unrelated workloads.
- Before Claude and after Claude/check execution, the controller binds the shared repository path, Git/common directory, HEAD, all refs, replace refs, effective system/global/local/worktree Git configuration, cleanliness, and resolved Claude/Flutter/Dart executable identities and hashes. Any drift blocks.
- Fixed checks run in a second disposable source copy under the same Landlock implementation. Only that copy, its scratch home, and `/dev/null` are writable; the validated Claude source, separate Git directory, shared repository, account paths, and SDK remain read-only. Check artifacts are deleted before publication.
- The adapter never mutates Kanban, opens a PR, merges, releases, deploys, signs, sideloads, or claims physical-device acceptance.
- The controller must run from a clean Git checkout. At process startup it records the adapter source digest, then captures one authenticated snapshot from exact Git objects: the 40-character controller commit, request/result schemas, hook/settings assets, and approved skill-release metadata and bundle bytes. The startup adapter digest must equal the committed adapter blob. All later schema validation, policy hashing, skill expectations, and result validation consume this snapshot rather than mutable live paths; a dirty, ABA-restored, or unidentifiable controller blocks before remote execution.

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
- no conflicting sandbox or branch.

### `run implementation`

- Validate a schema-bound request with no unknown fields or secret-shaped values.
- Require a full lowercase base commit reachable from `origin/main`.
- Create one disposable independent clone and one new feature/fix/docs/test/refactor/chore branch inside it. Claude cannot read or write the clone's separate Git directory.
- Require exact file paths or segment-bounded directory prefixes for intended implementation changes, and block before checks or commit if any changed path is undeclared.
- Pass prompt text to Claude through stdin, not argv.
- Use non-interactive structured JSON output in Claude's guarded `auto` mode without `--dangerously-skip-permissions` or Bash access.
- Require Claude to use the repository specification/ticket and TDD where a public seam exists. The controller independently runs requested fixed-enum checks and prepares an unreferenced local commit with a fixed message; neither Claude nor the adapter pushes. Commit preparation rejects configured Git filters, disables hooks/signing, captures each post-check changed path once into controller-owned memory, verifies its state/content digest and secret/path policy, writes exact blobs with `hash-object --no-filters`, constructs a private-index tree, validates the immutable tree, and creates the commit with `commit-tree` without advancing a ref or resetting the workspace.
- Final publication first schema-validates and fsyncs hidden canonical evidence under a retained no-follow directory descriptor, then transfers and verifies the unreferenced objects, creates the shared branch with a create-only compare-and-swap, and atomically hard-links the evidence. Any uncertain ref/evidence failure invokes idempotent exact-value ref deletion before publishing `BLOCK`; rollback uncertainty publishes no misleading evidence and fails closed. Credential/session purge is mandatory before publication, while full sandbox cleanup after the publication commit point is best-effort and cannot change a successful result.
- Return evidence; never treat Claude prose as approval.
- Block if the process or a fixed check times out, output is malformed or secret-shaped, HEAD does not descend from the base, the pre-commit state has no changes, the committed tree has no net changes, or the branch/ref is wrong.

### `run review`

- Materialize a detached disposable clone at the exact target commit.
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

The current result contract is schema version `2` and adapter version `0.4.1`; it is intentionally incompatible with historical adapter versions.

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

Raw Claude output is retained inside the canonical result rather than published as a separate sidecar. For implementation `PASS`, complete evidence is validated and durably staged before branch creation, then an exclusive atomic hard link publishes it after the branch compare-and-swap. Evidence-link failure rolls the exact branch value back before canonical `BLOCK` evidence is written. Malformed worker JSON therefore produces one canonical `BLOCK` result rather than an orphaned raw artifact.

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
- live Landlock enforcement for declared writes, undeclared sibling/Git denial, original-account denial, and shared-repository denial;
- sanitized `env -i` worker environment and fixed executable identities;
- protected shared Git/config/ref/executable before/after snapshot equality;
- implementation clean/commit/base checks;
- review before/after immutability checks;
- malformed JSON, timeout and nonzero exit fail closed;
- structurally valid synthetic credential shapes are rejected in worker output and changed-file content;
- exact controller-commit/byte binding and dirty-controller rejection;
- ABA-restored controller rejection and snapshot-only schema/policy consumption;
- hostile Git-filter rejection plus hook-free, filter-free exact-byte commit-tree construction;
- mutation-between-scan-and-commit rejection through post-check state/content digests and immutable-tree validation;
- one-artifact atomic result publication, including malformed-output retention;
- symlink-ancestor rejection and path-swap confinement through a retained directory descriptor;
- no reported failure after the atomic publication commit point;
- staged-evidence/ref ordering plus fault-injected exact-value rollback after uncertain ref or evidence failure;
- live preflight against `agent-claude`;
- one no-edit Claude smoke in a disposable sandbox.

## Rollback

- Remove only the adapter-created disposable sandbox and branch after confirming no unpushed work is needed.
- Remove `~/.claude/skills/<approved-name>` and the managed hook entry from the dedicated account if this lane is retired.
- Revoke GitHub deploy key `jellybase-jellyclaude` and remove the Jellyberry `agent-claude` SSH block/key to revoke access.
- Do not alter the existing `jellydev` implementation or reviewer profiles.
