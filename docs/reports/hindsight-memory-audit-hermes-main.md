# Hindsight memory quality audit: `hermes-main`

Date: 2026-05-29
Method: read-only audit against the live Hindsight API at `http://jellyhome:18888` (`/version` reported API `0.6.2`). No memories were edited or deleted.

## Bank audited

- Bank: `hermes-main`
- Total memory nodes: 2,466
- Fact types: 1,770 `experience`, 656 `observation`, 40 `world`
- Documents: 51
- Completed operations: 426
- Pending / failed operations at audit time: 0 / 0

## Executive summary

`hermes-main` is usable but materially noisy. The strongest quality issue is duplicate inflation: many facts appear multiple times as raw `experience` memories, sometimes alongside an `observation`, and often with only timestamp or task-ID differences. The second issue is retention of highly perishable operational state such as PIDs, ready/running task counts, `/tmp` paths, tmux pane routing, and one-off task IDs. These patterns make recall more likely to surface recent operational chatter instead of durable knowledge.

## Confirmed issues

### 1) Duplicate and near-duplicate inflation

Confirmed from the live bank contents:

- 293 exact-text duplicate clusters covering 740 memories
- 536 normalized duplicate clusters covering 1,415 memories
- Normalization removed only obvious formatting noise such as appended `| When: ... | Involving: ...`, task IDs, and `/tmp/...` path variance before clustering

Representative duplicate clusters:

- 16 copies: `Host is 'jellyberry' with Primary LAN IP '192.168.1.159' and Tailscale IP '100.68.81.120'.`
- 10 copies: `Existing running tasks count toward the limit; if 1 task is already running, only 1 more will start.`
- 9 copies: `Kanban board/dashboard is running with the Hermes gateway and dashboard operational.`
- 9 copies: `User requested to set up Tailscale SSH as a backdoor.`
- 8 copies: `User worked on kanban task <task>.`
- 8 copies: `Hermes core dashboard is running with PID 2026289 for 01:59:22 on port 9119.`

Observed shape of the duplication:

- the same statement is often stored as both `experience` and `observation`
- many repeated `experience` facts differ only by appended timestamp / actor metadata
- some clusters are concentrated inside a single parent session, indicating same-session amplification rather than independently useful corroboration

### 2) High volume of stale or perishable operational memories

The bank retains many details that are operationally true only for minutes or a single task run.

Pattern counts found directly in memory text:

- 844 memories containing embedded ISO timestamps
- 108 memories containing Kanban task IDs
- 16 memories containing `/tmp/...` paths
- 22 memories mentioning PIDs
- 40 memories mentioning ports
- 35 memories mentioning tmux
- 28 memories mentioning commits
- 27 memories mentioning worker processes

Examples of questionable long-term retention:

- `Hermes core dashboard is running with PID 2026289 for 01:59:22 on port 9119.`
- `Nothing is currently running on 'continuous-hermes-improvement'; board state shows 0 running, 0 ready, 24 blocked, 50 todo, and 21 done tasks.`
- `Log-signal probe rollout scripts generated for all 3 hosts in /tmp/node-exporter-rollout-{jellybase,jellyhome,jellyberry}/.`
- `The running task t_06bc53a4 has a status of running, assigned to default, with a PID of 2036629, and started at 21:36.`
- `dir and worktree workspaces are preserved, indicating that the issue is not isolated to t_ddd94f48.`

These facts are not wrong, but they age out quickly and can pollute future recall.

### 3) Same-session amplification

A small number of parent sessions generated disproportionately large memory volume.

Largest parent-session clusters seen in tags:

- `parent:20260529_193416_5122c6` → 315 memories
- `parent:20260526_232226_504703` → 195 memories
- `parent:20260528_070431_c15a8a` → 176 memories

This points to repeated extraction of a single session into many closely related `experience` facts, with limited consolidation before those facts become recall candidates.

## Suspected issues that need human review

### A) Shared-bank scope may be broader than expected

Memory tags were dominated by the default profile:

- `profile:default` → 2,439 memories
- `profile:hindsightpilot` → 6 memories

If `hermes-main` is intentionally a shared operational bank, this is fine. If the bank was expected to primarily represent `hindsightpilot`, the current contents are overwhelmingly from another profile and may need bank-scope clarification.

### B) Some duplicated infrastructure facts may be intentionally sticky

Examples like host identity, LAN IP, Tailscale IP, or Kanban safety settings are durable enough to be useful. The issue is not necessarily that they exist, but that they appear many times as raw memories rather than one consolidated durable fact with supporting evidence.

### C) Observation quality is mixed

The bank has 656 `observation` memories, which should be the cleaner consolidated layer, but duplicate clusters still include observations and observation/experience pairs. I did not mutate or re-run consolidation, so I cannot confirm whether this is a configuration issue, an extraction-policy issue, or simply backlog awaiting later consolidation behavior.

## Likely causes

Most likely contributors, based on the live configuration and bank contents:

1. Auto-retention is enabled on every turn (`retain_every_n_turns: 1`), so operational chatter is continuously admitted.
2. The current workflow appears to store both raw `experience` memories and derived `observation` memories for many of the same facts.
3. Operational sessions around Kanban status, dashboards, deployment checks, and rollout diagnostics generate lots of short-lived state but still enter the long-term bank.
4. Repeated follow-up checks appear to create fresh memories instead of strengthening or replacing a single durable fact.

## Safe conclusions

Confirmed:

- `hermes-main` contains substantial duplicate inflation.
- `hermes-main` contains substantial stale/perishable operational content.
- duplicate pressure is large enough to plausibly reduce recall usefulness.

Not confirmed from this audit alone:

- whether deduplication should happen at retention time, consolidation time, or bank-splitting time
- whether all repeated host / Kanban / dashboard facts are unwanted versus intentionally high-salience
- whether the current shared-bank profile mix is intentional policy or accidental drift

## Suggested follow-up questions for a human reviewer

1. Should transient runtime state (PIDs, `/tmp` paths, ready/running counts, one-off task IDs) be excluded from long-term retention entirely?
2. Should operational chatter live in a separate bank from durable Hermes conventions and user preferences?
3. Should repeated facts be collapsed into a single world/observation fact rather than many `experience` facts?
4. Is `hermes-main` intended to be a shared bank across profiles, or should `hindsightpilot` have a cleaner profile-scoped bank?
