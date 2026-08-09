# Skills Manager operating-overview visual review

## Native-page readback

PASS. The local draw.io MCP listed and read back the final uncompressed pages `Operating Map`, `Project Setup`, and `Skill Lifecycle` from source SHA-256 `3004d566860fb72c8f6efe17ae64e7400119ec8c7439d8c43397c67122896376`.

## First visual pass

BLOCK.

Concrete defects:

- Edge labels collided with strokes and other labels.
- Several long orthogonal connectors crossed intermediate cards, hiding route segments and making their source ambiguous.
- The project-setup rollback fan-out obscured the central control path.
- The skill-lifecycle cross-row transitions were routed through stage cards.

## Source-level corrections

- Quoted the Mermaid Git remote label so Mermaid parses punctuation safely.
- Removed redundant connector labels and replaced them with compact legends.
- Repositioned execution/evidence cards to align implementation, review, Git, and verdict flow.
- Removed redundant cross-page/fan-out edges where containment and node text already express the relationship.
- Added deterministic, source-owned orthogonal waypoints for non-trivial routes.
- Bound the source-driven preview renderer to those native waypoints.
- Split the complete story into three named pages rather than widening one page.

## Final visual pass

PASS on all three pages.

- Text is readable at the 1480 × 820 documentation view; no clipping or overlap remains.
- Primary paths and arrowheads are visible.
- Connectors use clear gaps/corridors instead of crossing cards.
- Containers, colour semantics, and reading order distinguish authority, control, execution, evidence, approval, and rollback.
- The operating map provides the complete control-to-execution-to-acceptance story; the other pages provide setup and skill-lifecycle detail.

Final artifacts:

- `diagram_creator/artifacts/source/skills-manager-operating-overview.drawio`
- `diagram_creator/artifacts/preview/skills-manager-operating-overview-operating-map.svg`
- `diagram_creator/artifacts/preview/skills-manager-operating-overview-project-setup.svg`
- `diagram_creator/artifacts/preview/skills-manager-operating-overview-skill-lifecycle.svg`
