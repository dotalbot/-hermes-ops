## Fresh exact-target acceptance

Card requirements:

- fresh card whose exact parent set contains only the authorizing review card;
- declare `expected_acceptance_profile`; use `null` only for exact unassigned/operator mode, where both canonical task assignee and run profile must remain null;
- bind the normalized review-authority file by SHA-256;
- bind identical repository/base/specification/path/digest/target/tree authority;
- verify every product-specific acceptance check and record non-empty, non-secret evidence no larger than 4096 UTF-8 bytes per check;
- complete the canonical Kanban run—including a synthetic zero-duration run for unassigned/operator completion—with structured metadata containing the exact work-item and acceptance-card IDs, `verdict: PASS`, the exact review card ID, exact review-authority digest, identical closed authority, and the identical ordered check list; free-text result/summary alone is insufficient, and `tasks.current_run_id` must be null after completion;
- reject missing checks, failed checks, non-terminal review/acceptance, changed IDs/authority, producer substitution, extra parents, or mutation of either canonical snapshot before publication;
- publish normalized authority only from a normal parent/operator context reading canonical board SQLite in read-only mode;
- prepare handoff only. PR opening and merge remain separate unauthorized gates.
