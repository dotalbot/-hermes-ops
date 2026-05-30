# ADR 0001: Hindsight vs Honcho as Hermes long-term memory provider

Status: Accepted
Date: 2026-05-30

## Context

Hermes Agent sessions are stateless — each conversation turn is a fresh API invocation with no built-in carryover between turns. To provide coherent long-term assistance, Hermes needs a persistent memory layer that can store facts across sessions and retrieve them during future conversations.

The project started with **Honcho** as the long-term memory provider. Honcho is an open-source agent memory framework that stores and retrieves structured facts about users, tasks, and entities. It was the default memory backend when Hermes was first deployed and accumulated a substantial body of cross-session knowledge.

However, over weeks of operation, several pain points emerged:

- Honcho's retrieval quality was inconsistent — workers sometimes could not recover enough context to act safely without asking the user to repeat information.
- Honcho's API surface is narrow and its maintenance cadence is uncertain.
- The accumulated memory volume grew without effective deduplication, making recall increasingly noisy.

In parallel, **Hindsight** (v0.6.2) became available — a purpose-built memory service designed specifically for Hermes-like agent workflows. It offers a richer API (semantic search, entity graph traversal, reflection/synthesis via `hindsight_reflect`, structured fact extraction, and memory consolidation), runs as a self-hosted service, and is under active development.

The operational question: should Hermes keep Honcho as the sole long-term memory provider, adopt Hindsight in its place, or run both in parallel during a transition?

## Decision

Adopt **Hindsight as the primary long-term memory provider** for Hermes, while **keeping Honcho active as a fallback** until Hindsight proves reliable across all operational workflows.

Key operational choices:

- **Memory provider**: Hermes is configured with `memory_provider: hindsight` and `bank: hermes-main` as the default bank.
- **Parallel operation**: Honcho remains deployed and available. It is not decommissioned and continues to receive memory writes.
- **Transition gates**: Honcho is demoted only after all five gates from the source-boundary rules pass — canonical docs exist in the repo, Hindsight recall is reliable, workers complete ordinary tasks without needing Honcho, a documented fallback path exists, and the operator explicitly agrees.
- **Bank architecture**: `hermes-main` is the single shared default bank. A separate `home-network` bank was proposed but deferred for pilot evaluation. Further bank splitting (portfolio, cert-study) is deferred until recall quality data justifies it.
- **Retention policy**: Hindsight's auto-retention is active (`retain_every_n_turns: 1`), which has led to duplicate inflation and stale operational content in the bank. The decision is to tighten routing quality (avoid transient PIDs, `/tmp` paths, task IDs, board-state chatter) rather than disable auto-retention wholesale.

## Consequences

### Benefits

- **Richer retrieval**: Hindsight provides semantic search, entity graph traversal, and synthesis/reflection — capabilities Honcho lacks. This enables workers to find relevant context without knowing exact keywords.
- **Bank scoping**: Hindsight supports multiple named banks, allowing future domain separation (operational facts vs user preferences vs portfolio knowledge) without changing the underlying provider.
- **Active development**: Hindsight is developed alongside Hermes, so bug fixes and feature improvements (consolidation, deduplication, routing policy) are actively arriving.
- **Structured fact storage**: Hindsight distinguishes between `experience` (raw observations), `observation` (consolidated facts), and `world` (stable knowledge) types, enabling layered memory quality rather than flat key-value storage.
- **Self-hosted**: The service runs on the user's own infrastructure (jellyhome, LAN + Tailscale), keeping memory data under local control.

### Costs and risks

- **Duplicate inflation**: Auto-retention at every turn has created ~2,466 memory nodes with 293 exact-text duplicate clusters covering 740 memories (as of the May 29 audit). Without cleanup, recall quality degrades because operational chatter (PIDs, tmux routing, board counts, `/tmp` paths) crowds out durable knowledge.
- **Transition uncertainty**: Honcho is the proven fallback, but the transition gates mean Honcho must be maintained alongside Hindsight indefinitely until all five pass — operational overhead of running two memory systems in parallel.
- **Bank-boundary ambiguity**: When to store a memory in `hermes-main` vs a domain-specific bank is not always clear. Wrong-bank placement is worse than mild shared-bank noise, so defaulting to `hermes-main` risks keeping it noisy.
- **Consolidation immaturity**: Hindsight's built-in consolidation (promoting `experience` → `observation`) has not yet reliably reduced duplicate pressure. The May audit showed observations themselves are duplicated in many clusters.
- **Service dependency**: If jellyhome (where Hindsight runs) is unreachable, Hermes loses memory recall. Honcho provides a fallback, but the fallback is on the same host infrastructure.

## Alternatives considered

- **Honcho only (no Hindsight)**: Rejected because retrieval quality was already causing worker friction, and Honcho's narrower API could not grow to meet the need for semantic search, synthesis, and entity-aware recall without significant custom wrapper work.

- **Hindsight only, immediate Honcho decommission**: Rejected because Hindsight had not yet proven recall reliability in all workflows. The May 29 audit showed noise and duplication issues that would make a hard cutover risky. The user's explicit direction was to keep both running until Hindsight proves itself.

- **Third-party memory service (e.g., Mem0, Letta)**: Not seriously evaluated because Hindsight was purpose-built by the same team that develops Hermes, is self-hosted (avoiding API-cost exposure), and was already available when the decision was made. A future revisit is possible if Hindsight's maintenance or recall quality falls short.

- **No long-term memory at all**: Rejected because cross-session context is essential for the user's workflow — Kanban task history, homelab architecture knowledge, user preferences, and multi-step project work all depend on recalling past decisions without the user repeating themselves.

## Related links

- Hindsight runtime: `http://jellyhome:18888` (LAN `192.168.1.1`, Tailscale `100.90.175.59`, UI `:9999`)
- Source boundary rules: `docs/guides/memory/source-boundaries.md` — defines the Honcho/Hindsight transition gates and the memory store decision table
- Memory audit report: `docs/reports/hindsight-memory-audit-hermes-main.md` — May 29 audit of `hermes-main` bank quality
- Bank taxonomy proposal: `docs/reports/hindsight-bank-taxonomy-proposal.md` — analysis of bank-splitting options
- Reversible cleanup plan: `docs/guides/memory/reversible-cleanup-plan.md` — phased approach to deduplication
- Kanban task: `t_65b8c779` — this ADR creation task
- Decision selection task: `t_42d533db` — selected this topic as the first formal ADR
