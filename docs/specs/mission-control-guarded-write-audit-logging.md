# Mission Control guarded write audit logging

Status: proposed implementation spec
Date: 2026-05-29
Related decision: `docs/decisions/guarded-mission-control-write-actions.md`
Primary output path: `docs/specs/mission-control-guarded-write-audit-logging.md`

## Purpose

Define the concrete audit trail for every Mission Control guarded write request, approval decision, and execution outcome.

This spec is design-only. It does not authorize live write actions. It defines what must be logged once guarded write actions are implemented.

## Goals

- Log every guarded write request and every approval decision with a stable event schema.
- Preserve a durable, reviewable trail across repo records, session logs, and Hindsight without storing secrets.
- Make replay, stale approval, and partial-failure investigations possible from redacted records.
- Give implementation a concrete contract: event names, required fields, status transitions, sink behavior, and examples.

## Non-goals

- Enabling destructive actions.
- Storing raw secrets, raw environment values, or full credential-bearing script bodies.
- Replacing the source-controlled design docs with Hindsight.
- Defining RBAC or identity-provider details beyond the fields the log must capture.

## Logging model

Treat audit logging as a first-class guardrail, not as an afterthought.

Each guarded write request produces:

1. One canonical append-only event stream.
2. One per-request repo record that mirrors the canonical stream in human-reviewable form.
3. One session-log trace for operator/session reconstruction.
4. Narrow Hindsight milestone summaries for later recall.

If canonical logging fails before mutation starts, the action must fail closed.

## Canonical identifiers

Every request uses these identifiers:

- `request_id`: stable id for the entire guarded write request. Format: ULID string. Generated when the proposal is created.
- `event_id`: stable id for one audit event. Format: ULID string. New per event.
- `correlation_id`: stable id shared by all events tied to the same user-visible action flow. Usually equal to `request_id`, but keep separate so a future workflow can link retries or mirrored systems.
- `approval_id`: id for one explicit approval or denial decision. Present on decision events.
- `execution_id`: id for one executor attempt. Present on execution events.
- `session_id`: Hermes session or dashboard session id if available.
- `trace_id`: optional distributed trace id if the API/UI/executor stack later adopts one.

Rules:

- `request_id` never changes after proposal creation.
- A retried execution for the same approved request keeps `request_id` and gets a new `execution_id`.
- A new approval after expiry or denial creates a new `approval_id` but not a new `request_id` if the proposal itself is unchanged.
- Any material change to command, target, risk level, rollback plan, or side effects invalidates the old request and requires a new `request_id`.

## Event names

Use these exact event names:

- `guarded_write.request_proposed`
- `guarded_write.approval_granted`
- `guarded_write.approval_denied`
- `guarded_write.approval_expired`
- `guarded_write.tmp_script_generated`
- `guarded_write.execution_started`
- `guarded_write.execution_completed`
- `guarded_write.execution_failed`
- `guarded_write.audit_sink_failed`
- `guarded_write.audit_sink_recovered`

Notes:

- The acceptance criteria require examples for proposed, approved, denied, expired, `/tmp` script generated, and completed. The failure events are included because implementation will need them.
- `execution_completed` covers both success and completed-with-warnings by a status field.
- `execution_failed` is for executor failure after an execution actually started.

## Canonical event schema

Every canonical audit event is a JSON object with these top-level fields.

### Required for every event

- `event_version`: integer. Start at `1`.
- `event_id`
- `event_name`
- `occurred_at`: UTC ISO-8601 timestamp.
- `request_id`
- `correlation_id`
- `status_from`: previous request status or `null` for the first event.
- `status_to`: new request status.
- `actor`: object; see below.
- `action`: object; see below.
- `target`: object; see below.
- `redaction`: object; see below.
- `sinks`: object; emit-time sink attempt results for this event only.

### Conditionally required

- `approval`: required on approval granted, denied, expired.
- `execution`: required on tmp-script-generated, execution-started, execution-completed, execution-failed.
- `error`: required on execution-failed and audit-sink-failed; optional otherwise.
- `result`: required on execution-completed and execution-failed.
- `reason`: required on approval-denied, approval-expired, execution-failed, and audit-sink-failed.

### `actor`

Required fields:

- `type`: one of `dashboard_user`, `cli_user`, `agent`, `system`.
- `id`: stable user/account/profile/session principal.
- `display`: safe short label if available.
- `source`: where the request originated, such as `mission-control-ui`, `hermes-cli`, `discord-gateway`, `internal-worker`.

