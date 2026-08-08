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

## How to create a new ADR

```sh
# 1. Find the next unused number
cd docs/decisions/
next=$(printf "%04d" $((10#$(ls [0-9][0-9][0-9][0-9]-*.md 2>/dev/null | grep -oP '^\K\d{4}' | sort | tail -1) + 1)))

# 2. Copy the template
cp 0000-adr-template.md "${next}-short-kebab-case-title.md"

# 3. Edit the new file:
#    - Update the heading line:    # ADR NNNN: <title>
#    - Fill in Status, Date, Context, Decision, Consequences, Alternatives
#    - Update Related links

# 4. Start with Status: Proposed
#    — change to Accepted, Superseded, or Deprecated when the outcome evolves.

# 5. Commit
git add "${next}-short-kebab-case-title.md"
git commit -m "docs: ADR ${next} — <short decision title>"
```

The template (`0000-adr-template.md`) defines the expected sections — use it as your starting point and do not edit it in place.

## When not to use an ADR

Do not create an ADR for routine implementation notes, command transcripts, temporary task status, or one-off bug notes. Use `docs/plans/`, `docs/runbooks/`, `docs/reports/`, or `docs/bugs/` for those instead.
