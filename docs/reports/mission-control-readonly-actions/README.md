# Mission Control read-only actions handoff

Source task: continuous-hermes-improvement `t_06bc53a4`.

The implementation is in local Hermes Agent worktree:

- `/tmp/hermes-readonly-actions`
- branch `feat/mission-control-readonly-actions`
- rebased onto current `origin/main` on 2026-05-30

Current local commits after rebase:

- `76a669fc2 feat: add read-only mission control actions`
- `2ddc8ccac feat: add read-only mission control UI`

Push status:

- Direct push to `git@github.com:NousResearch/hermes-agent.git` failed: permission denied for `dotalbot`.
- `gh` is unavailable/not authenticated on this host.
- No `dotalbot/hermes-agent` fork exists or is accessible by SSH.

Verification after rebase:

- `cd /tmp/hermes-readonly-actions/web && npm run build` passed.
- `uv run --with pytest --with pytest-asyncio --with pytest-timeout --with fastapi --with starlette --with httpx python -m pytest tests/hermes_cli/test_web_server.py -q -k readonly` passed: 9 passed, 150 deselected.
- `git diff --check` passed.

This directory preserves `git format-patch` output for the two commits so the work can be applied to a valid fork/upstream branch later.