Rules:

- Store identity handles, not secrets or bearer tokens.
- If the actor came from a messaging platform, log platform user id and display handle, never raw access tokens.

### `action`

Required fields:

- `action_id`: allowlisted action key such as `restart-hermes-dashboard`.
- `template_id`: immutable template/version key such as `restart-hermes-dashboard@v1`.
- `kind`: one of `service_restart`, `collector_rerun`, `backup_check`, `restore_drill`, `docker_recreate`, or another future allowlisted class.
- `risk_level`: `low`, `medium`, `high`, or `destructive_prohibited`.
- `command_preview_redacted`: exact command preview after redaction, or a lossless operation descriptor when shell is not used.
- `command_fingerprint`: non-reversible HMAC-SHA-256 of the normalized pre-redaction command/descriptor plus template version, using a server-held audit key.
- `side_effects_summary`: short human-readable list of expected side effects.
- `rollback_summary`: short human-readable rollback or recovery plan.
- `approval_ttl_seconds`

Rules:

- Do not store raw argv, raw env, or raw script body in the audit event.
- `command_preview_redacted` must preserve operator reviewability without leaking secrets.
- `command_fingerprint` is a persisted keyed digest, not a plain hash, so implementation can detect drift without storing the secret-bearing raw command.
- The pre-redaction normalized command/descriptor may exist briefly in memory for validation, but it must not be persisted to any sink.

### `target`

Required fields:

- `host`: approved host identifier.
- `environment`: such as `homelab`, `local`, `docker`, `tailnet`.
- `service_or_scope`: service, collector, backup target, or restore scope label.
- `path_labels`: array of sanitized path labels when paths matter.
- `remote_account`: approved runtime account label if relevant.

Rules:

- Paths must be sanitized labels or redacted placeholders when they reveal sensitive filesystem layout.
- The executor may know the real path; the log stores only the minimal safe representation.

### `approval`

Required fields:

- `approval_id`
- `decision`: `granted`, `denied`, `expired`.
- `approved_at` or `decided_at`
- `expires_at`
- `approver_asserted_identity`: safe identity label.
- `proposal_fingerprint`: non-reversible HMAC-SHA-256 fingerprint of the approved proposal contents.

Optional:

- `confirmation_phrase_used`: boolean.
- `denial_reason_code`: short safe code such as `operator_cancelled`, `risk_rejected`, `timeout`, `ui_closed`.

Rules:

- Never store typed confirmation phrases verbatim.
- Store reason codes or short sanitized text, not free-form secret-bearing notes.

### `execution`

Required fields when present:

- `execution_id`
- `executor_type`: `tmp_script`, `direct_argv`, `worker_job`, `remote_runner`
- `executor_host`: actual executor host label.
- `host_verified`: boolean.
- `started_at` or `generated_at` depending on the event.

Optional depending on event:

- `tmp_script_path`: basename or safe path under `/tmp`.
- `tmp_script_sha256`
- `tmp_script_bytes`
- `pid` if safe and useful.
- `duration_ms`
- `exit_code`
- `stdout_summary`
- `stderr_summary`
- `health_check_summary`

Rules:

- Log script hash, size, and safe path; do not log full script body.
- `stdout_summary` and `stderr_summary` must be bounded and redacted.
- Large raw output belongs in process-local logs, not Hindsight or repo records.

### `redaction`

Required fields:

- `ruleset_version`
- `applied`: boolean
- `fields_redacted`: array of dotted field names or categories.
- `secret_classes_checked`: array containing any of `token`, `password`, `api_key`, `private_key`, `cookie`, `env_value`, `secret_path`, `url_credential`, `raw_script_body`.
- `redaction_ok`: boolean

Rules:

- If redaction fails or the system cannot prove redaction ran, the action must not execute.
- `fields_redacted` may name categories like `action.command_preview_redacted` or `execution.stdout_summary`; it must not leak the removed value.

### `sinks`

`sinks` records what happened for this specific event emission attempt. It is not a mutable lifecycle summary for the whole request.

Allowed values per sink:

- `written_this_event`
- `deferred_from_event`
- `not_attempted_in_event`
- `skipped`
- `failed_safe`

Rules:

- Later mirror success/failure is recorded by later events, usually `guarded_write.audit_sink_failed` or `guarded_write.audit_sink_recovered`.
- Do not rewrite older events to change sink state.

### Sink-failure/recovery event fields

`guarded_write.audit_sink_failed` and `guarded_write.audit_sink_recovered` must also include:

- `sink_event.sink_name`: one of `canonical_ledger`, `session_log`, `repo_record`, `hindsight`.
- `sink_event.sink_role`: `primary` or `secondary`.
- `sink_event.detected_at`
- `sink_event.fallback_recorded_in`: array of sinks or local mechanisms that still captured the incident.

Rules:

- Sink events are status-neutral for the request unless they directly caused a `refused` transition before mutation.
- `guarded_write.audit_sink_recovered` normally keeps `status_from == status_to`.

### `result`

Required on terminal execution events:

- `outcome`: `succeeded`, `succeeded_with_warnings`, `failed`, `refused_before_mutation`.
- `mutation_started`: boolean.
- `postcheck_ok`: boolean or `null`.
- `summary`: short safe summary.

### `error`

Required on failure events:

- `class`: stable implementation error class or category.
- `safe_message`: sanitized message safe for repo/session/Hindsight.
- `retryable`: boolean.

## Request status machine

Use this request status progression.

- `draft` — internal proposal object exists but is not yet shown for approval.
- `proposed` — proposal shown or emitted for approval.
- `approved` — explicit approval granted and not yet consumed.
- `denied` — explicit denial recorded.
- `expired` — approval window ended before execution.
- `script_generated` — `/tmp` execution script was generated for an approved request.
- `running` — execution started.
- `completed` — execution finished successfully.
- `completed_with_warnings` — execution finished but post-checks or sink mirrors reported non-blocking issues.
- `failed` — execution started and ended unsuccessfully.
- `refused` — system refused to proceed before mutation because validation, audit, or redaction failed.

Allowed transitions:

- `draft -> proposed`
- `proposed -> approved`
- `proposed -> denied`
- `proposed -> expired`
- `denied -> proposed` only when the operator explicitly reopens the unchanged request for another review cycle
- `expired -> proposed` only when the unchanged request is reissued for another approval window
- `approved -> script_generated`
- `approved -> running` for direct argv execution with no tmp script
- `script_generated -> running`
- `running -> completed`
- `running -> completed_with_warnings`
- `running -> failed`
- `approved -> refused`
- `script_generated -> refused`
- `running -> refused` is not allowed once mutation has started; use `failed`

Rules:

- A `denied -> proposed` or `expired -> proposed` transition keeps the same `request_id` only if action id, target, risk level, rollback summary, and normalized command/descriptor are unchanged.
- If any of those fields changed, create a new `request_id` instead of reopening the old request.

## Sink design

### 1. Canonical durable ledger

This is the primary audit sink. It must succeed before mutation.

Recommended implementation target:

- Append-only JSONL file outside git, for example:
  - `/home/jellybot/.hermes/state/guarded-write-audit/guarded-write-events.jsonl`
  - or the equivalent runtime appdata path if Mission Control owns its own state directory.

Behavior:

- Append one line per canonical event.
- `fsync` after proposal, approval decision, and execution-started events.
- Rotate by size/date, but keep logical continuity through the same schema.
- If append or `fsync` fails on proposal/approval/execution-started, move request to `refused` and do not mutate.
- If append fails after mutation has already started, continue trying to mirror to session log and repo record, raise `guarded_write.audit_sink_failed` if the canonical ledger recovered enough to accept that event, and mark completion as `completed_with_warnings` or `failed` depending on the real outcome.
- If the canonical ledger is completely unavailable, fall back to a best-effort local process log and session log entry for operator diagnosis, but do not pretend the canonical event was durably recorded.

### 2. Repo record

This is the reviewable human-facing mirror.

Recommended implementation target in `hermes-ops`:

- `docs/reports/mission-control-guarded-write-audit/YYYY-MM/<request_id>.md`

Behavior:

- One markdown file per request.
- Frontmatter or embedded JSON summary may include request metadata and terminal outcome.
- Append a chronological event table or bullet log using the canonical event fields.
- Never write raw secrets, raw script body, full env values, or unbounded output.
- Repo-record write failure does not block execution if the canonical durable ledger succeeded.
- If the repo is unavailable or dirty, write a safe warning event and rely on the primary ledger plus session log.

Reasoning:

