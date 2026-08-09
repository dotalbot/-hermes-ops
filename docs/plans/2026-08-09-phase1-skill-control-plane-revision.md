# Phase 1 skill control-plane revision plan

**Goal:** Revise the Jellyberry Kanban orchestration Phase 1 package to add risk-tiered cross-model review, database/data expertise, governed global/project skill management, visual status, and repeatable project initialization while preserving the Phase 2 gate.

**Architecture:** Keep Git-backed manifests as authority. Model skills as versioned core releases, optional capability packs, project-only overlays, and profile/model/tool bindings. Generate human views and project setup plans from those manifests; do not make the visual surface or active profile copies authoritative.

**Tech stack:** Markdown, JSON Schema, YAML examples, Hermes profiles/skills/bundles/Curator concepts, Git validation, and independent OpenRouter review.

## Scope

- Replace proposed OpenRouter Claude reviewer bindings with `deepseek/deepseek-v3.2`.
- Define cross-model review risk levels and activation rules.
- Add database/data expert modes, triggers, output contract, and project overlay composition.
- Add a central Skill Control Plane design.
- Add fail-closed `/project-init` and `project-doctor` design.
- Add versioning, update, staleness, canary, rollback, and visual status rules.
- Integrate the revision into V3, the bridge, README, and Phase 1 report.

## Non-goals

- No Phase 2 authorization.
- No profile, skill, bundle, board, bank, checkout, plugin, cron, or worker creation.
- No JellySSH or LogK implementation changes.
- No Hermes Agent source or live configuration changes.

## Verification

- Parse all new JSON and YAML examples.
- Validate relative links, Markdown fences, and `git diff --check`.
- Search active Phase 1 files for stale Claude bindings.
- Confirm no JellySSH runtime artifacts or proposed profiles/board exist.
- Run an independent review using a model family different from both the OpenAI implementation binding and DeepSeek reviewer binding.
- Commit and push only the documentation branch; stop at Phase 1 acceptance.

## Outcome

Completed on 2026-08-09. JSON Schema, YAML/JSON, Markdown fence/link, and Git whitespace checks passed. A direct repository-only OpenRouter `google/gemini-3.1-pro-preview` review returned `REVIEW PASS`. No Phase 2 runtime artifact was created; the revision remains at the operator-acceptance gate.
