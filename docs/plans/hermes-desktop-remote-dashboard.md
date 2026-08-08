# Hermes Desktop Remote Dashboard Implementation Plan

> **For Hermes:** Use this plan to implement Hermes Desktop on Mac as the UI for the Hermes runtime on jellyberry.

**Goal:** Use Hermes Desktop on the Mac to interact with the existing Hermes runtime on jellyberry without exposing unauthenticated dashboard/tool access.

**Architecture:** The Mac is only the UI. jellyberry remains the runtime host for sessions, memory, tools, gateway, cron, and homelab access. The connection should use Tailscale direct access to the Hermes dashboard on jellyberry, protected with dashboard username/password auth and no `--insecure` flag.

**Tech Stack:** Hermes Agent dashboard, Hermes Desktop, Tailscale, systemd user service, basic dashboard auth, optional SSH tunnel fallback.

---

## Current state observed

- Host: `jellyberry`
- LAN IP: `192.168.1.159`
- Tailscale IP: `100.68.81.120`
- Dashboard process is running on `0.0.0.0:9119`
- Initial state before implementation:
  - Dashboard command included `--insecure`
  - `/api/status` returned `auth_required: false` and `auth_providers: []`
  - `/home/jellybot/.hermes/.env` was missing dashboard auth keys
- Implemented state as of 2026-06-13:
  - Dashboard auth keys are present in `/home/jellybot/.hermes/.env`
  - Backup created at `/home/jellybot/.hermes/.env.backup-before-dashboard-auth-20260613-221435`
  - User service exists at `/home/jellybot/.config/systemd/user/hermes-dashboard.service`
  - Service is enabled and active
  - User linger is enabled
  - Live dashboard command has no `--insecure`
  - `/api/status` returns `auth_required: true` and `auth_providers: ["basic"]` on local, Tailscale, and LAN URLs

## Decision

Use Tailscale remote dashboard access with strong dashboard basic auth.

Do not use public internet exposure.
Do not keep `--insecure` for the persistent service.
Use SSH tunnel only as a fallback if Desktop has trouble with Tailscale/DNS-rebinding checks.

## Acceptance criteria

1. Dashboard runs on jellyberry without `--insecure`.
2. Dashboard binds to a reachable Tailscale/LAN address, normally `0.0.0.0:9119`.
3. `/api/status` over Tailscale reports:
   ```json
   {
     "auth_required": true,
     "auth_providers": ["basic"]
   }
   ```
4. Hermes Desktop on Mac can connect to:
   ```text
   http://100.68.81.120:9119
   ```
   or MagicDNS if reliable:
   ```text
   http://jellyberry:9119
   ```
5. Desktop can open Chat and get a real Hermes session, not just dashboard status.
6. Dashboard survives logout/reboot using a user systemd service or equivalent managed process.
7. No API keys/secrets are printed in logs or summaries.

---

## Task 1: Add dashboard auth secrets

**Objective:** Configure username/password auth for non-loopback dashboard access.

**Files:**
- Modify: `/home/jellybot/.hermes/.env`

**Steps:**
1. Generate a 32-byte dashboard secret:
   ```bash
   openssl rand -base64 32
   ```
2. Add these keys to `/home/jellybot/.hermes/.env` without printing values:
   ```bash
   HERMES_DASHBOARD_BASIC_AUTH_USERNAME=<chosen-username>
   HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong-password>
   HERMES_DASHBOARD_BASIC_AUTH_SECRET=<openssl-output>
   ```
3. Verify presence only:
   ```bash
   python3 - <<'PY'
   from pathlib import Path
   text = Path('/home/jellybot/.hermes/.env').read_text()
   for key in [
       'HERMES_DASHBOARD_BASIC_AUTH_USERNAME',
       'HERMES_DASHBOARD_BASIC_AUTH_PASSWORD',
       'HERMES_DASHBOARD_BASIC_AUTH_SECRET',
   ]:
       print(key, 'present' if any(line.startswith(key + '=') and line.split('=',1)[1].strip() for line in text.splitlines()) else 'missing')
   PY
   ```

**Expected:** all three keys show `present`.

---

## Task 2: Replace the insecure dashboard process

**Objective:** Stop the current insecure dashboard and start it with auth enabled.

**Current bad shape:**
```text
hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build --insecure
```

**Target command:**
```bash
hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build
```

