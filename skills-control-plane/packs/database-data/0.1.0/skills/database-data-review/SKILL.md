---
name: database-data-review
description: Use when persistent data, schema, migration, query, retention, backup, or recovery risks trigger.
version: 0.1.0
metadata:
  hermes:
    ownership: capability-pack
    capability_pack: database-data
    approval_state: phase2-isolated-test
---

# Database and data review

Review only when a declared database/data trigger fires. Do not edit implementation files.

Required evidence:

1. State affected data contracts and invariants.
2. Classify compatibility, destructive/lossy behavior, and reversibility.
3. Review forward and rollback migration procedures.
4. Review transaction, locking, concurrency, and consistency behavior.
5. Require query-plan and representative-volume evidence when query risk is material.
6. Review privacy, retention, deletion, backup, restore, replication, and disaster-recovery implications where applicable.
7. Identify unresolved hard stops and return `BLOCK` if required evidence is absent.

Modes:

- `database-design`: schemas, indexes, constraints, relationships, transactions.
- `data-engineering`: pipelines, backfills, transformations, external contracts.
- `data-governance`: privacy, retention, deletion, regulated data, backup and recovery.

Output must include mode, trigger, evidence reviewed, findings ordered by severity, rollback assessment, and `PASS` or `BLOCK`.
