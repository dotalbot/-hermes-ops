# ADR: Guarded Mission Control write actions

Status: Proposed
Date: 2026-05-29

## Context

Mission Control currently belongs on the safe/read-only side of Hermes operations unless a separate implementation explicitly enables guarded write actions. Operators want a single place to inspect operational state and request common maintenance actions, but those actions can restart processes, mutate runtime state, or exercise backup/restore paths.

This ADR defines the approval and safety model before any dangerous action is implemented. It is intentionally design-only: no write, destructive, restart, restore, Docker, collector, or backup-health action may execute from Mission Control until a later implementation task adds the guarded path and passes review.

## Decision

Mission Control dangerous actions must use a guarded approval model.

The UI/API may present candidate write actions as requestable operations, but the default behavior is read-only design mode. A request may only become executable after all of these are true:

1. The user has explicitly approved the exact action in the current approval flow.
2. The approval screen displays the exact command or operation descriptor that will run.
3. The approval screen displays the target host, target service or subsystem, rollback plan, risk level, and expected side effects.
4. Secrets, tokens, environment values, and credential-bearing paths are redacted from all previews, logs, notifications, and stored approval records.
5. The backend validates that the approved action matches an allowlisted action template and target.
6. The executor re-checks approval immediately before execution and refuses stale, replayed, or modified requests.

Explicit rule: no destructive or write action may execute without user approval. If the system cannot prove approval for the exact command, target host, parameters, and risk level, it must refuse the action and remain read-only.

## Scope

This ADR covers the first guarded-action design for these candidate Mission Control actions:

- Restarting Hermes gateway and dashboard services.
- Rerunning selected collectors.
- Triggering backup health checks.
- Triggering restore drills.
- Recreating selected Docker services.

The ADR applies to Mission Control UI flows, API routes, worker/executor handoff records, logs, notifications, and any future automation that tries to call the same write-action backend.

## Candidate action classes

### Restart Hermes gateway/dashboard

Risk level: medium to high, depending on whether the operation interrupts active sessions.

Required preview fields:

- Exact restart command or service-management action.
- Target host.
- Target service name, such as gateway or dashboard.
- Expected downtime and health-check command.
- Rollback plan, such as restarting the previous service definition or restoring the prior process state if supported.

Approval path:

- User approval required in Mission Control before execution.
- For remote hosts, the approval must identify the remote host and runtime account.
- The executor must verify it is operating on the approved host before running anything.

### Rerun collectors

Risk level: low to medium, depending on whether the collector writes generated outputs or triggers external API usage.

Required preview fields:

- Exact collector command or job identifier.
- Target host and output path.
- Whether the collector writes tracked repo artifacts, runtime cache, database rows, or dashboard data.
- Expected API calls or rate-limit considerations.
- Rollback plan, such as restoring the previous generated artifact or marking output stale.

Approval path:

- User approval required for every collector rerun that writes files, updates a database, pushes commits, refreshes dashboard data, or contacts external services with side effects.
- Read-only collector dry runs may remain available without write approval if they cannot mutate local or remote state.

### Trigger backup health checks

Risk level: medium.

Required preview fields:

- Exact health-check command.
- Backup target or repository being checked.
- Target host and runtime user.
- Whether the command is read-only or may repair, prune, lock, rewrite, or upload metadata.
- Rollback plan for stale locks or failed checks.

Approval path:

- User approval required before any backup-health command runs.
- Commands must default to non-mutating checks unless the user separately approves a mutating repair or prune operation.
- Any output containing repository paths, hostnames, or operational metadata must be reviewed for secret leakage before display or persistence.

### Trigger restore drills

Risk level: high.

Required preview fields:

- Exact restore-drill command.
- Backup repository or snapshot source.
- Restore target host and restore destination path.
- Confirmation that the destination is a drill/staging path, not a production overwrite path.
- Validation command after restore.
- Cleanup and rollback plan.

Approval path:

- User approval required.
- A restore drill must refuse to run if the destination path overlaps production data unless a separate high-risk approval path is implemented.
- The approval prompt must call out that restore drills may read sensitive backup contents and create local recovered files.

### Recreate selected Docker services

Risk level: high.

Required preview fields:

- Exact `docker compose` or deployment command.
- Target host, compose project, compose file path, and service names.
- Whether volumes, networks, images, secrets, ports, or environment variables are affected.
- Health-check command after recreation.
- Rollback plan, such as prior image tag, previous compose commit, or `docker compose up -d` from the known-good checkout.

Approval path:

- User approval required before any container recreate, rebuild, pull, restart, or service-management command runs.
- The executor must never run broad `docker compose down`, volume removal, image pruning, or orphan cleanup through this first model.
- Selected-service recreation must be allowlisted by service and host.

## Threat model

The guarded model must address these threats:

- Accidental clicks or mistaken target selection.
- Prompt injection or malicious dashboard data causing Mission Control to propose a dangerous command.
- Stale approvals being replayed after the visible command or target changed.
- Confused-deputy execution where a read-only UI route indirectly triggers a write action.
- Command injection through service names, hostnames, collector identifiers, paths, or user-provided parameters.
- Secret disclosure through command previews, environment variables, logs, approval records, notifications, or error messages.
- Unauthorized use by someone with dashboard access but no permission to perform host-level operations.
- Over-broad Docker or backup commands causing destructive state changes.
- Partial failure leaving services stopped, generated data half-written, or restore artifacts exposed.

