# Feature lifecycle

## 0. Intake

The operator supplies:

```text
Repository: Git URL or existing /home/jellydev/src/<repo> path
Feature: desired user-visible outcome
Constraints: technology, security, compatibility, time, and non-goals
Acceptance criteria: observable conditions for success
```

Before editing, inspect repository status, remotes, default branch, existing documentation, and the test/build commands. Preserve any uncommitted or untracked work.

## 1. Prepare the development clone and branch

For a new clone, place the code under:

```text
/home/jellydev/src/<repo>
```

Then:

1. inspect the working tree;
2. fetch the remote and fast-forward the default branch without overwriting local work;
3. create a meaningful branch, normally `feat/<short-description>`;
4. record the repository path, branch, commit, and expected test command on the Kanban card.

Use `fix/`, `docs/`, `test/`, `refactor/`, or `chore/` prefixes when they describe the work better. The standing exception is the `home-network` repository, which uses its explicit direct-`main` convention.

## 2. Configure the Matt workflow once per repository

Before the first engineering flow, run `setup-matt-pocock-skills` interactively. It establishes the repository's issue tracker and domain-document conventions. See [Matt Pocock skills](matt-pocock-skills.md).

This is an operator interaction step, not an unattended card: the skill asks where issues are tracked and which repository convention to use.

## 3. Design before implementation

For an existing codebase, run `grill-with-docs` in one continuous design session. It reads the repository context, clarifies unresolved design branches, and records durable decisions.

Use `prototype` only when a design question needs runnable evidence. Keep prototype code disposable. Record the conclusion, not the prototype as production code.

When a design session needs a fresh context window, use `/context-handoff`; do not rely on the reserved `/handoff` command.

## 4. Specify and split work

Use `to-spec` to turn the agreed design into a feature specification. Then use `to-tickets` to produce small vertical-slice tickets with real dependency edges.

A good ticket:

- delivers an observable end-to-end behavior;
- is small enough for one fresh worker context;
- declares its blocker tickets;
- has acceptance criteria and test evidence;
- avoids stale file-path or implementation-detail guesses unless the codebase has been inspected.

The operator approves ticket granularity and dependencies before implementation cards are dispatched.

## 5. Implement one ticket at a time

Assign one code-editing card to `jellybase_hermes` with the exact remote repository and branch. Force-load `implement`, `tdd`, and `code-review` as appropriate.

The implementation sequence is:

1. read the ticket, specification, context, and existing similar behavior;
2. write a focused failing behavior test where a stable seam exists;
3. run the test and confirm it fails for the intended reason;
4. implement the smallest behavior that makes it pass;
5. run focused tests repeatedly;
6. run required lint, typecheck, build, integration, and full-suite checks;
7. update relevant documentation;
8. inspect `git diff` and run `git diff --check`;
9. commit only intended files and push the feature branch.

## 6. Validate and independently review

A validation/review card is dependent on implementation. It verifies the exact pushed commit, stated acceptance criteria, tests, docs, and branch diff.

A review finding creates a new linked fix card. It does not silently re-run the completed implementation card, and a review card should not become a second untracked editor.

## 7. Operator decision

After the review passes, report the remote repository, branch, commit, tests, review result, and any limits. Creating a pull request and merging are explicit operator actions, not automatic worker behavior.

## Stop conditions

Block the card and request operator input when:

- sudo, a password, a secret, or a production change is needed;
- Git status is not clean and the existing work is not understood;
- the remote branch moved unexpectedly;
- acceptance criteria are ambiguous or contradict the specification;
- test failures are unrelated and cannot be safely distinguished;
- a required review, push permission, or external dependency is unavailable.
