# Operator checklist

## Before starting a feature

- [ ] Identify the Git remote or existing Jellybase path.
- [ ] Confirm the target is a dedicated development clone, not a production checkout.
- [ ] Confirm the selected execution lane is declared by the approved project/work-item routing contract: agent type, host, profile or adapter, model/provider, skill bundle, workspace, permissions, memory route, preflight, evidence contract, and fallback-to-block behavior. Hermes on Jellyberry remains the Kanban assignee and orchestration authority regardless of the selected execution engine.
- [ ] Inspect repository status before fetch, branch creation, or edits.
- [ ] Preserve and understand existing uncommitted and untracked files.
- [ ] Define the feature outcome, constraints, non-goals, and observable acceptance criteria.
- [ ] Select or create a dedicated project board rather than mixing unrelated work.
- [ ] Confirm the assigned project-specific profile exists and matches the approved repository, host, skill, and memory-bank route; never silently fall back to `jellybase_hermes`.

## Before implementation

- [ ] The feature branch exists and is recorded on the card.
- [ ] Every pinned workflow skill is installed at the approved version with recorded provenance and compatibility evidence.
- [ ] Design questions were resolved through `grill-with-docs` or a suitable alternative.
- [ ] A spec exists and scope/non-goals are clear.
- [ ] Ticket breakdown and dependency edges were approved.
- [ ] The implementation card includes the exact remote path, branch, ticket, acceptance criteria, and final report requirements.
- [ ] No parallel worker is editing the same checkout or branch.
- [ ] For a Claude adapter card, live preflight proves the exact skill hashes, repository-scoped GitHub access, Git attribution, clean coordinator clone, requested base, and no conflicting attempt path.
- [ ] A Claude implementation card uses an isolated feature worktree and an independent reviewer; a Claude implementation session never approves its own candidate.

## Before calling implementation complete

- [ ] Focused behavior tests passed.
- [ ] Relevant project checks passed: lint, typecheck, build, integration tests, or full suite as appropriate.
- [ ] `git diff --check` passed.
- [ ] The final diff was inspected for scope creep, secrets, generated noise, and accidental changes.
- [ ] Behavior/setup/API/operations docs are current.
- [ ] Intended files only were committed.
- [ ] The feature branch was pushed.
- [ ] The implementation card records the branch, commit, commands, results, and limitations.

## Before approving a branch

- [ ] An independent standards/spec review examined the exact pushed commit.
- [ ] Review findings are either resolved by a linked fix card or explicitly accepted by the operator.
- [ ] The remote branch still points at the reviewed commit.
- [ ] Required runtime verification was performed when the repository backs a live service.
- [ ] A pull request or merge has not been created automatically.

## Immediate stop conditions

Block and request operator direction if any of these occur:

- sudo, passwords, tokens, or secret values are required;
- the worker reaches a production system or live deployment checkout;
- Git reports unexpected local changes, conflicts, or a moved remote branch;
- a card needs to alter the existing remote `~/.hermes` directory;
- a broad sync/archive/download starts instead of bounded repository work;
- acceptance criteria are unclear or requirements contradict one another;
- the test failures cannot be attributed to the intended change;
- push permissions, CI, or required external services are unavailable.

## Recovery

For a stuck worker, inspect the exact card, its logs, and its runs before taking action. Reclaim only the exact worker/card involved. After unblocking, verify the assignee and dispatch state before allowing another run. Never use a running worker process alone as proof that a particular card is still active.
