# Jellybase SSH backend file-sync fix plan

## Goal
Enable the Jellyberry `jellybase_hermes` Kanban worker to execute terminal commands over LAN SSH to `jellydev@192.168.1.2` without reading, writing, uploading to, or downloading the existing Jellybase `~/.hermes` tree.

## Root cause
Hermes `SSHEnvironment` currently creates a `FileSyncManager` for every SSH backend and cleanup calls `sync_back()`. Its bulk download tars the complete remote `~/.hermes`. On Jellybase that directory is 2.2 GiB, causing an unsuitable transfer and violating the required remote-state boundary.

## Scope
- Add a profile-configurable SSH file-sync opt-out.
- Default remains backward-compatible for existing SSH backend users.
- Configure only `jellybase_hermes` to opt out.
- Preserve LAN SSH, Kanban routing, remote terminal execution, and no-sudo policy.

## Non-goals
- No changes to Jellybase's existing Hermes installation or credentials.
- No remote account creation.
- No upstream PR or merge.

## Acceptance criteria
- With opt-out enabled, SSH environment setup neither creates nor synchronizes remote `~/.hermes` transport state.
- Cleanup does not tar/download remote `~/.hermes`.
- Existing default file-sync behavior remains covered by tests.
- `jellybase_hermes` completes the read-only Spawner connectivity card over `192.168.1.2` and reports the requested system facts without sudo.

## Verification
1. Add regression tests for the opt-out and legacy default behavior.
2. Run focused SSH-environment and terminal-config bridge tests.
3. Run an actual `jellybase_hermes` Kanban task and verify the result, worker logs, and no active large tar transfer.

## Rollback
Set `terminal.ssh_file_sync: true` in the `jellybase_hermes` profile, or remove the local patch by reverting its commit and restarting the gateway.
