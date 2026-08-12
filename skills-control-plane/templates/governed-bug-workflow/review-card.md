## Fresh independent exact-target review

Card requirements:

- fresh card and attempt; do not inherit any earlier verdict;
- assignee: `jellybase_jellyssh_reviewer`;
- workspace: `scratch`;
- max runtime: `20m`;
- max retries: `1`;
- exact repository, base commit, specification commit/path/authenticated digest, target commit, and target tree;
- restricted `jellyssh_review` MCP tools only;
- consume only same-attempt authenticated capability evidence;
- independently return Standards PASS/BLOCK and Specification PASS/BLOCK with findings;
- run fixed focused smoke before policy-required broad suite;
- final clean/exact-target check;
- canonical latest-terminal-run metadata must include the exact `work_item`, `verdict`, `findings`, both axes, `capability_evidence_sha256` for the exact attached same-attempt capability JSON, and the closed authority object required by `governancectl review-bind`; after completion `tasks.current_run_id` must be null, and the task assignee and latest-run profile must equal the review contract's `expected_reviewer_profile`.

A capability PASS is readiness evidence only. It cannot be copied into the semantic verdict.
