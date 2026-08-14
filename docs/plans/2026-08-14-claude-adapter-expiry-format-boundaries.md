# Claude adapter 0.4.5 expiry/format boundary replacement

> **For Hermes:** Implement this plan with TDD in `/tmp/hermes-ops-adapter-046`. Do not edit `/tmp/hermes-ops-adapter-044-postmerge`. Do not publish blocked SHA `d4b2f9e73176c485cf19607ebc7fa9ada4c56d43`.

**Goal:** Replace blocked adapter candidate `d4b2f9e…` with a fresh 0.4.5 candidate that keeps the intended auth/scoped-format work and fail-closes the two independent-review blockers.

**Architecture:** Reapply the unpublished 0.4.5 changes from exact base `697eb2c1af059a581ac140dadf895dd339fa2db9` onto a new branch. Then lock two public seams with RED tests and minimal production fixes: the generated OAuth expiry gate must accept only real finite numbers, and request-derived Dart formatter operands must follow `--`.

**Tech Stack:** Python 3 stdlib, `unittest`, JSON Schema, existing `claude_worker_adapter.py`.

**Confirmed seams:**

1. `oauth_expiry_check_script()` executed in a temporary `HOME` with expiry-only credential fixtures.
2. `check_command(request, "format")` plus request-schema/scope validation for option-like `app/` paths.
3. Existing review-mode format command and full-output scan/failure/publication-suppression tests remain green.

**Non-goals:**

- Attempt 005, product edits, PR/merge unless later authorized.
- Reusing blocked SHA/branch/review assets unchanged.
- Emitting token values.

---

### Task 1: Reapply unpublished 0.4.5 changes

**Objective:** Recreate the intended 0.4.5 tree from base without mutating blocked `d4b2f9e…`.

**Step:** Cherry-pick `d4b2f9e73176c485cf19607ebc7fa9ada4c56d43` onto `fix/claude-worker-expiry-format-boundaries`.

Expected: new commit, same intended files, adapter version still `0.4.5`.

### Task 2: RED OAuth expiry matrix

**Files:**

- Modify: `skills-control-plane/tests/test_claude_worker_adapter.py`

Add/extend the HOME-isolated gate test so access and refresh expiries independently cover:

- expired → exit 2
- future finite → exit 0
- `NaN` → exit 2
- `Infinity` → exit 2
- `-Infinity` → exit 2
- string/malformed type → exit 2
- boolean `true`/`false` → exit 2

Assert empty stdout/stderr. Do not put token fields in fixtures.

Run focused test; expect current `d4b2f9e` logic to fail on NaN/Infinity/boolean.

### Task 3: GREEN finite expiry validation

**Files:**

- Modify: `skills-control-plane/scripts/claude_worker_adapter.py` `oauth_expiry_check_script()`

Require `type(value) in (int, float)` (excludes bool), `math.isfinite(value)`, and `value > minimum_expiry_ms`. Fail closed otherwise. Import `math` in the generated script. Never print credential values.

### Task 4: RED formatter option-injection tests

**Files:**

- Modify: `skills-control-plane/tests/test_claude_worker_adapter.py`

Cover:

- schema + scope accept `app/--help` and `app/-x`
- rendered implementation command contains `--` before those operands and does not become `dart format ... --help`
- normal two-file scope still formats `lib/example.dart test/example_test.dart` after `--`
- outside-app path still rejected
- review mode remains `format --output=none --set-exit-if-changed lib/ test/`

Run focused tests; expect current command construction to fail the `--` / `--help` assertions.

### Task 5: GREEN `--` before request-derived formatter paths

**Files:**

- Modify: `skills-control-plane/scripts/claude_worker_adapter.py` `check_command()`

Insert `--` after `--set-exit-if-changed` and before request-derived relative paths. Keep review-mode command unchanged. Keep `shlex.join`.

### Task 6: Verify and stop before publication

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v skills-control-plane/tests/test_claude_worker_adapter.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills-control-plane/tests -p 'test_*.py' -q
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 -m py_compile skills-control-plane/scripts/*.py
git diff --check
python3 skills-control-plane/scripts/managerctl.py verify
git fsck
```

Then live Jellybase preflight from the exact replacement commit, then isolated dual review. Do not push/open PR unless asked.
