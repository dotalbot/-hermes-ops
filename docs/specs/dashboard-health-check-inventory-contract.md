# Dashboard health-check inventory contract

## Purpose

Define the deterministic source-of-truth input for dashboard/Homepage quality checks. The contract is intentionally reviewable in git and separates actionable failures from acceptable skips so a no-agent watchdog can stay quiet unless a supported required check fails.

Machine-readable inventory: `config/dashboard-inventory.json`

## Sources represented

- Homepage services: `/home/jellybot/dev_projects/home-network/docker/appdata/homepage/services.yaml`
- Homepage bookmarks: `/home/jellybot/dev_projects/home-network/docker/appdata/homepage/bookmarks.yaml`
- Hermes dashboard runtime: `/home/jellybot/.config/systemd/user/hermes-dashboard.service`, checked through port `9119`
- Portfolio Mission Control runtime: `/home/jellybot/dev_projects/portfolio-intel/mission-control-v2`, checked through port `8787`

## Network context

The current checker context is the trusted home LAN/Tailnet, with jellyberry as the primary local checker host for Hermes dashboard and Portfolio Mission Control local routes.

Known host context used by the inventory:

- jellyhome: `192.168.1.1`, Tailscale `100.90.175.59`
- jellybase: `192.168.1.2`, Tailscale `100.125.86.118`
- jellyberry: `192.168.1.159`
- LAN assumption: `192.168.1.0/24` is reachable from the checker for Homepage links that use LAN IPs

A future checker may run somewhere else, but it must either preserve these reachability assumptions or mark entries that cannot be reached from its context as acceptable skips.

## Entry schema

Each `entries[]` object uses these fields:

- `id`: stable lowercase identifier for diff-friendly references.
- `display_name`: human label from the dashboard, Homepage service, or bookmark.
- `source`: one of `hermes-dashboard-runtime`, `mission-control-v2-runtime`, `homepage-service`, `homepage-service-related-route`, or `homepage-bookmark`.
- `source_file`: path to the source-of-truth file or runtime component used to derive the entry.
- `category`: dashboard/Homepage grouping.
- `url`: the URL or route the checker should use when the entry is supported.
- `homepage_href`: original Homepage `href` when the entry comes from Homepage.
- `homepage_site_monitor`: original Homepage `siteMonitor` when it differs from `href`; omitted when identical to `homepage_href` to keep diffs compact.
- `service`: normalized endpoint details: `scheme`, `host`, `port`, and `path`; dashboard-local entries also name `runtime_host`.
- `expected_http`: expected status behavior for HTTP-family entries. Supported values include exact `status`, simple `status_class` values such as `2xx`, `allowed_status_classes`, `text_contains`, and endpoint-specific notes. If an expression is richer than the current watchdog supports, the checker must either implement it explicitly or skip/report it as unsupported rather than guessing.
- `assets`: optional bundle/asset metadata, currently used for Hermes dashboard plugins. Unauthenticated plugin asset `401` responses are acceptable when the manifest itself is reachable.
- `required`: boolean failure policy. `true` means a supported failed check is actionable. `false` means the entry is inventory-only or optional unless promoted later.
- `check_mode`: execution class. Current values:
  - `http`: safe for a normal LAN HTTP watchdog.
  - `external_http`: optional public-internet dependency; include in manual/audit mode, not noisy no-agent LAN alerting.
  - `skip`: inventory only until a protocol-specific checker exists or the endpoint is promoted.
- `acceptable_skip_reason`: required when `required` is false or `check_mode` is `skip`; explains why absence/failure should not alert.
- `network_assumptions`: concise reachability/trust-boundary notes.

## Failure semantics

- `required: true` and supported `check_mode`: failed probe is an actionable dashboard quality failure.
- `required: false`: failed probe or omitted probe is an acceptable skip; it may appear in a digest but should not page/chat-alert.
- `check_mode: skip`: do not probe with the HTTP watchdog. Examples: MQTT, PostgreSQL, SSH, or host-local `127.0.0.1` endpoints where localhost would refer to the checker rather than the service host.
- `check_mode: external_http`: keep out of quiet no-agent runs unless the operator explicitly wants internet/GitHub link audits.
- Unsupported `expected_http` expressions must be reported as unsupported/skip in digest mode, not silently converted into a weaker check.

## Current coverage

The inventory currently contains:

- Hermes dashboard status API and plugin manifest, including bundled plugin asset metadata for `hermes-achievements` and `kanban`.
- Portfolio Mission Control root page and JSON data routes: `/`, `/data/hermes.json`, `/data/roadmap.json`.
- Hindsight UI and API routes: `:9999/` and `:18888/openapi.json`.
- All current Homepage service entries from the home-network source config.
- All current Homepage operation bookmarks.
- Explicit skip records for non-HTTP and host-local entries so they are visible without creating false alarms.

## Relationship to `config/dashboard-links.json`

`config/dashboard-links.json` remains the small executable config consumed by the current `scripts/dashboard_link_check.py` watchdog.

`config/dashboard-inventory.json` is the broader contract that future checker work should consume or compile down into executable checks. That future conversion should preserve the failure semantics above instead of treating every dashboard link as equally required.

## Acceptance criteria mapping

- Deterministic: no generated timestamps; stable ids; stable source paths.
- Reviewable in git: JSON inventory plus this spec live in the repo.
- Covers current Homepage/dashboard entries: entries are derived from the current Homepage services/bookmarks and the live Hermes/Mission Control routes already used by the watchdog.
- Distinguishes failures from skips: `required`, `check_mode`, and `acceptable_skip_reason` make the policy explicit.
