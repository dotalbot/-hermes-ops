# Review: Guarded approval design for release readiness

**Review date:** 2026-05-30  
**Reviewer:** Hermes (operator-directed)  
**Parent task:** t_05849579 — Design guarded approval model for Mission Control write actions  
**Child task:** t_25036ea4 — Review guarded approval design for release readiness  

## Artifacts reviewed

| Artifact | Path | Status |
|----------|------|--------|
| ADR | `docs/decisions/guarded-mission-control-write-actions.md` | Proposed |
| Runbook | `docs/runbooks/approved-mission-control-actions.md` | Evaluation only — execution disabled |
| Audit logging spec | `docs/specs/mission-control-guarded-write-audit-logging.md` | Proposed spec |
| UX mock | `workspaces/t_47efc315/index.html` | Read-only prototype, operator-approved |

## Cross-reference consistency

| Check | Pass/Fail |
|-------|-----------|
| ADR references runbook and audit logging concepts | ✓ pass |
| Runbook explicitly references ADR by path | ✓ pass |
| Audit spec references ADR by path | ✓ pass |
| UX mock README maps acceptance criteria | ✓ pass |
| All artifacts agree on the same 5 candidate action classes | ✓ pass |
| All artifacts share the same core guardrails (exact command, target host, rollback, risk, secret redaction) | ✓ pass |
| No artifact contradicts another on scope, risk, or safety boundary | ✓ pass |

## Goal verification

**Original goal:** "Design but do not immediately enable dangerous Mission Control actions."

| Criterion | Assessment |
|-----------|------------|
| ADR/runbook exists | ✓ ADR and runbook both exist with full detail |
| Read-only prototype or mock demonstrates UX | ✓ Approved by operator |
| No destructive/write action enabled without user approval | ✓ All artifacts enforce read-only default; no implementation present |

## Candidate action coverage

Every candidate action in the ADR has corresponding detail in the runbook:

| Action | ADR | Runbook | Audit spec | UX mock |
|--------|-----|---------|------------|---------|
| Restart Hermes gateway/dashboard | ✓ | ✓ | ✓ (primary example) | ✓ (dashboard example) |
| Rerun collectors | ✓ | ✓ | ✓ | — (not shown in mock) |
| Trigger backup health checks | ✓ | ✓ | ✓ | — |
| Trigger restore drills | ✓ | ✓ | ✓ (denied example) | — |
| Recreate Docker services | ✓ | ✓ | ✓ | — |

All five actions have: approval requirements, exact command visibility, target host, rollback, risk level, logging, and secret-redaction coverage at the design level.

## Remaining risks

1. **Allowlist governance** — The ADR and runbook reference allowlists for action IDs, hosts, services, and paths but don't define who maintains them or how they're updated. Needs a follow-up decision.
2. **Identity/approver binding** — Open question in ADR: which identity provider binds approval events (local user, Discord user, dashboard session)? Needs resolution before implementation.
3. **UX mock scope** — The approved mock covers the dashboard restart action only. The other four candidate actions (collectors, backup checks, restore drills, Docker) have no UI mock. Acceptable at design stage; mock demonstrates the pattern.
4. **No implementation exists** — This is intentional and correct per the design-only scope. Implementation is still a future task. No code paths, no API routes, no executor logic exist.
5. **No stale/missed cross-reference** — The audit spec references the ADR but the ADR doesn't explicitly link back to the audit spec path. Minor documentation gap.

## Conclusion

**PASS — Release ready as a design package.**

All four artifacts are consistent, well-scoped, and enforce the read-only safety boundary. The guarded approval model is fully documented across ADR, runbook, audit spec, and UX mock. No dangerous action can execute under current design — no code, no API, no executor exists. The user has reviewed and approved the UX mock.

**Recommended next steps (for follow-up, not this task):**
1. Resolve the approval identity provider question (ADR open question #1).
2. Define allowlist maintenance procedures.
3. Gate the actual implementation behind a disabled-by-default feature flag, as specified.
4. Implement the canonical audit event struct and JSONL writer.
5. Implement the redaction library and proposal fingerprinting.
