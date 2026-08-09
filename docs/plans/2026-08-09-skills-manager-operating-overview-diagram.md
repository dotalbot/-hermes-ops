# Skills Manager operating-overview diagram plan

## Goal

Fix the Mermaid parse error in the first architecture diagram and add a formal, editable draw.io operating overview of the Phase 2.5 Skills Manager control plane.

## Audience and question

- Audience: operator and engineering reviewers.
- Question: how do authority, planning, approval, project setup, profile routing, execution, verification, skill promotion, and rollback work together?

## Scope

- Three draw.io pages: operating map, project setup, and skill lifecycle.
- Left-to-right reading direction with compact horizontal composition.
- Git authority, immutable plans, operator approval hashes, non-routable setup/candidates, exact profiles/skills/banks, isolated workspaces, independent review, fleet projections, and rollback.
- No credentials, tokens, secret values, host-specific private paths, or write-capable Desktop controls.

## Outputs

- Native source: `diagram_creator/artifacts/source/skills-manager-operating-overview.drawio`
- Per-page SVG previews: `diagram_creator/artifacts/preview/skills-manager-operating-overview-*.svg`
- Structural validator/renderer: `diagram_creator/tests/validation/validate_and_render_drawio.py`
- Validation and visual-review evidence: `diagram_creator/tests/results/`

## Verification

- Render every Mermaid block in the changed Markdown file with a pinned Mermaid CLI.
- Parse draw.io XML; assert page names, unique IDs, valid references, edge geometry, minimum font sizes, and required labels.
- List and read back every page through the local draw.io MCP.
- Render every page from the native source and inspect previews at normal documentation scale.
- Run repository tests, manager verification, `git diff --check`, focused diff review, and independent review before commit.

## Rollback

The change is documentation and editable diagram artifacts only. Roll back by reverting the focused commit; no runtime state is changed.