- The repo record is for durable review, audits, and later documentation work.
- It should not be the only sink because git availability and workspace cleanliness are operational concerns, not safety gates.

### 3. Session log

This is the operator trace within Hermes/dashboard activity.

Behavior:

- Emit a structured log record for every canonical event in the active session or request trace.
- Keep the same `request_id`, `event_id`, `approval_id`, and `execution_id` so session reconstruction matches the durable ledger.
- Include bounded summaries of validation failures, execution start, post-checks, and sink-mirror issues.
- Session log failure alone does not block execution if the canonical durable ledger succeeded.

### 4. Hindsight

This is the recall layer, not the authority.

Store milestone summaries only for:

- `request_proposed`
- `approval_granted`
- `approval_denied`
- `approval_expired`
- `execution_completed`
- `execution_failed`

Do not store:

- Full event streams.
- Raw output tails.
- Full command previews when they contain sensitive structure.
- `/tmp` script body.
- Transient sink-delivery chatter.

Recommended retained content shape:

- One concise summary sentence.
- Tags such as `mission-control`, `guarded-write`, action kind, target host, and final outcome.
- A pointer back to the canonical repo record path or request id.

Example Hindsight summary text:

- `Mission Control guarded write request 01J... to restart hermes-dashboard on jellyberry was approved by dominic, executed successfully, and recorded in hermes-ops audit records.`

Rules:

- Hindsight failure is non-blocking if the canonical durable ledger succeeded.
- Hindsight must never become the sole source of truth for whether a dangerous action was approved.

## Redaction rules

Redaction must run before anything is persisted to any sink.

Always redact or omit:

- API keys, bearer tokens, passwords, cookies, private keys, recovery codes.
- Raw environment variable values.
- Secret-file contents.
- URL credentials.
- Command arguments whose literal values are secrets.
- Full script body for generated `/tmp` scripts.
- Full stdout/stderr when they may contain secret material.
- Arbitrary user-supplied free text unless explicitly sanitized.

Allowed to persist when safe:

- Allowlisted action id and template id.
- Host and service labels.
- Redacted command preview.
- Command fingerprint/hash.
- `/tmp` script basename or safe path.
- `/tmp` script SHA-256 and size.
- Short bounded stdout/stderr summaries after redaction.
- Safe error classes and safe error messages.

Required redaction transforms:

- Secret values -> `"[REDACTED]"`
- Sensitive filesystem paths -> preserve only safe label where needed, for example `"restore_staging_path"` instead of the full path if the full path is considered sensitive.
- Confirmation text -> store `confirmation_phrase_used: true` instead of the phrase.
- Script body -> replace with hash, byte length, and template id.

Fail-closed conditions:

- Redactor crashed.
- Redactor cannot classify a field that might contain a secret.
- Command preview cannot be safely rendered.
- Output summarizer exceeds size limits without safe truncation.

## Failure handling

### Before mutation

Refuse execution and move the request to `refused` when any of these happen before mutation starts:

- proposal cannot be durably logged to the canonical ledger;
- approval decision cannot be durably logged;
- redaction fails;
- proposal fingerprint no longer matches approved fingerprint;
- approval expired;
- target validation fails;
- repo mirror tries to block canonical logging due to an implementation bug.

Logging note:

- If the canonical ledger is still writable, also emit `guarded_write.audit_sink_failed` with the sink name and failure category.
- If the canonical ledger itself is unavailable, record the refusal only in best-effort fallback channels such as the local process log and session log, then surface a safe error to the operator.

### After mutation starts

If the underlying action already started:

- preserve the real execution outcome;
- keep trying to emit canonical, session, and repo-mirror records;
- mark `completed_with_warnings` if the action succeeded but one or more secondary sinks failed;
- mark `failed` if the underlying action failed, even if logging later succeeds.

### Sink priority order

1. Canonical durable ledger — mandatory.
2. Session log — strong preference, non-blocking if canonical succeeded.
3. Repo record — non-blocking mirror.
4. Hindsight — non-blocking recall layer.

## Example payloads

The examples below are intentionally sanitized.

