# Kanban adoption and board separation policy

Use this policy when deciding whether Hermes work stays in chat or becomes Kanban work.

## Default decision

Keep the work in chat only when all of these are true:

- It can be finished in one short session, usually under 30 minutes.
- It has no durable artifact, code change, deployment, or review gate.
- Losing the chat context would not lose important project state.
- No visual status tracking or parallel coordination is useful.
- The user does not need progress tracked across time.

Create or move to Kanban when any trigger below is true.

## Kanban triggers

1. Multi-step work
   - Use Kanban when the work has three or more meaningful steps, depends on sequencing, or needs a checklist.
   - Chat is enough for one-off lookups, tiny edits, or a single command with immediate verification.

2. Long-running work
   - Use Kanban when the work may run unattended, take more than one focused session, or needs heartbeats/status updates.
   - Chat is enough when the user is actively present and the task will finish in the current session.

3. Work needing review
   - Use Kanban when code, docs, config, deployment, or policy changes need human or peer review before being considered done.
   - The worker should write a handoff comment and block with `review-required: ...` instead of silently treating reviewable work as complete.

4. Work that must survive restart or context loss
   - Use Kanban when the next worker must recover goal, decisions, artifacts, test output, or blockers after a restart.
   - Durable outputs must live in the assigned repo under `docs/` or the project source tree, not only in scratch workspaces.

5. Work needing visual tracking
   - Use Kanban when the user benefits from seeing status columns, blocked cards, ownership, dependencies, or progress at a glance.
   - Chat is enough when status is obvious from the final answer.

6. Work with parallel lanes
   - Use Kanban when multiple independent lanes can proceed separately, such as research + implementation + review, or backend + frontend + docs.
   - Create separate cards with dependencies instead of burying parallel state in a chat thread.

## Board separation rules

Use one board per durable project area. Do not mix unrelated projects on one board just because the same assistant is doing the work.

Choose the board by the source of truth for the final artifact:

- `home-network`
  - Use for homelab infrastructure, Docker services, monitoring, backups, network maps, Homepage, Jellyoffice, and runtime deployment work.
  - Durable repo: `/home/jellybot/dev_projects/home-network`.
  - Example: "Add Borgmatic restore verification for jellyhome" belongs here.

- `portfolio`
  - Use for portfolio intelligence, project tracking, dashboards, investment/research summaries, and portfolio progress digests.
  - Durable repo: `/home/jellybot/dev_projects/portfolio-intel`.
  - Example: "Add a source-quality audit to the portfolio digest" belongs here.

- `continuous-hermes-improvement`
  - Use for Hermes operating model, Kanban policy, memory/Hindsight hygiene, assistant workflow, worker standards, gateway behavior, and local Hermes process docs.
  - Durable repo: `/home/jellybot/dev_projects/hermes-ops` unless changing Hermes Agent source code.
  - Example: "Define when chat work becomes Kanban work" belongs here.

- Hermes Agent source code
  - Use the `continuous-hermes-improvement` board, but write code changes in the Hermes Agent source repo, not `hermes-ops`.
  - Durable repo: `/home/jellybot/.hermes/hermes-agent` or the explicitly assigned source checkout.
  - Example: "Fix Mission Control API route behavior" belongs in the source repo with review.

- Cert study
  - Use a separate `cert-study` board when the task tracks lessons, study plans, labs, exam objectives, spaced repetition, or progress over weeks.
  - Durable folder/repo should be the user's chosen study notes location; if none is known, block and ask for the durable path before producing final artifacts.
  - Example: "Build a two-week subnetting lab plan" belongs on cert-study, not Hermes improvement.

- Other project areas
  - Create or use a separate board when a project has its own durable repo/folder, recurring workflow, independent roadmap, or visual tracking need.
  - Examples: `3dprint-loader`, `jellyfood`, `logk`, `personal-admin`, or a new client/project repo.
  - If the final artifact belongs in an existing repo, the board should match that repo's project area.

## Task creation checklist

Before creating a Kanban card, include:

- Board name.
- Concrete goal and acceptance criteria.
- Durable output path or source repo.
- Workspace kind: prefer `dir:` or `worktree:` for durable output.
- Assignee profile.
- Review requirement, if any.
- Dependencies or child lanes, if any.

If the durable output path is unknown, create the card as blocked or block before writing final artifacts.
