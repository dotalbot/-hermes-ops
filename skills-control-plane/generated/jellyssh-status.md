# Skill Control Plane status: jellyssh

- Manifest validation: PASS
- Project state: `proposed`
- Governed skills: 14
- Routable now: `false`

## Actions

- [present] verify profile jellybase_jellyssh
- [present] verify profile jellybase_jellyssh_reviewer
- [present] verify local coordinator_checkout /home/jellybot/dev_projects/jellyssh
- [present] verify local coordinator_review_checkout /home/jellybot/dev_projects/jellyssh-review
- [present] create empty board jellyssh

## Blockers

- Jellybase repository deploy key is not registered and verified
- selected-ticket Flutter/Android quality gate is not verified; development dispatch must remain disabled

## Skill layers

- `code-review` — core_release / core-development@0.1.0
- `codebase-design` — core_release / core-development@0.1.0
- `database-data-review` — capability_pack / database-data@0.1.0
- `diagnosing-bugs` — core_release / core-development@0.1.0
- `flutter-mobile-review` — capability_pack / flutter-mobile@0.1.0
- `grill-with-docs` — core_release / core-development@0.1.0
- `implement` — core_release / core-development@0.1.0
- `jellyssh-controller-evidence-review` — project_overlay / jellyssh@0.1.0
- `jellyssh-drift-data-review` — project_overlay / jellyssh@0.1.0
- `jellyssh-mobile-ux-review` — project_overlay / jellyssh@0.1.0
- `jellyssh-ssh-security-review` — project_overlay / jellyssh@0.1.0
- `tdd` — core_release / core-development@0.1.0
- `to-spec` — core_release / core-development@0.1.0
- `to-tickets` — core_release / core-development@0.1.0
