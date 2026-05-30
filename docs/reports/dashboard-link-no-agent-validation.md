# Dashboard link no-agent validation

Date: 2026-05-30

Purpose: validate the implemented `dashboard-link-watchdog` no-agent cron script in representative quiet, action-required, digest, and failure cases before recommending the next conversion candidates.

## Runtime configuration checked

Installed cron job in `/home/jellybot/.hermes/cron/jobs.json`:

- Job id: `adf27938fea4`
- Name: `dashboard-link-watchdog`
- Script: `dashboard_link_check.py`
- Schedule: `every 30m`
- `no_agent`: `true`
- Delivery: `local`
- `enabled_toolsets`: `null`
- `model` / `provider`: `null`
- Last status: `ok`

The recorded cron output at `/home/jellybot/.hermes/cron/output/adf27938fea4/2026-05-30_11-25-17.md` says:

```text
Mode: no_agent (script)
Status: silent (empty output)
```

This confirms the scheduler ran the script path directly and did not invoke an agent/LLM loop for the successful tick.

## Validation command

A temporary local HTTP server was used so the checks did not depend on external dashboard availability. The command created good, bad, malformed, and missing config cases under `/tmp/dashboard-link-validation-vqm9jbsz` and ran both the repo script and runtime cron copy:

```bash
python3 - <<'PY'
# created local test server and invoked scripts/dashboard_link_check.py
# with isolated --config, --state, and --lock paths
PY
```

Also compiled both script copies:

```bash
python3 -m py_compile scripts/dashboard_link_check.py /home/jellybot/.hermes/scripts/dashboard_link_check.py
```

## Results

| Case | Exit | Stdout | Stderr | Result |
|---|---:|---:|---:|---|
| `quiet_good_first` | 0 | 0 bytes | 0 bytes | Passing config stayed silent. |
| `quiet_good_second` | 0 | 0 bytes | 0 bytes | Repeated passing config stayed silent. |
| `runtime_copy_quiet_good` | 0 | 0 bytes | 0 bytes | Runtime cron copy stayed silent on pass. |
| `digest_good` | 0 | 161 bytes | 0 bytes | Explicit digest mode printed a deterministic report. |
| `failure_alert_first` | 0 | 329 bytes | 0 bytes | Action-required link failures printed a concise fixed alert. |
| `failure_alert_suppressed_repeat` | 0 | 0 bytes | 0 bytes | Duplicate unchanged failure fingerprint was suppressed. |
| `failure_alert_no_state` | 0 | 329 bytes | 0 bytes | `--no-state` forced the failure alert for testing. |
| `malformed_config` | 1 | 0 bytes | 48 bytes | Config schema failure exited non-zero with clear error. |
| `missing_config` | 1 | 0 bytes | 71 bytes | Missing config exited non-zero with clear error. |

Representative action-required output:

```text
Dashboard link check failed:
- bad expected text: expected status 200, got status 200; expected status 200 and text 'gateway'; attempts=1; url=http://127.0.0.1:42033/wrong-text
- service down: expected status 200, got no response; URLError: <urlopen error [Errno 111] Connection refused>; attempts=1; url=http://127.0.0.1:9/nope
```

Representative digest output:

```text
Dashboard link check digest:
- checked: 1
- passed: 1
- failed: 0
- config: /tmp/dashboard-link-validation-vqm9jbsz/good.json
- ok: local ok -> status 200, 13ms
```

## Failure behavior

- Per-link service failures are normal action-required checks: the script exits 0 and prints a fixed `Dashboard link check failed:` message only when the failure fingerprint is new or `--no-state` is used.
- Duplicate identical failures are quiet by default to avoid repeated chat spam.
- Bad configuration and missing configuration are operator failures: the script exits non-zero with a short stderr message, letting Hermes no-agent cron deliver its normal job-error alert.
- The script uses only the Python standard library (`argparse`, `json`, `urllib`, etc.), so there are no Python package dependencies to install. Missing runtime dependencies are limited to `python3` itself and readable config/state/log paths.
- Logging is compact: one status line per completed run in `/home/jellybot/.hermes/logs/dashboard_link_check.log`; logging failures are swallowed so log write issues do not turn successful checks into noisy alerts.

## Conclusion

Quiet/no-news behavior is confirmed: passing runs and duplicate unchanged failures produce empty stdout, which Hermes no-agent cron treats as silent. Action-required failures, explicit digest mode, and operator/config errors are deterministic and clear enough for debugging without invoking an LLM.
