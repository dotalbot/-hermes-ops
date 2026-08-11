# JellySSH Phase 2 routing/setup evidence — 2026-08-09

> **Status:** setup verified; routing and development remain blocked
>
> **Evidence cut:** 2026-08-09 12:08 BST
>
> **Branch:** `feat/jellyssh-phase2-routing`
>
> **Accepted Phase 1 base:** `c3daa570e7e1d3a8b15f8667c6803361130b0504`
>
> **Accepted JellySSH intake:** `main` at `7f612d96bd35fcaa336956d7922a82513d2e9e0d`

## Outcome

Phase 2 established the minimum Git-backed Skill Control Plane, separate implementation and review checkouts on Jellyberry and Jellybase, isolated implementation/reviewer profiles, the `jellyssh-main` bank binding, a six-tool restricted review MCP route, controller-enforced DeepSeek final-review and Gemini conditional mobile-UX routes, and an empty non-executable `jellyssh` board.

JellySSH is not routable. The Phase 2 runtime schema has no routable state, semantic validation rejects `project.state=routable`, and `promotion.candidate_routable` must remain false. Phase 3 is not authorized.

Authoritative state is in machine-readable manifests under `skills-control-plane/`; this report is a projection.

## Skill Control Plane

Implemented:

- immutable `core-development@0.1.0` release;
- `database-data@0.1.0` and `flutter-mobile@0.1.0` capability packs;
- three project-specific JellySSH overlays;
- project and runtime Draft 2020-12 schemas;
- semantic validation, live checkout/profile/bank/toolchain discovery, plan, audit, verify, dry-run-only initialization, and generated status;
- deterministic, framed skill-package hashing with symlink and non-regular-file rejection;
- aggregate hashes over sorted skill name/hash pairs;
- descriptor hashes over governance metadata, provenance, ownership, compatibility, approvals, state, and aggregate hash;
- atomic generated-report writes confined to `skills-control-plane/generated/`.

Pinned content hashes remain:

- core: `sha256:5b639dd39dbddf6360926df3b4e91c9e9c828f686d2989bad6b8493694105f59`
- database/data: `sha256:eae9d69125f92eff65d6c249cfcc3e9a3ab6384a2dbc1cbdcf3530d46f18a339`
- Flutter/mobile: `sha256:fcf64f75fc767c9737df2dfe4849552109cc2a16615e815358daaf591eb6356f`

The implementation bundle includes `implement`, `tdd`, and `diagnosing-bugs`. Review bundles include the required shared review skills, database/data capability, Flutter/mobile capability, and all three JellySSH overlays. The expert trigger matrix includes dependency upgrades, navigation/session lifecycle, terminal/native bridge, destructive data, transactions/concurrency, privacy, deletion, replication/export/backup, and screenshot/keystore/clipboard/I/O cases.

### Overlay authority

The accepted JellySSH intake commit is immutable and direct Jellybase GitHub authentication is blocked. Phase 2 therefore records the three pilot overlays under `skills-control-plane/projects/jellyssh/overlays/` with `authority: control-plane`. They are project-specific, may materialize only into the two named JellySSH profiles, and are not part of any global baseline. Mirroring into `.hermes-project/skills/` is deferred until repository authentication, a reviewed JellySSH commit, and explicit operator authorization exist.

## Workspaces

The scanner validates all four checkouts against the accepted remote, branch, commit, and clean state:

- Jellyberry coordinator: `/home/jellybot/dev_projects/jellyssh`
- Jellyberry coordinator review: `/home/jellybot/dev_projects/jellyssh-review`
- Jellybase implementation: `/home/jellydev/dev_projects/jellyssh`
- Jellybase isolated review: `/home/jellydev/dev_projects/jellyssh-review`

The path-stable bridges `/var/tmp/hermes-jellyssh` and `/var/tmp/hermes-jellyssh-review` are checked independently on both hosts. The implementation profile live smoke returned user `jellydev`, cwd `/var/tmp/hermes-jellyssh`, exact accepted commit, Flutter `3.44.9`, and Dart `3.12.2`.

