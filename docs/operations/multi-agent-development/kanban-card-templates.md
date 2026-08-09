# Kanban card templates

## Board policy

Keep `Spawner` as the proven Jellybase transport/worker validation board. Create a separate board for each development repository, for example:

```text
project-dev
logk-dev
```

Use `--board <slug>` explicitly in every command. Do not rely on the currently selected board.

Run only one Jellybase implementation card at a time until the project has deliberate remote Git-worktree isolation and a reviewed concurrency limit.

## Card 1: repository intake and branch preparation

```text
Title: Prepare feature branch for <feature>

Repository: /home/jellydev/dev_projects/<repo>
Target remote: jellydev@192.168.1.2 through jellybase-lan

Required actions:
1. Inspect git status, remotes, current branch, default branch, existing docs, and test commands.
2. If the repository clone does not exist, clone it under /home/jellydev/dev_projects/<repo>.
3. Fetch and fast-forward the default branch without overwriting local changes.
4. Create feat/<feature>.
5. Report repository path, branch, HEAD, remote, current status, and test commands.

Do not implement the feature. Do not use sudo. Block if local work is present or a push credential is unavailable.
```

## Card 2: design/specification gate

Use this only after an interactive design session has settled the feature.

```text
Title: Publish feature specification for <feature>

Repository: /home/jellydev/dev_projects/<repo>
Branch: feat/<feature>

Read the agreed design, repository context, ADRs, and domain language.
Publish the specification through the configured issue tracker.
Record scope, non-goals, acceptance criteria, testing decisions, and dependency assumptions.
Do not implement code.
```

## Card 3: implementation ticket

```text
Title: Implement <ticket title>

Repository: /home/jellydev/dev_projects/<repo>
Branch: feat/<feature>
Ticket: <issue URL or local ticket path>
Specification: <spec URL or path>

Required skills: implement, tdd, code-review

Required actions:
1. Read the ticket, specification, repository context, and relevant existing implementation.
2. Work only on the stated branch.
3. Use a focused failing test at the agreed public seam where practical.
4. Make the smallest behavior change satisfying the ticket.
5. Run focused tests during the work, then required project checks.
6. Update documentation if behavior, setup, API, or operations changed.
7. Run git diff --check and inspect the final diff.
8. Commit only the intended files and push the branch.

Final report must include: branch, commit, push result, exact checks and results, files changed, and any limitations.

No sudo. No PR creation. No merge. Block for unknown existing changes, secrets, production changes, or missing approvals.
```

## Card 4: independent validation/review

Make this card dependent on the implementation card.

```text
Title: Review <ticket title> on feat/<feature>

Repository: /home/jellydev/dev_projects/<repo>
Branch: feat/<feature>
Expected commit: <commit from implementation card>
Specification/Ticket: <references>

Read-only review:
1. Verify the exact branch and commit are present remotely.
2. Compare the diff with the ticket and specification.
3. Run the agreed non-mutating checks where possible.
4. Review tests, error paths, security, documentation, and operational impact.
5. Report PASS, BLOCKED, or a numbered list of findings.

Do not edit, commit, push, create a PR, merge, or use sudo.
```

## Card 5: review fix

Create a new card only if review finds a real issue.

```text
Title: Resolve review findings for <ticket>

Repository: /home/jellydev/dev_projects/<repo>
Branch: feat/<feature>
Parent review: <review card id>

Address only the numbered review findings. Add or update regression tests.
Run the affected checks, commit, and push. Report the new commit and which finding each change resolves.
```

## Dispatch pattern

Before dispatching:

1. confirm the target board, assignee, card body, branch, and dependencies;
2. inspect ready/running cards on the board;
3. confirm no other worker is editing the same remote checkout;
4. dispatch one card with `--max 1`;
5. verify the exact card state, board running list, and process/log evidence.

A card becoming `done` is not proof by itself. Verify the stated branch, commit, pushed remote, and durable artifacts.
