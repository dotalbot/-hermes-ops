# JellySSH Phase 2 routing setup plan

**Date:** 2026-08-09

**Branch:** `feat/jellyssh-phase2-routing`

**Authority:** Accepted Phase 1 governance in `docs/operations/multi-agent-development/jellyberry-kanban-orchestration-design-v3.md`

## Goal

Prepare a fail-closed JellySSH route without creating or dispatching any development card.

## Authorized scope

- Record Phase 1 acceptance and Phase 2 authorization.
- Implement the minimum Git-backed Skill Control Plane and deterministic `projectctl` read-only commands.
- Materialize exact core/capability/overlay/project manifests with real hashes.
- Generate machine-readable and Markdown status views.
- Prepare independent JellySSH implementation and review checkouts.
- Create and configure the named implementation and reviewer profiles.
- Bind the project bank and conservative retention.
- Promote only accepted skills into named profiles with rollback/provenance evidence.
- Create a `jellyssh` board containing no executable development card.
- Run positive and negative profile/model/bank/skill/workspace/guard/reviewer-boundary tests.
- Commit and push the Phase 2 branch after independent review.

## Non-goals

- No JellySSH source-code change.
- No Phase 3 ticket selection, design, implementation, or dispatch.
- No LogK change.
- No Hermes Agent source change.
- No Hindsight server/configuration change or broad memory seeding.
- No PR, merge, release, signing, sideloading, deployment, sudo, production data, or secret output.
- No Desktop plugin, cron audit, automatic promotion, or automatic decomposition.

## Implementation sequence

1. Preflight live profiles, banks, model catalogue, SSH identity, repository remote/default branch, paths, toolchain, and GitHub access.
2. Add deterministic control-plane catalog/release/pack/project manifests plus `projectctl` and tests.
3. Run `scan` and `plan`; review exact proposed side effects.
4. Establish private repository authentication and clone exact clean implementation/review checkouts.
5. Create profiles from the reviewed generic baseline and then narrow them deliberately.
6. Add project-local bank configuration and accepted skills; record hashes and rollback copies.
7. Enforce reviewer access through a restricted read-only MCP adapter while disabling arbitrary terminal/file/code tools.
8. Create the board with the verified path bridge required by Hermes's single-host Kanban workspace resolver; create no cards.
9. Run fresh-session and negative smoke tests.
10. Generate status/evidence, independently review, commit, push, and stop.

## Known preflight findings

- Jellybase is reachable as non-privileged `jellydev`.
- `/home/jellydev/dev_projects` and the JellySSH checkout were absent at Phase 2 start.
- `jellyssh-main` exists on central Hindsight.
- Flutter, Dart, ADB, and Java were absent on Jellybase at Phase 2 start; setup must be grounded in the repository's actual requirements.
- A repository-specific Jellybase SSH key was generated, but GitHub deploy-key registration is currently blocked because the available token cannot access the repository Administration/deploy-key endpoint. Do not copy a personal private key as a workaround.
- Hermes Kanban resolves `dir`/`worktree` paths on Jellyberry before spawning an SSH-backed profile. A remote-only `/home/jellydev/...` board path is therefore not natively path-stable. Phase 2 must implement and negative-test an explicit same-absolute-path bridge or block routing.

## Verification

- Unit tests for schema, hashes, scan/plan/status, missing assets, shadowing, drift, overlay compatibility, and non-routable states.
- Repository and toolchain checks on both hosts.
- Fresh implementation/reviewer profile sessions report exact model/provider/bank/retention.
- Reviewer cannot invoke terminal/file/write/code tools or access the implementation checkout through its restricted adapter.
- Board readback shows zero tasks and no ready/running cards.
- Conservative global dispatcher settings remain unchanged.
- No LogK or unauthorized runtime artifact changes.
- Independent non-implementation-model review of repository and runtime evidence.