## Required approval paths

All dangerous actions require an explicit user approval path. A compliant approval path includes:

1. A read-only preparation step that builds a structured action proposal.
2. A human-readable approval view that shows:
   - Action name.
   - Exact command or normalized operation descriptor.
   - Target host.
   - Target service, collector, backup repository, or restore destination.
   - Risk level: low, medium, high, or destructive-prohibited.
   - Expected side effects.
   - Rollback plan.
   - Secret-redaction statement.
3. A user approval event bound to the proposal hash, user identity, timestamp, and expiry.
4. Backend validation that the proposal hash, allowlist entry, parameters, host, and risk level still match immediately before execution.
5. A refusal path that explains why execution was denied without leaking secrets.

Approval must be per action. Bulk approvals, standing approvals, cron-triggered approvals, and model-only approvals are out of scope.

## Guardrails

Implementation must enforce these guardrails before any write action is enabled:

- Read-only default: Mission Control ships with proposals and documentation only until the guarded executor is separately implemented and enabled.
- Exact command display: the user must see the exact shell command, or a lossless normalized operation descriptor when the implementation does not use shell commands.
- Host display: the user must see the exact target host and runtime account or execution context.
- Rollback display: every approval screen must show a rollback or recovery plan. If rollback is not possible, the screen must say so and raise the risk level.
- Risk labeling: every proposal must carry a visible risk level and the backend must reject missing risk labels.
- Secret redaction: secrets must be redacted before display, logging, notifications, and persistence. When exact-match audit verification requires a stored fingerprint, persist only a non-reversible keyed digest derived from the normalized pre-redaction proposal; never persist the raw secret-bearing form. Redaction must cover tokens, passwords, API keys, private keys, secret file contents, and credential-bearing environment values.
- Allowlisted actions only: no arbitrary command text from the UI, LLM output, dashboard data, or request body may be executed.
- Parameter validation: service names, hosts, paths, collector names, and backup identifiers must be selected from allowlists or validated against strict schemas.
- Short-lived approvals: approvals must expire quickly and be single-use.
- Revalidation: the executor must re-fetch and revalidate the proposal before execution.
- Audit trail: approved and refused actions must be recorded with redacted command, action id, target, risk level, approver, timestamp, and result.
- Safe failure: if validation, redaction, audit logging, or health checks fail, the action must stop before mutation when possible and report a safe error.

## Non-goals

This ADR does not approve or implement write execution.

This ADR does not cover:

- Autonomous execution of dangerous actions.
- LLM-only approval or policy decisions.
- Destructive backup pruning, volume deletion, broad Docker cleanup, or production restore overwrites.
- A general-purpose remote shell in Mission Control.
- Privilege escalation, sudo password handling, or host credential management.
- Multi-user role-based access control beyond requiring explicit approval identity in the future design.
- Replacing existing manual operator workflows.

## Consequences

Benefits:

- Mission Control can grow toward operational actions without weakening the read-only safety boundary.
- Users see exactly what will happen before approving.
- Dangerous commands become allowlisted, auditable, and easier to review.
- Secret leakage is treated as a design constraint rather than an afterthought.

Costs:

- Every action needs a proposal schema, allowlist entry, redaction tests, approval UI, and executor validation.
- Some useful actions will remain manual until the guarded path is implemented.
- High-risk operations require more confirmation text and rollback documentation.

## Verification expectations for implementation

A future implementation should include tests for:

- Refusing execution without approval.
- Refusing stale, expired, replayed, or modified approvals.
- Refusing unknown hosts, services, collectors, backup targets, and paths.
- Displaying exact command or normalized operation descriptor.
- Displaying target host, risk level, rollback plan, and secret-redaction behavior.
- Redacting secrets from previews, logs, audit records, notifications, and errors.
- Keeping Mission Control read-only when the guarded executor is disabled.

## Open questions

- What is the exact identity provider for approval events: local Hermes user, Discord user, dashboard session, CLI token, or another source?
- Should high-risk actions require a second confirmation phrase or out-of-band confirmation?
- Where should approval audit records live, and how long should they be retained?
- Which hosts and services are in the first allowlist?
- How should Mission Control represent non-shell operations so they are as reviewable as exact commands?
- What timeout should approvals use for each risk level?
- Should backup health checks and restore drills have separate dry-run-only modes before write-capable modes exist?

## Follow-up implementation tasks

- Define the action proposal schema and proposal hash rules.
- Build a read-only Mission Control proposal API that returns candidate actions without executing them.
- Add UI affordances for risk level, exact command, target host, rollback plan, and secret-redaction behavior.
- Implement a secret-redaction library with tests and conservative failure behavior.
- Define host/service/collector/backup allowlists.
- Implement a guarded executor behind a disabled-by-default feature flag.
- Add audit records for approved, refused, failed, and completed actions.
- Add end-to-end tests proving dangerous actions cannot execute without explicit approval.
