# ADR NNNN: <short decision title>

Status: <Proposed | Accepted | Superseded | Deprecated>
Date: <YYYY-MM-DD>

## Context

Describe the background, constraints, and problem that forced a decision.

Include enough detail for a future operator to understand why the decision mattered without rereading the whole project history.

## Decision

State the decision plainly.

Use bullets if the decision has several rules or boundaries.

## Consequences

List the expected effects of this decision.

### Benefits

- <Benefit or operational simplification>

### Costs and risks

- <Trade-off, maintenance cost, or risk introduced>

## Alternatives considered

- <Alternative 1>: <why it was not chosen>
- <Alternative 2>: <why it was not chosen>

## Related links

- <Link to issue, Kanban card, spec, runbook, PR, or prior ADR>

## Naming and numbering instructions

1. Copy this file when creating a new ADR; do not edit the template in place.
2. Name new ADRs as `NNNN-short-kebab-case-title.md`, for example `0003-guarded-mission-control-actions.md`.
3. Use the next unused four-digit number in `docs/decisions/`.
4. Keep the title line in the form `# ADR NNNN: <title>` so ADRs are easy to scan.
5. Start new records as `Status: Proposed`; change to `Accepted`, `Superseded`, or `Deprecated` when the decision outcome changes.
6. If an ADR supersedes another ADR, add that relationship under Related links.
