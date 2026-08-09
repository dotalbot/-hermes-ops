---
name: jellyssh-drift-data-review
description: Use for JellySSH Drift schema, migration, query, retention, backup, or data-integrity changes.
version: 0.1.0
metadata:
  hermes:
    ownership: project-overlay
    project: jellyssh
    capability_pack: database-data
    approval_state: phase2-isolated-test
---

# JellySSH Drift data review

Read-only project overlay used only when the database/data trigger fires.

Require:

1. Drift schema version and generated representation are consistent.
2. Forward and rollback behavior is explicit, including downgrade limits.
3. Existing connection/profile/session data invariants are named and tested.
4. Destructive migration, default-value, nullability, uniqueness, and foreign-key effects are assessed.
5. Transaction and concurrent reader/writer behavior is reviewed.
6. Representative query plans or indexes are provided for material query changes.
7. Sensitive SSH metadata retention, deletion, export, backup, and restore are addressed.

Return active database/data mode, exact commit, evidence, severity-ordered findings, recovery assessment, and `PASS` or `BLOCK`.
