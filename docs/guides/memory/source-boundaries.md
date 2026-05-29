# Memory source boundaries for Hermes operations

Purpose: keep each kind of knowledge in the place where it is easiest to verify, least likely to become stale, and safest to share with future workers.

Use this as the default rule for Dominic's Hermes setup. If a fact could affect a future automated action, prefer the most durable and auditable source that can hold it without exposing secrets.

## Decision table

| Source | Store here | Do not store here | Retrieval path | Retention rule |
|---|---|---|---|---|
| Built-in prompt memory / user profile | Compact, durable preferences and stable environment conventions that should steer every future assistant run. Examples: communication style, repo workflow preferences, standing exceptions, stable host roles. | Run status, PR/issue numbers, commit SHAs, temporary project state, secrets, raw logs, detailed procedures, facts likely to expire within a week. | Automatically injected into sessions. Update with explicit memory operations only when the fact is long-lived. | Keep terse. Replace or remove stale facts; do not append duplicate history. |
| Hindsight long-term memory | Searchable cross-session knowledge that helps recall decisions, entities, and recurring context without bloating the prompt. Good for durable project relationships, operator conventions, and lessons that may matter later but do not need to be always injected. | Secrets, credentials, large documents, raw transcripts, temporary task progress, status snapshots, or anything that needs source-control review. | `hindsight_recall` for targeted recall; `hindsight_reflect` for synthesis across stored memories. | Treat as assistant memory, not authoritative docs. Promote stable operational guidance into repository docs. |
| Current session history | Immediate working context, tool outputs, in-progress reasoning, and temporary details needed to finish the current turn or task. | Anything expected to survive context compaction or be used by another worker later. | Already in context while the session is active. | If it matters after this session, move it to docs, Kanban comments, or the right memory store before finishing. |
| `session_search` | Past conversation retrieval: what was discussed, what decisions were made, and where a previous session left off. Best for answering "what did we do about X?" | Canonical operating procedures, current source of truth, or facts that should be acted on without re-verification. | Search previous sessions by keywords, then verify against repo docs/current state before acting. | Use as historical evidence. Do not treat old transcript snippets as current state. |
| Repository documentation | Canonical runbooks, decision records, specs, plans, checklists, architecture notes, audit reports, and project state that must be reviewable, versioned, and shared between workers. | Secrets, local-only credentials, token values, volatile runtime telemetry, unreviewed scratch notes. | Read directly from the project repo, usually under `docs/`. Changes must be committed and pushed when possible. | Source of truth for durable operating guidance and project documentation. Keep current through normal git review. |
| Honcho | Current source of truth or fallback for task/project knowledge that Hindsight has not yet proven it can reliably recover and surface during normal workflow. | New long-term policy if it has already been migrated, verified, and actively maintained in docs plus Hindsight. | Keep Honcho active and consult it for known-good project/operator context until confidence gates below pass. | Retire or demote only after successful parallel operation and documented rollback path. |

## Checklist: where should this fact go?

1. Is it a secret, token, password, cookie, recovery key, private API response, or credential-equivalent browser/profile state?
   - Store it outside memory and docs in the approved secret store or host-local path.
   - Docs may record the existence and restore requirement, never the value.
2. Does every future assistant run need this to behave correctly?
   - If yes and it is stable, keep a short built-in prompt memory entry.
   - If not, do not put it in always-injected memory.
3. Is it durable operational guidance, a runbook, architecture, a decision, or project state another worker must audit?
   - Put it in repository documentation under `docs/` and commit it.
4. Is it useful historical context but not canonical?
   - Use Hindsight or `session_search`, then verify before acting.
5. Is it only relevant to the current task attempt?
   - Keep it in current session history or a Kanban comment/handoff.
6. Could it become stale within days, such as a branch name, run status, current port check, package version, backup result, or service health snapshot?
   - Do not put it in built-in prompt memory.
   - Put the durable rule or runbook in docs; put one-off results in Kanban comments/reports if needed.

## Source-specific guidance

### Built-in prompt memory

Use for small facts that are both stable and high-leverage:

- User preferences: concise style, communication channel preferences, approval habits.
- Standing workflow conventions: feature branches by default, repo-specific direct-main exceptions, Kanban defaults.
- Stable environment landmarks: durable repo paths, persistent service host roles, long-lived tool quirks.

