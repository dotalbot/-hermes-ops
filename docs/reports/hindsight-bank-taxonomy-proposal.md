# Hindsight bank taxonomy proposal

Date: 2026-05-29
Status: proposal
Related inputs:
- `docs/reports/hindsight-memory-audit-hermes-main.md`
- task `t_5ac655c7`

## Executive recommendation

Do not split all four candidate banks immediately.

Recommended path:
1. Keep `hermes-main` as the shared default bank.
2. Pilot a separate `home-network` bank first.
3. Add `portfolio` only if recall remains noisy after the `home-network` pilot.
4. Defer `cert-study` until study-memory volume or workflow intensity clearly justifies a separate bank.
5. Reassess after 2-4 weeks using actual recall quality, routing mistakes, and duplicate pressure.

This gets most of the likely recall-precision gain without paying the full fragmentation cost up front.

## Decision frame: recall precision vs fragmentation

### Why separate banks can help

- Domain-specific recall becomes cleaner when the current task obviously belongs to one area.
- Operational homelab facts stop crowding out Hermes-operating guidance and user preferences.
- Domain audits, cleanup, export, and retention-policy tuning become easier.
- Different banks can eventually have different missions, such as stable assistant memory versus host/service operational memory.

### Why separate banks can hurt

- Every retained memory needs a routing choice, and wrong-bank placement is worse than mild shared-bank noise.
- Cross-domain tasks become harder if relevant facts are split across multiple banks.
- Users and agents may duplicate memories across banks "just in case," increasing total clutter.
- Small banks can become too sparse, making recall less useful than a somewhat noisy shared bank.
- Migration costs are real: bank creation, routing rules, habit changes, and possible backfill/relabel work.

### Practical split rule

A new bank is justified only when all three are true:
1. The domain boundary is stable.
2. Shared-bank noise from that domain is materially hurting recall.
3. Future queries are often domain-scoped enough to benefit from isolated recall.

By that rule:
- `home-network` is the strongest split candidate now.
- `portfolio` is a plausible second candidate.
- `cert-study` is the weakest candidate today.
- `hermes-main` should remain as the cross-cutting base layer.

## Candidate bank definitions

### 1) `hermes-main`

Intended scope
- Cross-cutting assistant memory that should follow the user everywhere.
- Stable user preferences, communication style, workflow conventions, and durable Hermes-operating facts.
- Shared facts that matter across Hermes improvement, homelab operations, and portfolio work.
- Meta-memory about how Hermes should behave.

Examples that belong here
- User prefers concise operational updates.
- Feature branches are the default, except `/home/jellybot/home-network` goes directly to `main`.
- Hermes dashboard runs on jellyberry on port 9119.
- Portfolio/project digests should go to Discord twice daily.
- Hermes uses two memory layers: prompt/built-in memory plus Hindsight.

Examples that should not belong here
- A detailed restore procedure for a specific host or service.
- Narrow project-specific planning facts that only matter inside portfolio work.
- Flashcard-like certification facts or exam notes.
- Repetitive telemetry, temporary incident data, PIDs, `/tmp` paths, or one-off task state.

Migration risks
- If `hermes-main` stays too broad, it remains noisy and weakens the value of splitting.
- If too much is removed, cross-domain work loses useful default context.
- It may become a dumping ground for uncertain memories if routing rules are weak.

Recommendation
- Keep `hermes-main` as the default shared bank.

### 2) `home-network`

Intended scope
- Homelab, infrastructure, deployment, host operations, monitoring, backup/restore, network topology, runtime services, and operational runbooks.
- Host- or service-specific truth that is too detailed for general assistant memory.

Examples that belong here
- UFW remains inactive until the Tailscale-SSH firewall plan is complete.
- `3dprint_loader` runtime is on jellyhome and its MakerWorld state JSON stays outside Git.
- Borg/Borgmatic rollout details, restore checks, or backup-policy conventions for specific hosts.
- Compose/runtime facts for Grafana, Loki, Alloy, Prometheus, Homepage, Manyfold, and similar services.
- Operational facts about `/opt/docker`, service rebuild/recreate requirements, or host-specific runbooks.

Examples that should not belong here
- Global user style preferences.
- General Hermes workflow conventions that apply outside homelab work.
- Portfolio tracking decisions or product-roadmap judgments.
- Study notes for Microsoft certification prep.

Migration risks
- Operational tasks often overlap with Hermes tooling, so some facts will be ambiguous.
- Host/service facts can be volatile; this bank could still become noisy if retention quality is not improved.
- Agents may over-retain runtime checks unless transient-state filtering improves.

Recommendation
- Pilot now. This is the cleanest and highest-value split.

### 3) `cert-study`

Intended scope
- Certification objectives, study plans, lab patterns, spaced-repetition notes, exam-domain summaries, and durable learning artifacts.
- Facts useful for repeated study sessions over weeks or months.

