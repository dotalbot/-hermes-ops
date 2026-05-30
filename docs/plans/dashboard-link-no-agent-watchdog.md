# Plan: dashboard link no-agent watchdog

## Goal

Implement the top no-agent recurring-check recommendation: a deterministic stale dashboard link checker that can run as a Hermes `no_agent=true` cron job.

## Scope

- Add a Python watchdog script that performs read-only HTTP GET/HEAD checks against fixed configured URLs.
- Keep success quiet by default so no-news cron ticks produce no delivered message.
- Add explicit digest mode for manual/operator summaries.
- Add duplicate-alert suppression with a runtime state file.
- Add a repo-owned config and operator runbook.
- Install a runtime copy under `/home/jellybot/.hermes/scripts/` and schedule or document the no-agent cron job.

## Non-goals

- No browser automation.
- No mutation, restart, deployment, repair, or dashboard config changes.
- No arbitrary URL input from chat, dashboard UI, or LLM output.
- No LLM/chat-agent execution during scheduled checks.

## Acceptance checklist

- [x] Source script added under `scripts/dashboard_link_check.py`.
- [x] Fixed link config added under `config/dashboard-links.json`.
- [x] Runtime copy installed under `/home/jellybot/.hermes/scripts/dashboard_link_check.py`.
- [x] Manual digest run works.
- [x] Quiet passing mode produces empty stdout.
- [x] Forced bad config emits a deterministic fixed alert.
- [x] No-agent cron job scheduled or ready-to-install entry documented.
- [x] Runbook documents config, schedule, logging, state, and manual checks.