Avoid storing:

- "Task X completed", PR numbers, issue numbers, commit SHAs, temporary branches, or last-run results.
- Long runbooks or multi-step procedures. Save those as skills or repository docs.
- Credential material or secret locations unless the location itself is a durable restore prerequisite and does not reveal the secret.

### Hindsight long-term memory

Use Hindsight when the information is useful later but should not be forced into every prompt:

- Cross-session relationships and lessons learned.
- Durable facts that are helpful for semantic recall.
- Summaries of stable conventions after they have been cleaned of transient status and secrets.

Hindsight is not a replacement for repository docs. If a fact should be reviewed, diffed, linked, or used by several workers as a canonical instruction, promote it to docs. Hindsight can point back to docs or help find the relevant docs, but docs remain the source of truth for operating procedures.

### Current session history

Use the current context for active work only:

- Tool output needed to make the next decision.
- Temporary command results.
- Draft reasoning before it becomes a deliverable.

Before finishing a task, ask: "Would another worker need this after my context disappears?" If yes, write it to a durable artifact, Kanban comment, or appropriate memory store.

### `session_search`

Use `session_search` to recover prior conversations before asking the user to repeat themselves. It is especially useful for:

- Finding a past decision or rationale.
- Reconstructing where work stopped.
- Checking whether an issue was already discussed.

Treat results as historical transcripts. Verify current state with repository files, live commands, or Hindsight before making changes. A session transcript can explain why a choice was made; it should not silently override newer docs.

### Repository documentation

Use docs for canonical, durable, auditable knowledge:

- Runbooks and operational procedures.
- Architecture and integration maps.
- Specs, plans, checklists, and roadmaps.
- Decision records and policy boundaries.
- Audit reports and durable Kanban deliverables.

Docs should explain secret handling without containing secrets. Example: "The API key lives in `/opt/docker/.secrets/service.env` and must be restored before deploy" is acceptable if the file path is not itself sensitive; the key value is never acceptable.

Operational facts that may become stale belong in docs only when framed as policy, design, or verification procedure. For example:

- Good: "Run `git diff --check` before committing docs-only Kanban artifacts."
- Good: "Prometheus rules should avoid unsupported template pipes."
- Bad: "Service X was healthy at 21:14 yesterday" unless it is part of an incident report or audit with a timestamp.

## Honcho and Hindsight transition rule

Keep Honcho active until Hindsight proves itself in normal workflow. That means Honcho remains the source of truth or fallback when any of these are true:

- Hindsight recall has not been exercised successfully for the relevant workflow in day-to-day use.
- Hindsight returns noisy, duplicate, missing, or stale results for the workflow.
- A worker cannot recover enough context from Hindsight plus repository docs to act safely without asking the user to repeat known information.
- The workflow involves high-risk operations, credentials, backups, homelab changes, or other actions where losing context would be costly.
- There is no documented fallback path for restoring the knowledge from docs or Honcho.

Hindsight can become primary for a workflow only after all of these gates pass:

1. The canonical rules and runbooks are in repository docs.
2. Hindsight can reliably recall the relevant docs, entities, and operator preferences during normal tasks.
3. Workers have completed several ordinary tasks using Hindsight without needing Honcho for missing context.
4. A documented fallback exists: if Hindsight recall is incomplete, consult Honcho and/or repository docs before acting.
5. The operator agrees Honcho can be demoted for that workflow.

Until then, run both in parallel: use repository docs for canonical instructions, Hindsight for recall, `session_search` for historical transcript recovery, and Honcho as the proven fallback. Belt, braces, and one spare bit of string.

## Practical examples

- "Dominic prefers concise Discord updates without tool details unless permission is needed" → built-in prompt memory; optionally Hindsight for recall.
- "The memory hygiene runbook says how to audit Hindsight duplicates" → repository docs.
- "A worker found 2,466 Hindsight nodes during a dated read-only audit" → audit report in docs; not prompt memory.
- "The current backup run passed at 03:00" → current session/Kanban/reporting only; do not store as durable memory unless it changes policy.
- "Backups must include restore verification" → prompt memory if it must steer future behavior; detailed commands belong in docs/runbook.
- "A GitHub token value or browser storage state" → secret store only; never docs, prompt memory, Hindsight, or session handoff.