### 1. Proposed

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP01H0A1C8B3T6N1Q",
  "event_name": "guarded_write.request_proposed",
  "occurred_at": "2026-05-29T22:41:00Z",
  "request_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "correlation_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "status_from": null,
  "status_to": "proposed",
  "actor": {
    "type": "dashboard_user",
    "id": "dominic",
    "display": "Dominic",
    "source": "mission-control-ui"
  },
  "action": {
    "action_id": "restart-hermes-dashboard",
    "template_id": "restart-hermes-dashboard@v1",
    "kind": "service_restart",
    "risk_level": "high",
    "command_preview_redacted": "systemctl --user restart hermes-dashboard.service",
    "command_fingerprint": "hmac-sha256:9aa95f8f5d58b7d2b3d8f8db6f8c4c1f9d9e6f8a3e13b8c6d2d8724f1bc70355",
    "side_effects_summary": "Dashboard API and UI may be briefly unavailable.",
    "rollback_summary": "Restart the previous known-good service definition and re-check /api/status.",
    "approval_ttl_seconds": 300
  },
  "target": {
    "host": "jellyberry",
    "environment": "homelab",
    "service_or_scope": "hermes-dashboard",
    "path_labels": [],
    "remote_account": "jellybot"
  },
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": [],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "not_attempted_in_event",
    "hindsight": "not_attempted_in_event"
  }
}
```

### 2. Approved

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP02V5Q0Q9Y4MKP0S",
  "event_name": "guarded_write.approval_granted",
  "occurred_at": "2026-05-29T22:42:12Z",
  "request_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "correlation_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "status_from": "proposed",
  "status_to": "approved",
  "actor": {
    "type": "dashboard_user",
    "id": "dominic",
    "display": "Dominic",
    "source": "mission-control-ui"
  },
  "action": {
    "action_id": "restart-hermes-dashboard",
    "template_id": "restart-hermes-dashboard@v1",
    "kind": "service_restart",
    "risk_level": "high",
    "command_preview_redacted": "systemctl --user restart hermes-dashboard.service",
    "command_fingerprint": "hmac-sha256:9aa95f8f5d58b7d2b3d8f8db6f8c4c1f9d9e6f8a3e13b8c6d2d8724f1bc70355",
    "side_effects_summary": "Dashboard API and UI may be briefly unavailable.",
    "rollback_summary": "Restart the previous known-good service definition and re-check /api/status.",
    "approval_ttl_seconds": 300
  },
  "target": {
    "host": "jellyberry",
    "environment": "homelab",
    "service_or_scope": "hermes-dashboard",
    "path_labels": [],
    "remote_account": "jellybot"
  },
  "approval": {
    "approval_id": "01J0AUDITAPR5XKM2Q3D3H4WY",
    "decision": "granted",
    "decided_at": "2026-05-29T22:42:12Z",
    "expires_at": "2026-05-29T22:47:12Z",
    "approver_asserted_identity": "dominic",
    "proposal_fingerprint": "hmac-sha256:0f5672fc8a06a5b7d166f7c10dbf7d83d75f1c5d3b00ef8db8dd0d09bf1d5fc7",
    "confirmation_phrase_used": true
  },
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": [],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "not_attempted_in_event",
    "hindsight": "deferred_from_event"
  }
}
```