Examples that belong here
- SC-401 and MS-102 topic summaries.
- Durable study-plan structure, lab sequences, and concept maps.
- Notes about which exam domains are weak or need repetition.
- Reusable study prompts and review patterns.

Examples that should not belong here
- General assistant/user preferences.
- Homelab operational procedures.
- Portfolio project-tracking notes.
- One-off browsing notes that will never be reused.

Migration risks
- If memory volume is still low, the bank will be too sparse to improve recall.
- Study work often produces ephemeral notes that may not deserve long-term retention.
- Over-separating learning content too early can create maintenance without practical benefit.

Recommendation
- Defer for now. Create only when study traffic becomes sustained and recall-worthy.

### 4) `portfolio`

Intended scope
- Portfolio intelligence, roadmap tracking, spec/project relationships, digest preferences tied to portfolio operations, and durable knowledge about portfolio tooling.
- Long-lived facts about portfolio structures, dashboards, project categorization, and review workflows.

Examples that belong here
- Portfolio Mission Control V2 source path and runtime route details.
- Portfolio repo layout and config patterns, such as `repos.yaml` local-path usage.
- Durable project-roadmap conventions or digest-generation rules specific to portfolio work.
- Long-lived facts about portfolio dashboards, collectors, and project summarization.

Examples that should not belong here
- Low-level homelab deployment details unless they are directly part of portfolio infrastructure.
- Global Hermes behavior preferences.
- Certification-study notes.
- Temporary daily portfolio status snapshots that will be stale within days.

Migration risks
- Portfolio work overlaps with Hermes-operating work, so boundaries need clear examples.
- Some portfolio facts are partly operational and partly product-facing.
- If the bank becomes a dump for transient status summaries, fragmentation will not help.

Recommendation
- Consider as the second split, but only after observing the `home-network` pilot.

## Comparison table

| Bank | Split now? | Why | Main risk |
| --- | --- | --- | --- |
| `hermes-main` | Keep shared | Needed for cross-domain defaults and user/Hermes behavior | Stays noisy if scope is not tightened |
| `home-network` | Yes, pilot | Strong boundary and high operational-noise pressure | Volatile runtime facts may still flood it |
| `cert-study` | No, defer | Weak current volume signal; likely sparse | Fragmentation without enough recall benefit |
| `portfolio` | Maybe later | Plausible domain boundary and useful if project recall is noisy | Boundary overlap with general Hermes/product work |

## Low-risk adoption path

### Phase 0: tighten policy before splitting

Before adding more banks, improve routing quality:
- Keep obviously durable cross-domain facts in `hermes-main`.
- Avoid retaining perishable runtime state such as PIDs, ready/running counts, `/tmp` paths, and one-off task IDs.
- Prefer one consolidated durable fact over many repeated near-duplicates.

Without this step, new banks will inherit the same noise pattern.

### Phase 1: pilot `home-network`

- Create `home-network` and route only clearly homelab-scoped memories there.
- Keep ambiguous or cross-domain facts in `hermes-main` during the pilot.
- Do not migrate the full historical bank immediately.
- Start with new retention only, plus optional manual migration of a few high-value durable facts.

Success signals
- Homelab queries return more precise results.
- Fewer unrelated operational facts appear in general Hermes recall.
- Routing mistakes remain manageable.

Failure signals
- Frequent uncertainty about which bank should receive a memory.
- Repeated duplication across `home-network` and `hermes-main`.
- Little measurable improvement in recall quality.

### Phase 2: evaluate `portfolio`

Only add `portfolio` if the `home-network` pilot helps and portfolio/project recall is still materially noisy.

Start narrow:
- Portfolio repo layout and dashboard conventions.
- Long-lived roadmap/spec relationships.
- Digest-generation rules specific to portfolio workflows.

Avoid moving all project chatter into the bank. Keep transient status snapshots out.

### Phase 3: defer `cert-study` until justified

Add `cert-study` only when at least one of these becomes true:
- recurring study sessions create substantial durable notes,
- recall requests are often exam-domain-specific,
- shared-bank noise from study material becomes noticeable.

Until then, `cert-study` should remain a future option, not an immediate split.

## Migration guidance

Recommended migration posture
- Do not bulk-move everything out of `hermes-main`.
- Keep historical `hermes-main` intact during the pilot.
- Route new memories conservatively.
- Manually migrate only a small set of obviously durable, high-value facts into `home-network` if needed.
- Reassess with an audit after the pilot window.

Why this is safer
- It avoids irreversible taxonomy mistakes.
- It reduces duplicate backfill work.
- It lets observed recall outcomes drive the next split.
- It limits the blast radius if bank boundaries need adjustment.

## Final recommendation

Adopt a gradual two-step approach, not a four-bank hard split.

Recommended call today:
- Keep `hermes-main` as the shared/default bank.
- Pilot `home-network` now.
- Consider `portfolio` later if recall still needs more separation.
- Defer `cert-study` until memory volume and workflow intensity justify it.

That is the best balance between better recall precision and avoiding premature taxonomy fragmentation.