## Profiles and Hindsight

### `jellybase_jellyssh`

- provider/model: OpenAI Codex `gpt-5.6-terra`
- fallback routes: none
- SSH to Jellybase as non-privileged `jellydev`
- exact isolated implementation workspace
- skills: `implement`, `tdd`, `diagnosing-bugs`
- bank: `jellyssh-main`
- automatic retention: disabled

### `jellybase_jellyssh_reviewer`

- provider/model: OpenRouter `deepseek/deepseek-v3.2`
- API mode: `chat_completions`
- fallback routes: none, including legacy fallback keys
- SSH workspace: `/home/jellydev/dev_projects/jellyssh-review`
- only platform toolset: `mcp-jellyssh_review`
- terminal, file, code execution, Kanban, memory, delegation, browser, cron, and unrelated broad toolsets disabled
- automatic recall and retention disabled
- bank binding: `jellyssh-main`
- MCP trust: untrusted
- MCP sampling: disabled

Live Hindsight discovery found `jellyssh-main`. No global Hindsight routing or retention setting was changed.

## Reviewer boundary

Exactly six MCP tools are exposed:

- `repository_metadata`
- `list_repository_files`
- `read_repository_text`
- `review_git_diff`
- `review_git_show`
- `run_readonly_check`

All advertise `readOnlyHint=true`, `destructiveHint=false`, and `openWorldHint=false`.

The boundary:

- reaches the isolated Jellybase review checkout over fixed SSH;
- reads tracked regular-file blobs from the exact commit rather than worktree paths;
- limits MCP-visible Git refs to the exact target plus the transient controller-supplied base; interactive profile use is target-only;
- rejects symlinks, path traversal, Git metadata, credential-like names, Git pathspec magic, arbitrary refs, arbitrary commands, and write tools;
- disables Git hooks, fsmonitor, global/system config, external diff, textconv, filters, credential helpers, network prompting, and optional locks;
- bounds paths, files, lines, output size, response size, and time;
- never exposes model terminal, file, code, Kanban, memory, or arbitrary MCP tools.

Fixed Flutter checks use attribute-independent `ls-tree`/`cat-file` materialization of every regular tracked blob from the exact commit in a disposable directory and a digest-pinned local Docker image with `--network none`, a private IPC/PID namespace, a read-only root, dropped capabilities, no-new-privileges, no host home or runtime-socket mounts, bounded read-only SDK/cache mounts, one disposable writable scratch mount, and PID/process/memory/CPU/time/file-size limits. The exact commit's resolved `.dart_tool` metadata is hash-pinned and copied into scratch, so review checks perform no dependency resolution or network access. A fixed sandbox self-check proves network denial, container PID isolation, host-home/socket absence, root read-only behavior, and scratch cleanup before evidence is accepted. SSH ignores user configuration and uses an exact LAN address, user, key, port, disabled proxy/jump, a dedicated ED25519 known-hosts pin, and validated Jellybase hostname plus hashed machine identity. As of 2026-08-11, `flutter-test` additionally uses Flutter's JSON machine reporter and summarizes its sandbox-local stream before SSH/MCP; the controller accepts only a bounded, versioned, terminally complete and internally consistent success object, never a `PASS` substring.

### Compact Flutter test proof

Evidence: `skills-control-plane/projects/jellyssh/evidence/flutter-test-compact-summary.json`

The frozen BUG-008 target `da96d24bf57daf47ee5f8a238e8c5f940f3cae3d` completed the unchanged restricted sandbox with 716 passed, 0 failed, 0 skipped, terminal `done`, process exit `0`, and protocol `0.1.1`. The summary was 854 bytes against a 4096-byte controller bound; the earlier raw MCP result was 263,513 characters and lost its terminal totals at the bridge. Two bounded read-only Flutter SDK stamp warnings are retained as diagnostics. CHI/JellySSH task-ID sets and both Jellybase JellySSH checkout heads/branches/clean-status digests matched before and after the proof.