### 3. Denied

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP03CYW57MCMQ8R5F",
  "event_name": "guarded_write.approval_denied",
  "occurred_at": "2026-05-29T22:43:10Z",
  "request_id": "01J0AUDITREQDENIED7Y8V4D9",
  "correlation_id": "01J0AUDITREQDENIED7Y8V4D9",
  "status_from": "proposed",
  "status_to": "denied",
  "actor": {
    "type": "dashboard_user",
    "id": "dominic",
    "display": "Dominic",
    "source": "mission-control-ui"
  },
  "action": {
    "action_id": "restore-drill-manyfold",
    "template_id": "restore-drill-manyfold@v1",
    "kind": "restore_drill",
    "risk_level": "high",
    "command_preview_redacted": "bash /tmp/mc-restore-drill-[REDACTED].sh",
    "command_fingerprint": "hmac-sha256:c94aef83ce7dfca7f219d62d56fb2aa887adf0f7db3d4f6720eb14df4d7b6c7a",
    "side_effects_summary": "Creates restore-drill files in a staging destination.",
    "rollback_summary": "Delete the staging destination after verification.",
    "approval_ttl_seconds": 600
  },
  "target": {
    "host": "jellyhome",
    "environment": "homelab",
    "service_or_scope": "manyfold-restore-drill",
    "path_labels": ["restore_staging_path"],
    "remote_account": "dockerops"
  },
  "approval": {
    "approval_id": "01J0AUDITAPRDENIED5XKM2Q3",
    "decision": "denied",
    "decided_at": "2026-05-29T22:43:10Z",
    "expires_at": "2026-05-29T22:53:10Z",
    "approver_asserted_identity": "dominic",
    "proposal_fingerprint": "hmac-sha256:62a2bc21ec184a1d85f737ca15826ecef8a1b0d2324d0d0faa31f587da0d08ee",
    "denial_reason_code": "risk_rejected"
  },
  "reason": "Operator declined the restore drill after reviewing risk and side effects.",
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": ["action.command_preview_redacted", "target.path_labels"],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "secret_path", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "deferred_from_event",
    "hindsight": "deferred_from_event"
  }
}
```

### 4. Expired

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP04T8RBP6X2B7QKB",
  "event_name": "guarded_write.approval_expired",
  "occurred_at": "2026-05-29T22:48:13Z",
  "request_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "correlation_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "status_from": "approved",
  "status_to": "expired",
  "actor": {
    "type": "system",
    "id": "approval-expirer",
    "display": "approval-expirer",
    "source": "internal-worker"
  },
  "action": {
    "action_id": "restart-hermes-dashboard",
    "template_id": "restart-hermes-dashboard@v1",
    "kind": "service_restart",
    "risk_level": "high",
    "command_preview_redacted": "systemctl --user restart hermes-dashboard.service",
    "command_fingerprint": "hmac-sha256:9aa95f8f5d58b7d2b3d8f8db6f8c4c1f9d9e6f8a3e13b8c6d2d8724f1bc70355",
    "side_effects_summary": "Dashboard API and UI may be briefly unavailable.",
    "rollback_summary": "Restart the previous known-good service definition and re-check /api/status.",
    "approval_ttl_seconds": 300
  },
  "target": {
    "host": "jellyberry",
    "environment": "homelab",
    "service_or_scope": "hermes-dashboard",
    "path_labels": [],
    "remote_account": "jellybot"
  },
  "approval": {
    "approval_id": "01J0AUDITAPR5XKM2Q3D3H4WY",
    "decision": "expired",
    "decided_at": "2026-05-29T22:48:13Z",
    "expires_at": "2026-05-29T22:47:12Z",
    "approver_asserted_identity": "dominic",
    "proposal_fingerprint": "hmac-sha256:0f5672fc8a06a5b7d166f7c10dbf7d83d75f1c5d3b00ef8db8dd0d09bf1d5fc7"
  },
  "reason": "Approval window expired before execution started.",
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": [],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "deferred_from_event",
    "hindsight": "deferred_from_event"
  }
}
```

