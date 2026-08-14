# Claude adapter 0.4.6 read-only SDK analyze/test overlay

> **For Hermes:** Implement with TDD in `/tmp/hermes-ops-adapter-047`. Do not reuse attempt 005. Do not launch attempt 006 until this adapter is merged and post-merge verified.

**Goal:** Stop independent `analyze`/`test` from writing the shared Flutter SDK stamp `libimobiledevice.stamp`.

**Architecture:** Keep the real SDK read-only under Landlock. Give Flutter a disposable `FLUTTER_ROOT` overlay under `check-home` with dummy iOS USB binaries so cache update considers those artifacts current and any stamp write stays inside the overlay.

**Tech Stack:** Existing `claude_worker_adapter.py`, unittest.

**Confirmed seams:**

1. `run_checks()` prepare script / check environment.
2. Landlock write set remains `check-home` + `check-source` only.
3. Existing scoped format `--` and OAuth expiry tests stay green.

**Non-goals:** Attempt 006, product edits, mutating the real Flutter SDK, granting SDK write-file.

---

### Task 1: RED overlay/env assertions

Modify `skills-control-plane/tests/test_claude_worker_adapter.py` so analyze/test `run_checks` must:

- set `FLUTTER_ROOT` to `.../check-home/flutter-root`
- prepare dummy `idevicescreenshot`, `idevicesyslog`, `iproxy` under that overlay
- keep `--read-dir` on the real SDK
- omit `--write-dir` / `--write-file` on the real SDK

### Task 2: GREEN overlay prepare + env

Modify `run_checks()` to build the overlay during prepare and export `FLUTTER_ROOT`. Bump adapter/result/docs to `0.4.6`.

### Task 3: Verify and stop before publication