### Preserved controller verdict

Evidence: `skills-control-plane/projects/jellyssh/evidence/reviewer-controller-smoke.json`

SHA-256: `c09e9ec2e7bd12b6887ad00645e6581bf871e1cffad473fe29d24a5a7462ed55`

Exact structured verdict: `BLOCK`.

Controller checks:

- sandbox self-check: PASS
- head clean: PASS
- exact diff: PASS
- recursive submodule state: PASS
- Dart format: PASS (`135 files`, `0 changed`)
- Flutter analyze: BLOCK
- Flutter test: BLOCK

The controller rejected an intermediate DeepSeek response that cited the virtual path `controller_evidence`; only tracked findings within the requested repository scope are accepted. The final accepted structured response returned `BLOCK` with the seven controller statuses and no model-authored findings. The exact analyzer findings remain separately recorded below from preserved check output. No unsupported PASS was accepted.

Conditional UI evidence: `skills-control-plane/projects/jellyssh/evidence/ui-controller-smoke.json`

SHA-256: `b3dd35ce1a4484ae5abee865af2a8774eab3a95daf50833b9c9684eb3b4ad09b`

The controller explicitly selected and verified `openrouter/google/gemini-3.1-pro-preview` with OpenRouter fallback disabled. It returned the same expected structural `BLOCK` because the accepted source quality checks remain blocked.

## Flutter/toolchain evidence

Machine-readable evidence: `skills-control-plane/projects/jellyssh/evidence/flutter-quality-gate.json`

SHA-256: `c13a8162abf39bab65a329985eba292bd154d28b4e483e3b8fb434a8ab82d4bf`

Installed without `sudo` under the `jellydev` account:

- Flutter `3.44.9`
- Dart `3.12.2`
- Temurin JDK `17.0.20+8`
- Android command-line tools `22.0`
- ADB/platform-tools `37.0.1`

Android platforms/build-tools and licence acceptance remain incomplete.

A disposable intake smoke completed `flutter pub get` and stopped at `flutter analyze` under `set -euo pipefail`; its subsequent `flutter test` did not run. The later restricted controller route invoked both analyze and test checks; both blocked on the same current-source incompatibilities.

Findings:

1. `app/lib/screens/groups/manage_groups_screen.dart:67` — deprecated `onReorder`.
2. `app/lib/screens/sftp/sftp_browser_screen.dart:58` — unawaited future.
3. `app/test/services/port_forward_service_test.dart:551` — missing concrete `SSHSocket.flush` implementation.
4. `app/test/services/sftp_service_test.dart:100` — synchronous fake `close` does not override `Future<void> SftpClient.close`.

These are accepted-intake/source-quality blockers. Phase 2 does not authorize fixing them.

## Repository authentication

Jellybase has a repository-specific public key with fingerprint:

`SHA256:OiEwRyQVvFLNPp8IkWqpOYAgT9d+0Spx5gsvRXlkOGE`

Direct GitHub SSH remains blocked with `Permission denied (publickey)`. The available GitHub token cannot administer deploy keys and returned `Resource not accessible by personal access token`. Bundle bootstrapping established isolated exact checkouts but does not authorize fetch, push, or development dispatch.

## Board

Board `jellyssh` remains setup-only:

- workdir: `/var/tmp/hermes-jellyssh`
- task count: `0`
- no ready, running, or development cards
- `auto_decompose=false`
- empty default assignee and orchestrator profile
- `max_spawn=1`
- `max_in_progress=1`

Board evidence is read through SQLite in read-only mode. No dispatch command was used.

## Verification

Latest completed mechanical verification:

- 43 unit and negative-boundary tests: PASS
- `projectctl scan`, `verify`, and `audit`: PASS
- Python compilation and `git diff --check`: PASS
- `projectctl plan` and Markdown/JSON status: expected exit `1` with explicit blockers
- changed/untracked credential scan: 51 regular files, zero symlinks, zero findings
- all four JellySSH checkouts: clean `main`, exact intake commit, exact origin
- controller DeepSeek and conditional Gemini routes: schema-valid BLOCK with seven controller checks each and exact response-model verification
- board: verified empty
- reviewer scratch directories: zero
- Phase 2 routable-state mutation: rejected
- descriptor-governance mutation: rejected
- exact-commit/worktree mutation bypass: rejected
- Git fsmonitor execution probe: rejected
- credential/pathspec probes: rejected

`projectctl plan` and status must remain blocked while repository authentication, Android readiness, and JellySSH source-quality gates are unresolved.

## Independent review state

The first full Phase 2 review batch produced:

- standards/code-quality review: timeout, no verdict;
- spec-compliance review: BLOCK with nine findings;
- reviewer-boundary/security review: timeout, no verdict.

The later completed batch `deleg_9ecba75a` returned three `BLOCK` verdicts. Its still-applicable findings identified project-bundle/profile-skill incoherence, missing-runtime exception leakage, incomplete atomic-write durability/cleanup, parent-directory diff credential leakage, the unproved conditional Gemini route, mutable-profile/controller races, semantic check-output gaps, missing controller component integrity pins, direct-API fallback/model-identity gaps, and self-referential host attestation. Historical-ref and the earlier systemd isolation findings had already been superseded by the exact base/target ref restriction and Docker route.

The current candidate remediates those findings with authoritative runtime bundles, project-authority skill hash comparison, structured missing-runtime digests, fsync plus failure cleanup, expansion and validation of every diff-emitted file, attribute-independent regular-blob materialization, complete base-to-target diff checking, exact-file finding validation, hash-bound specialist procedures, an explicit implementation-to-review handoff, an exercised Gemini route, one immutable in-memory profile snapshot, hash-pinned private MCP snapshots, before/after metadata and check semantics, response-model verification with fallback disabled, and pinned SSH host key/remote machine identity.

The final/code-quality controller route uses the project-owned `jellyssh-controller-evidence-review` procedure rather than the upstream tool-dependent `code-review` workflow. The adapter is explicitly designed for the complete diff and fixed checks pre-collected by the trusted controller, requires no model tools or subagents, and is hash-verified before prompting.

Procedure trees are captured once in memory; the controller hashes and prompts from those same captured bytes, eliminating a separate post-verification `SKILL.md` read.

On 2026-08-09 the operator temporarily disabled the separate adversarial security-review subagent because its upstream provider safety classifier rejected defensive audit prompts. No adversarial security-review prompt may be dispatched until the operator re-enables that lane.

Final review disposition under that operator policy:

- specification compliance: PASS; retained across the later localized code-quality fixes because implementation scope and architecture did not fundamentally change;
- standards/code quality: PASS on the final 51-file code candidate `sha256:dc7b73c5fc20adf58e7f78e191a070e7ca4f821a11f2dc576a6f3f7a86308993`, with no findings;
- adversarial security review: disabled by operator and not rerun.

## Rollback

Current target-profile rollback archive:

`/home/jellybot/.hermes/backups/jellyssh-phase2-20260809T075208+0100/jellyssh-target-profiles-verified.tar.gz`

Current archive SHA-256: `a2c66f577bc45228326eab64da77921a2e345ee93c372225b2295eb24ac4af40`

Mode: `0600`.

Rollback removes the two isolated profiles, the empty board, and `/var/tmp/jellyssh-review-runtime`. It does not modify `jellybase_hermes`, global skills, global Hindsight routes, LogK, Hermes Agent source, or JellySSH source.

## Hard stop

Do not create or dispatch a JellySSH development card. No product implementation, merge, release, signing, sideloading, deployment, production operation, privilege escalation, or `sudo` action occurred.