### 5. `/tmp` script generated

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP05R5QC00GQ1YV4Z",
  "event_name": "guarded_write.tmp_script_generated",
  "occurred_at": "2026-05-29T22:42:20Z",
  "request_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "correlation_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "status_from": "approved",
  "status_to": "script_generated",
  "actor": {
    "type": "system",
    "id": "guarded-write-executor",
    "display": "guarded-write-executor",
    "source": "internal-worker"
  },
  "action": {
    "action_id": "restart-hermes-dashboard",
    "template_id": "restart-hermes-dashboard@v1",
    "kind": "service_restart",
    "risk_level": "high",
    "command_preview_redacted": "bash /tmp/mc-guarded-write-01J0AUDITREQ7Y8V4D9P2X3M5.sh",
    "command_fingerprint": "hmac-sha256:9aa95f8f5d58b7d2b3d8f8db6f8c4c1f9d9e6f8a3e13b8c6d2d8724f1bc70355",
    "side_effects_summary": "Dashboard API and UI may be briefly unavailable.",
    "rollback_summary": "Restart the previous known-good service definition and re-check /api/status.",
    "approval_ttl_seconds": 300
  },
  "target": {
    "host": "jellyberry",
    "environment": "homelab",
    "service_or_scope": "hermes-dashboard",
    "path_labels": ["/tmp"],
    "remote_account": "jellybot"
  },
  "execution": {
    "execution_id": "01J0AUDITEXE61EZSHQQJYPYQ",
    "executor_type": "tmp_script",
    "executor_host": "jellyberry",
    "host_verified": true,
    "generated_at": "2026-05-29T22:42:20Z",
    "tmp_script_path": "/tmp/mc-guarded-write-01J0AUDITREQ7Y8V4D9P2X3M5.sh",
    "tmp_script_sha256": "sha256:4b0dd76de6679f41d5f9887cbc8d5da0daa6dc9116069c775d8ab6f955b9d892",
    "tmp_script_bytes": 812
  },
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": ["execution.tmp_script_body"],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "deferred_from_event",
    "hindsight": "skipped"
  }
}
```

### 6. Completed

```json
{
  "event_version": 1,
  "event_id": "01J0AUDITP06W4W09Q6R39A4H",
  "event_name": "guarded_write.execution_completed",
  "occurred_at": "2026-05-29T22:42:37Z",
  "request_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "correlation_id": "01J0AUDITREQ7Y8V4D9P2X3M5",
  "status_from": "running",
  "status_to": "completed",
  "actor": {
    "type": "system",
    "id": "guarded-write-executor",
    "display": "guarded-write-executor",
    "source": "internal-worker"
  },
  "action": {
    "action_id": "restart-hermes-dashboard",
    "template_id": "restart-hermes-dashboard@v1",
    "kind": "service_restart",
    "risk_level": "high",
    "command_preview_redacted": "bash /tmp/mc-guarded-write-01J0AUDITREQ7Y8V4D9P2X3M5.sh",
    "command_fingerprint": "hmac-sha256:9aa95f8f5d58b7d2b3d8f8db6f8c4c1f9d9e6f8a3e13b8c6d2d8724f1bc70355",
    "side_effects_summary": "Dashboard API and UI may be briefly unavailable.",
    "rollback_summary": "Restart the previous known-good service definition and re-check /api/status.",
    "approval_ttl_seconds": 300
  },
  "target": {
    "host": "jellyberry",
    "environment": "homelab",
    "service_or_scope": "hermes-dashboard",
    "path_labels": ["/tmp"],
    "remote_account": "jellybot"
  },
  "execution": {
    "execution_id": "01J0AUDITEXE61EZSHQQJYPYQ",
    "executor_type": "tmp_script",
    "executor_host": "jellyberry",
    "host_verified": true,
    "started_at": "2026-05-29T22:42:24Z",
    "duration_ms": 13044,
    "exit_code": 0,
    "stdout_summary": "systemctl restart returned success; dashboard status endpoint recovered within 4 seconds.",
    "stderr_summary": "",
    "health_check_summary": "GET /api/status -> 200 OK"
  },
  "result": {
    "outcome": "succeeded",
    "mutation_started": true,
    "postcheck_ok": true,
    "summary": "Restart completed and post-check passed."
  },
  "redaction": {
    "ruleset_version": "2026-05-29.1",
    "applied": true,
    "fields_redacted": [],
    "secret_classes_checked": ["token", "password", "api_key", "env_value", "raw_script_body"],
    "redaction_ok": true
  },
  "sinks": {
    "canonical_ledger": "written_this_event",
    "session_log": "written_this_event",
    "repo_record": "written_this_event",
    "hindsight": "written_this_event"
  }
}
```

## Implementation checklist

- Generate `request_id` before showing the approval UI.
- Compute proposal fingerprint before approval and re-check it immediately before execution.
- Run redaction before writing to any sink.
- Refuse mutation if canonical proposal, approval, or execution-start logging fails.
- Mirror terminal outcomes into repo record and Hindsight after canonical logging succeeds.
- Keep repo record and Hindsight content narrow enough to avoid leaking secrets or noisy output.
- Test all required status transitions and sink-failure branches.

## Verification expectations for the future implementation

Minimum tests:

- Proposal event emitted once per request.
- Approval granted, denied, and expired events preserve the same `request_id` and distinct `approval_id` values.
- Material change to proposal contents forces a new `request_id`.
- `/tmp` script generation logs path, hash, and size without logging script body.
- Canonical ledger failure before mutation produces `refused` and zero side effects.
- Secondary sink failure after mutation produces `completed_with_warnings` when the underlying action succeeded.
- Hindsight stores milestone summaries only and never becomes the sole approval record.
- Redaction removes secrets from command preview, output summaries, repo record, session log, and Hindsight.

## Recommended next tasks

- Implement the canonical event struct and JSONL writer.
- Implement the redaction library and proposal fingerprinting.
- Add repo-record renderer for per-request markdown files.
- Add Hindsight milestone retention helper with fixed tags and safe summary templates.
- Add tests for fail-closed audit behavior and replay/expiry validation.
