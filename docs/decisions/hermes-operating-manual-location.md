# Hermes operating manual location recommendation

## Recommendation

Save Dominic's concise Hermes operating manual as a new file at:

`docs/operations/dominic-hermes-operating-manual.md`

## Why this fits

- This repository is explicitly the private durable home for Dominic's Hermes operating knowledge, local conventions, Kanban-produced runbooks, assistant behavior guidance, and review gates.
- `docs/operations/` is defined in `docs/README.md` for local operating rules, schedules, dashboards, and service notes, which matches a Dominic-specific Hermes manual better than a generic public user guide.
- The upstream Hermes Agent docs site under `/home/jellybot/.hermes/hermes-agent/website/docs/` is better for generic product documentation. Dominic-specific preferences, homelab paths, approval gates, Discord habits, Hindsight rules, and Kanban workflow conventions should stay in this private operator repo.
- `docs/guides/` is better for reusable how-to procedures, and `docs/runbooks/` is better for command-heavy operational procedures. A compact standing manual that explains how Dominic wants Hermes operated is local operating policy, so `docs/operations/` is the best fit.

## New file vs existing file

Create a new file rather than updating an existing one. Existing docs define repository conventions and Kanban output rules; none are the manual itself.

## Nearby docs to keep consistent

- `README.md` — repository purpose and standard docs layout.
- `docs/README.md` — folder definitions and durable output path rule.
- `docs/guides/kanban/output-path-guide.md` — Kanban task output and completion expectations.
- `docs/specs/kanban-durable-workspace-standard.md` — durable workspace and commit/push standard.
- `/home/jellybot/.hermes/hermes-agent/website/docs/` — upstream public docs, useful as reference material only when content is generic and safe to publish.

## Link/reference suggestion

After the manual is written, add a bullet for `docs/operations/dominic-hermes-operating-manual.md` to `docs/README.md` or an operations index if one exists by then. Do not link it from upstream Hermes Agent website docs unless the content is generalized and scrubbed of Dominic-specific details.
