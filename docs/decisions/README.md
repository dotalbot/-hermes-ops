# Decision records

Use this folder for Hermes Ops, CHI, Mission Control, Kanban workflow, memory, gateway, dashboard, and operator-process decisions that should remain reviewable and reusable.

## Default template

Use `0000-adr-template.md` as the default starting point for new decision documentation in this area.

Create a new ADR when a document captures any of these:

- a durable architecture or workflow decision;
- an accepted default for how Hermes/CHI/Mission Control should operate;
- a trade-off between multiple viable approaches;
- a boundary that future workers should not rediscover or renegotiate;
- a choice that changes documentation, Kanban, gateway, dashboard, memory, or operating-manual behavior.

## Naming

1. Copy `0000-adr-template.md`; do not edit the template in place.
2. Name the new file `NNNN-short-kebab-case-title.md`.
3. Use the next unused four-digit number in this folder.
4. Keep the heading as `# ADR NNNN: <short decision title>`.
5. Start with `Status: Proposed`; change to `Accepted`, `Superseded`, or `Deprecated` when the outcome changes.

## When not to use an ADR

Do not create an ADR for routine implementation notes, command transcripts, temporary task status, or one-off bug notes. Use `docs/plans/`, `docs/runbooks/`, `docs/reports/`, or `docs/bugs/` for those instead.