**Steps:**
1. Identify the current dashboard process:
   ```bash
   ps -eo pid,cmd | grep -E '[h]ermes.*dashboard'
   ```
2. Stop only that dashboard process.
3. Start the dashboard without `--insecure` and with `.env` loaded.
4. Confirm it is listening:
   ```bash
   curl -s http://127.0.0.1:9119/api/status
   ```

**Expected:** dashboard returns JSON; auth is enabled after Task 3.

---

## Task 3: Verify dashboard auth gate

**Objective:** Prove the dashboard is protected before trying Desktop.

**Commands:**
```bash
curl -s http://100.68.81.120:9119/api/status | jq '.auth_required, .auth_providers'
```

**Expected:**
```text
true
[
  "basic"
]
```

**Failure modes:**
- `auth_required: false`: dashboard is still insecure or auth env vars were not loaded.
- `auth_required: true` but providers missing `basic`: username/password env keys are missing or not loaded.
- Connection refused: dashboard is not running or Tailscale/firewall path is blocked.

---

## Task 4: Create persistent user service

**Objective:** Make the secure dashboard survive logout/reboot.

**File:**
- Create: `~/.config/systemd/user/hermes-dashboard.service`

**Service:**
```ini
[Unit]
Description=Hermes Dashboard for Hermes Desktop remote access
After=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.hermes/.env
ExecStart=%h/.hermes/hermes-agent/venv/bin/hermes dashboard --host 0.0.0.0 --port 9119 --no-open --skip-build
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

**Commands:**
```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-dashboard.service
systemctl --user status hermes-dashboard.service --no-pager
```

**If user services cannot access DBus from this agent session:** use the existing sudo-capable tmux shell or ask the user to run the systemctl commands directly.

---

## Task 5: Verify from the Mac

**Objective:** Confirm Desktop can use the real remote chat backend, not only `/api/status`.

**Desktop settings:**
- Remote URL:
  ```text
  http://100.68.81.120:9119
  ```
- Alternative if MagicDNS works:
  ```text
  http://jellyberry:9119
  ```
- Sign in with the dashboard username/password from Task 1.

**Verification:**
1. Desktop reports backend connected.
2. Open Chat.
3. Send a short message.
4. Confirm Hermes responds from jellyberry.
5. If Chat fails but status succeeds, inspect dashboard logs for WebSocket close code:
   - `4401`: WebSocket ticket/auth problem.
   - `4403`: Host/peer guard mismatch, usually URL/bind/Host-header issue.

---

## Task 6: Optional firewall/Tailscale tightening

**Objective:** Reduce exposure after basic Desktop connectivity is proven.

**Options:**
- Prefer Tailscale-only access if practical.
- If LAN access is not needed, block LAN TCP/9119 and allow only Tailscale interface/source.
- Keep dashboard auth even on Tailscale; Tailscale is not a substitute for dashboard auth.

**Verification:**
- Tailscale URL works from Mac.
- LAN URL is blocked if intentionally disabled.
- `/api/status` still reports auth required.

---

## SSH tunnel fallback

If direct Tailscale mode is problematic, use this safer fallback.

On jellyberry, run dashboard loopback-only:
```bash
hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
```

From Mac:
```bash
ssh -L 9119:127.0.0.1:9119 jellybot@jellyberry
```

Desktop URL:
```text
http://127.0.0.1:9119
```

This avoids remote dashboard exposure but requires the SSH tunnel to stay open.

---

## Implementation order

1. Choose username/password.
2. Add dashboard auth env vars.
3. Stop the insecure dashboard process.
4. Start dashboard without `--insecure`.
5. Verify `/api/status` shows `auth_required: true` and `basic` provider.
6. Connect Hermes Desktop from Mac over Tailscale.
7. Make the command persistent with a user systemd service.
8. Optionally tighten firewall to Tailscale-only.

## Rollback

If Desktop stops connecting:
1. Stop `hermes-dashboard.service`.
2. Temporarily start loopback dashboard:
   ```bash
   hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build
   ```
3. Use SSH tunnel from Mac.
4. Do not re-enable `--insecure` except as a brief local diagnostic with explicit approval.

## Open questions before execution

1. What username/password do you want for dashboard basic auth, or should I generate/store random credentials and report only where they are stored?
2. Do you want Tailscale-only access, or LAN + Tailscale initially?
3. Do you want me to implement this now using the current jellyberry host, or only keep this plan for later?
