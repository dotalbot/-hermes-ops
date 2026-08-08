# Hindsight bank routing and hygiene update

Date: 2026-08-08
Status: applied with follow-up cleanup pending

## Context

The home directory was reorganized so coding/git checkouts live under:

- `/home/jellybot/dev_projects`

Non-git project/activity folders live under:

- `/home/jellybot/projects`

This layout is intended to be replicated on other agent hosts.

A Hermes Desktop session named `Organizing Project Directory Structure` confirmed this cleanup. The session source was Desktop and the session ID was `20260808_010333_2258fd`.

## Live Hindsight state checked

Hindsight is centralized on `jellyhome`:

- API: `http://jellyhome:18888`
- LAN API: `http://192.168.1.1:18888`
- UI: `http://192.168.1.1:9999`
- Runtime version: `0.9.0`
- Runtime image: `ghcr.io/vectorize-io/hindsight:0.9.0`

Known banks after the update include:

- `hermes-main`
- `home-network-main`
- `jellybase-worker-main`
- `global-dominic`
- `logk-main`
- `jellyfood-main`
- `jellyssh-main`
- `portfolio-intel-main`

## Issue found: new bank creation failed before shm fix

Creating `jellybase-worker-main` initially failed with PostgreSQL shared-memory errors inside the Hindsight container:

```text
could not resize shared memory segment ... to 533795040 bytes: No space left on device
```

The host had plenty of disk and host `/dev/shm`, but the container used Docker's default 64 MiB `/dev/shm`.

Fix applied:

- Added `shm_size: "1gb"` to the `hindsight` service in `docker/hosts/jellyhome.yaml`.
- Patched the live `/opt/docker/hosts/jellyhome.yaml` runtime copy on `jellyhome`.
- Recreated only the `hindsight` container using the base + host Compose overlay.

Verification:

- Container `ShmSize=1073741824`.
- In-container `/dev/shm` reported `1.0G`.
- Hindsight API `/version` returned `0.9.0` after restart.
- `jellybase-worker-main` bank creation succeeded after the fix.

## Profile-to-bank routing after update

Current intended mapping:

- `default` -> `hermes-main`
  - Cross-cutting Hermes operating memory, profile behavior, tool conventions, Desktop/session/Kanban policy, and memory policy.
- `homenetworkworker` -> `home-network-main`
  - Home-network/homelab infrastructure, monitoring, backup/restore, deployment, and operational runbooks.
- `jellybase_hermes` -> `jellybase-worker-main`
  - Durable reusable remote-worker facts for Jellybase implementation work.
  - Configured with `auto_recall=true` and `auto_retain=false` to prevent implementation-task noise until retention behavior is proven.
- `hindsightpilot` -> removed
  - Exported first, then deleted because it was writing pilot/test memory into `hermes-main`.

Backup/export location:

```text
/home/jellybot/.hermes/backups/hindsight-bank-routing-20260808T001954Z/
```

## Multi-bank agent support

The Hermes Hindsight provider supports `bank_id_template` with placeholders including:

- `{profile}`
- `{workspace}`
- `{platform}`
- `{user}`
- `{session}`

Policy:

- Prefer explicit profile-to-bank mapping for now.
- Test `{workspace}` before relying on it across CLI, Desktop, gateway, and Kanban contexts.
- Avoid `{session}` by default because it creates fragmented banks.
- Use short-lived task/eval/lab banks only when intentionally isolating noisy experiments.

## 0.6.2 vs 0.9.0 knowledge policy

Historical 0.6.2 facts are not inherently wrong. Keep them when they are framed as history, for example:

- Hindsight was upgraded from `0.6.2` to `0.9.0`.
- The pre-upgrade backup path existed before the recreate.

Cleanup targets are stale current-state observations, for example:

- statements saying the current Hindsight runtime is `0.6.2`;
- old endpoint/current-version statements that conflict with `0.9.0`;
- duplicated runtime snapshots that crowd out the current canonical fact.

Desired recall behavior:

- Query: `current Hindsight version`
- Expected current answer: `0.9.0`
- Historical `0.6.2` facts may appear only as upgrade history, not as current state.

## Hermes-main pollution policy

`hermes-main` is too broad and should be narrowed. Do not bulk-delete.

Safe cleanup sequence:

1. Export/list `hermes-main` into a dated backup file.
2. Generate read-only candidate reports for:
   - home-network facts in `hermes-main`;
   - stale `0.6.2` current-state facts;
   - duplicate/perishable operational facts;
   - `/tmp`, PID, task-ID, tmux, branch-status, and one-off service-health snapshots.
3. Manually review candidates before destructive writes.
4. Retain high-value durable home-network facts into `home-network-main` where useful.
5. Delete or neutralize only approved stale/noisy observations.
6. Verify recall before and after.

No bank-wide delete should be used for this cleanup.

## Maintenance routine

Recommended recurring maintenance:

- Monthly read-only bank audit.
- Check bank counts and last-write timestamps.
- Run recall probes:
  - `current Hindsight version`
  - `home-network source path`
  - `jellybase_hermes memory bank`
  - `how should Hermes route Hindsight banks`
- Produce candidate reports only.
- Require explicit approval before memory mutations.

## Follow-up work

- Commit/push the `home-network` `shm_size` source change after reconciling the concurrent home-directory path cleanup changes.
- Run the `hermes-main` read-only pollution audit and review the candidate cleanup bundle before deleting any memories.
- Verify workspace-derived `bank_id_template` behavior in Desktop/CLI/gateway/Kanban before using dynamic project-bank routing.
