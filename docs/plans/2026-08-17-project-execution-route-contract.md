# Project execution route-contract implementation plan

**Goal:** Make the Git-backed project setup authority declare validated, fail-closed execution route candidates by role, without dispatching work or changing any live profile/board.

**Architecture:** Add a required `execution_routes` catalog to the generic project definition. Each route binds a role to a declared Hermes owner profile, engine/host/account identity, exact model/provider when applicable, skill bundle, workspace, permissions, memory policy, preflight/evidence identifiers, and `fallback: block`. The existing manager validates cross-references during plan and doctor operations; routes remain descriptive authority until a later card-level selection/enforcement slice.

**Scope:** `project-definition.schema.json`, generic project setup template, manager validation, tests, and routing documentation.

**Non-goals:** Changing JellySSH product code or frozen Phase 2 bootstrap fields, creating profiles/boards/cards, dispatching workers, configuring real adapters, or automatically selecting a model. The existing evolving review-boundary integrity hash is updated only to bind the changed generic controller source.

## Steps

1. Add a failing manager test: valid route catalog passes; unknown owner/bundle and permissive fallback block.
2. Extend the project-definition schema with required, closed `execution_routes` entries.
3. Add semantic cross-reference validation in `managerlib.build_project_plan` and `doctor_project`.
4. Update the generic setup template and routing policy with the route catalog shape.
5. Run focused manager tests, full control-plane suite, JSON/YAML/Markdown validation, and independent review.
6. Commit and push only after all required checks/review pass; report any environment-only test failure separately.
