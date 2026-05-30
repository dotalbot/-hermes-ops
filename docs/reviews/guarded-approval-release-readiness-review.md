# Release readiness review: Guarded Mission Control approval design

Reviewed: 2026-05-30
Artifacts reviewed:
- `docs/decisions/guarded-mission-control-write-actions.md` (ADR)
- `docs/runbooks/approved-mission-control-actions.md` (runbook)
- `docs/specs/mission-control-guarded-write-audit-logging.md` (audit logging spec)
- `docs/operations/mission-control-read-only-actions.md` (read-only UX design)

## Summary

**PASS** — all four artifacts are consistent with the stated goal: design but do not enable dangerous Mission Control actions. No destructive or write execution path is enabled, every candidate action has documented coverage for the seven required fields, and remaining risks are explicitly documented as open questions.

## Candidate action coverage (7 required fields)

Each of the 5 candidate action classes in the ADR is expanded in the runbook with full coverage:

| Requirement | Restart | Rerun collectors | Backup checks | Restore drills | Docker recreate |
|---|---|---|---|---|---|
| Approval requirements | ADR §55-57, runbook §85-87 | ADR §72-74, runbook §144-146 | ADR §90-91, runbook §199-201 | ADR §109-111, runbook §256-258 | ADR §127-128, runbook §316-318 |
| Exact command visibility | ADR §47, runbook §67-71 | ADR §65, runbook §127-131 | ADR §82, runbook §183-185 | ADR §100, runbook §237-241 | ADR §119-120, runbook §296-301 |
| Target host | ADR §48, runbook §61-62 | ADR §66, runbook §121-123 | ADR §83-84, runbook §176-178 | ADR §101-102, runbook §231-233 | ADR §120, runbook §288-291 |
| Rollback plan | ADR §51, runbook §96-101 | ADR §69, runbook §156-158 | ADR §86, runbook §211-213 | ADR §105, runbook §268-270 | ADR §123, runbook §329-331 |
| Risk level | ADR §43, runbook §86 | ADR §61-62, runbook §146 | ADR §78, runbook §200 | ADR §96, runbook §257 | ADR §115, runbook §317 |
| Logging | Runbook §105-108, audit spec full schema | Runbook §162-165, audit spec | Runbook §217-220, audit spec | Runbook §274-277, audit spec | Runbook §335-338, audit spec |
| Secret redaction | ADR §22/§174, runbook §73 | ADR §22, runbook §132 | ADR §92, runbook §187 | ADR §22/§111, runbook §243 | ADR §22, runbook §303 |

## Cross-reference consistency

| Ref pair | Status | Notes |
|---|---|---|
| ADR → Runbook | ✓ PASS | All 5 candidate classes expanded with action ids, command shapes, preflight checks |
| ADR → Audit spec | ✓ PASS | Events map to ADR's required approval path (proposed→approved/denied → execution → completed/failed) |
| ADR → UX mock | ✓ PASS | UX mock references ADR; read-only boundary matches ADR's "read-only default" guardrail |
| Runbook → Audit spec | ✓ PASS | Runbook's "expected logs" per action are implemented by audit spec's sink design |
| UX mock → Runbook | ✓ PASS | UX mock references future write-action runbook in "Related docs" |
| UX mock → Audit spec | ✓ PASS | UX mock references audit logging spec |

## No destructive/write path enabled

All four artifacts explicitly assert design-only / read-only status:

- ADR: "design-only: no write, destructive, restart, restore, Docker, collector, or backup-health action may execute" (§10)
- Runbook: "execution disabled" header, "Mission Control must remain read-only" (§12)
- Audit spec: "It does not authorize live write actions" (§12)
- UX mock: "Mission Control is read-only today" (§9)

Confirmed: no executable scripts, no write-action endpoints, no feature flags enabled in reviewed files.

## Guardrail coverage

The ADR defines 11 guardrails (§167-180); all are addressed across the four artifacts:

1. Read-only default — explicit in all docs ✓
2. Exact command display — runbook has command shape examples ✓
3. Host display — runbook has `<HOST>` placeholders per action ✓
4. Rollback display — runbook has rollback steps for all 5 actions ✓
5. Risk labeling — all actions have risk levels in runbook ✓
6. Secret redaction — audit spec has full redaction ruleset, examples, fail-closed conditions ✓
7. Allowlisted actions only — runbook has explicit allowlist action ids, ADR mentions allowlists ✓
8. Parameter validation — runbook has allowlist/preflight checks per action ✓
9. Short-lived approvals — audit spec includes `approval_ttl_seconds` ✓
10. Revalidation — ADR §23, runbook step 4 ✓
11. Audit trail — full audit spec with 4-sink design, fail-closed on canonical ledger loss ✓
12. Safe failure — audit spec §440-467 details before-mutation/after-mutation failure handling ✓

## Findings

### Minor gaps (non-blocking)

1. **Asymmetric cross-referencing** — The UX mock (2026-05-30) references all three other docs, but the ADR, runbook, and audit spec (all 2026-05-29) do not reference the UX mock back. Recommend adding "Related: docs/operations/mission-control-read-only-actions.md" to the frontmatter of the other three docs for complete circular cross-referencing.

2. **No explicit risk→TTL timeout table** — The audit spec examples use `approval_ttl_seconds: 300` (5 min) for restart and `600` (10 min) for restore drills, but there is no documented default mapping from risk level to timeout. The ADR open question (§229) asks about this explicitly. Should add a timeout table: `low→600, medium→300, high→120` (example values) or similar in the audit spec or runbook.

### Open questions (documented, not blocking)

The ADR's 7 open questions (§224-231) remain open and are explicitly documented:
- Identity provider for approval events
- Second confirmation for high-risk actions
- Audit record location/retention (audit spec proposes a specific path but retention is not specified)
- First allowlist scope
- Non-shell operation representation
- Per-risk-level timeouts
- Separate dry-run modes for backup/restore

### Prior reviewer findings

The audit logging spec parent reviewer (t_c3648498) flagged 4 findings (3 high, 1 medium) on fingerprint alignment, sink status mutability, canonical-ledger failure path, and incomplete `audit_sink_recovered` spec. The current version of the spec appears to address all four:
- Fingerprint approach now aligned (pre-redaction keyed HMAC, digest-only persistent) ✓
- Sinks documented as per-event emission attempt, not mutable lifecycle summary ✓
- Canonical-ledger failure path has explicit before-mutation/after-mutation handling ✓
- `audit_sink_recovered` defined with required fields ✓

## Conclusion

**PASS for release readiness.** The design satisfies the original constraint: design is complete, no write/destructive path is enabled, all candidate actions have the 7 required coverage fields, and remaining implementation questions are explicitly documented as open items. Recommend addressing the two minor gaps before the implementation phase begins.
