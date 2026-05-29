# Recurring chat checks: no-agent conversion plan

Purpose: prioritize recurring chat-driven checks that should be converted from LLM-agent cron jobs into deterministic `no_agent=True` script jobs, with optional downstream human-facing formatting only when reasoning is truly needed.

## Recommendation

Implement the stale dashboard link checker first.

It is the best first conversion because it has the strongest no-agent fit: deterministic inputs, deterministic pass/fail outputs, low safety risk, simple verification, and high drift-reduction value. It can stay silent when everything passes and emit a fixed alert only when links break. That matches the ideal watchdog pattern for `no_agent=True` jobs.

## Scoring rubric

Scores use 1-5, where 5 is best for conversion.

- Value: how useful the check is to the operator.
- Determinism: how easy it is to express as fixed logic with structured output.
- Implementation effort: 5 means low effort, 1 means high effort.
- Safety/risk: 5 means low risk, 1 means high risk.
- Prompt-drift reduction: how much conversion reduces recurring prompt variability or chatty LLM behavior.

## Prioritized list

| Rank | Candidate | Value | Determinism | Effort | Safety | Drift reduction | Rationale | Prerequisites / risks |
|---:|---|---:|---:|---:|---:|---:|---|---|
| 1 | Stale dashboard link checker | 4 | 5 | 5 | 5 | 5 | Clear scripted inputs and outputs: read known dashboard URLs, perform HTTP checks, compare status/age/redirects, stay quiet on pass, alert only on failure. Very little need for reasoning. | Needs authoritative list of dashboard links and expected statuses. Avoid noisy alerts by supporting retries, per-link timeouts, and allowlisted non-200 expected responses. |
| 2 | Daily/weekly backup restore-confidence summary | 5 | 4 | 3 | 4 | 5 | High operational value and already aligned with the user's preference for backup restore verification. Most data can be scripted: last backup, last restore test, repo reachability, check age, and warning thresholds. | Needs stable local paths for backup status artifacts and restore-test evidence. Risk: a summary can imply false confidence unless it clearly distinguishes backup success from restore verification. |
| 3 | Prometheus/Alertmanager summary with human labels | 5 | 4 | 3 | 4 | 4 | Alertmanager APIs are structured, and label grouping can be deterministic. Good candidate for a script that emits fixed bullets for active alerts grouped by severity/service/owner. | Needs reachable Prometheus/Alertmanager endpoint and agreed label taxonomy. Risk: bad labels produce misleading grouping; avoid LLM-generated labels in the no-agent layer. |
| 4 | Operational digest for items needing approval | 4 | 3 | 3 | 3 | 4 | Valuable because it highlights blocked decisions, but it may aggregate heterogeneous sources: Kanban blocked tasks, approval queues, dashboard action proposals, and cron failures. Deterministic if limited to explicit queues. | Needs a defined source list and an allowlist of approval states. Risk: accidental escalation or omission if the script scrapes free text instead of structured fields. |
| 5 | Weekly homelab changes digest | 4 | 3 | 3 | 4 | 3 | Useful, but summarizing changes often benefits from reasoning. A no-agent version can still report deterministic facts: git commits, changed files, deployments, backup checks, and incident links. | Needs source-of-truth repositories/logs and a fixed template. Risk: too much raw diff noise without an LLM summarizer; may be better as script collection plus optional agent summarization. |
| 6 | Cert study streak and weak-topic reminder | 3 | 3 | 4 | 5 | 3 | Low risk and easy if study data is structured. However, weak-topic inference can become subjective unless based on quiz results or tagged notes. | Needs a durable study log or quiz result source. Risk: motivational reminders can get annoying if frequency and quiet conditions are not explicit. |
| 7 | Existing weather/tide briefing pattern | 3 | 2 | 3 | 5 | 2 | Keep as an example, not the first conversion target. The current value is partly in friendly presentation: jokes, quote, concise Discord style, and local context. Raw weather/tide retrieval can be scripted, but the human-facing brief may still benefit from formatting rules or a small LLM step. | Needs reliable weather and tide APIs. Risk: fully deterministic output may feel worse than the current briefing; use it as a reference for delivery shape, not as the first no-agent migration. |

## Implementation order

1. Stale dashboard link checker.
   - Create a script-only cron job with `no_agent=True`.
   - Input: a checked-in or profile-local list of dashboard URLs, expected status class, optional expected text, timeout, and retry count.
   - Output: empty stdout when all checks pass; concise alert text only for failures.
   - Verification: run the script manually against at least one known-good URL and one forced-bad URL.

2. Backup restore-confidence summary.
   - Script collection should separate backup recency, repo reachability, integrity checks, and restore-test evidence.
   - Output should say "restore confidence" only when a restore verification artifact is current.

3. Prometheus/Alertmanager summary.
   - Query Alertmanager directly and group active alerts by fixed labels.
   - Emit only active/unacknowledged or changed alert groups to avoid recurring noise.

4. Operational approval digest.
   - Limit the first version to structured queues, especially blocked Kanban tasks with `review-required:` or approval-specific status.

5. Weekly homelab changes digest.
   - Start with deterministic collection. Consider a chained LLM summarizer only if the raw digest is too noisy.

6. Cert study streak and weak-topic reminder.
   - Implement after the study data source is stable and quiet-day behavior is agreed.

7. Weather/tide briefing pattern.
   - Retain as a delivery-format benchmark. Convert only the data-fetching layer if needed; preserve the user-facing style constraints separately.

## First-candidate implementation notes

The stale dashboard link checker should be a no-agent watchdog, not an agent summary job:

- Schedule: every 30-60 minutes, or daily if the dashboard links are low urgency.
- Silent success: empty stdout when all links pass.
- Failure output shape:
  - `Dashboard link check failed:`
  - one bullet per failing URL with expected status, actual status/error, and retry count.
  - no stack traces unless a debug flag is enabled.
- Safety: read-only HTTP checks only; no login, no mutation, no browser automation.
- State: optional last-failure hash to avoid repeating identical alerts every run.

## Decision

Top candidate: stale dashboard link checker.

Reason: it is the most deterministic, lowest-risk, lowest-effort conversion with the cleanest `no_agent=True` success behavior. It should reduce prompt drift immediately because the job never needs to ask an LLM to decide whether a link is up.
