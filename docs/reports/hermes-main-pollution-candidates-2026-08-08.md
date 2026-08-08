# Hindsight `hermes-main` pollution candidate report

Date: 2026-08-08
Mode: read-only candidate generation
Bank: `hermes-main`
Total memories fetched: 5386

## Backup

Raw memory-list backup was written locally with mode `0600` because memory text may contain sensitive operational context.

- Backup JSONL: `/home/jellybot/projects/hindsight-cleanup/hermes-main-memory-list-20260808T003100Z.jsonl`
- SHA256: `323344ccc542d09f06013af0ea2d62f16ce87543c5e5e121f846c4a24d9a1592`
- Candidate JSON: `/home/jellybot/projects/hindsight-cleanup/hermes-main-cleanup-candidates-20260808T003100Z.json`

No Hindsight memories were deleted or edited by this report.

## Candidate counts

- Home-network/domain candidates currently in `hermes-main`: 1025
- Stale `0.6.2` current-state candidates: 11
- Historical `0.6.2` upgrade/background facts to preserve or review: 13
- Perishable operational-state candidates: 412
- Entries retained from Desktop cleanup session `20260808_010333_2258fd`: 33
- Normalized duplicate clusters: 547

## Home-network/domain candidates

These are candidates for review and possible copy/migration to `home-network-main`; do not blindly delete them because some may also be Hermes-operating context.

1. `44245b7c-503c-41a5-9372-734e358951e2` `world` 2026-08-08T00:28:05.868492+00:00 — To view Hermes dashboard credentials safely on Jellyberry, use the command `grep '^HERMES_DASHBOARD_BASIC_AUTH_' ~/.hermes/.env`.
2. `92920b3f-5427-4962-853f-d4dce53df62a` `observation` 2026-08-08T00:26:43.356556+00:00 — Addresses to access Hermes dashboard: Local on Jellyberry: http://127.0.0.1:9119, LAN: http://192.168.1.159:9119, Tailscale: http://100.68.81.120:9119.
3. `74830e8e-bc0d-4d20-88c1-ae087c2793c7` `world` 2026-08-08T00:24:40.804067+00:00 — Suggested probes for maintenance include current Hindsight version, home-network source path, jellybase_hermes memory bank, routing banks, current LogK deployment target, and current Home Assistant Meross architecture.
4. `bae5f4c3-8dec-451b-8ce3-95a621dd3a35` `observation` 2026-08-07T21:20:28.061676+00:00 — Suggested probes for maintenance include current Hindsight version, home-network source path, jellybase_hermes memory bank, routing banks, current LogK deployment target, and current Home Assistant Meross architecture.
5. `2e950b7f-7430-4c25-8643-5115f49a5c3c` `world` 2026-08-08T00:24:40.774067+00:00 — Recommended banks include `global-dominic`, `hermes-main`, `home-network-main`, `jellybase-worker-main`, and various project banks like `logk-main` and `jellyfood-main`. | To structure operational facts and memory effect…
6. `062df592-bdea-44bd-a5c3-6130dac03bfb` `observation` 2026-08-07T21:20:28.031676+00:00 — Recommended final architecture includes banks: `global-dominic`, `hermes-main`, `home-network-main`, `jellybase-worker-main`, and various project banks like `logk-main` and `jellyfood-main` to structure operational facts…
7. `96624a92-79e3-4161-848e-4ecb720a7ba0` `world` 2026-08-08T00:24:40.734067+00:00 — User is advised to set `auto_retain: false` initially for `jellybase_hermes` to avoid retaining transient noise from implementation workers. | When: 2026-08-08 | Involving: user | Implementation workers produce lots of t…
8. `cecff33c-ad0b-4d0f-ae14-0e1dfb8279f2` `observation` 2026-08-07T21:20:27.991676+00:00 — User is recommended to set `auto_retain: false` initially for `jellybase_hermes` to avoid retaining transient noise from implementation workers, including tests running, blockers, local branch state, and intermediate fil…
9. `62e0416d-581d-425b-8d66-0ec4cdc64af6` `world` 2026-08-08T00:24:40.724067+00:00 — User should use the bank `jellybase-worker-main` for short term, not `hermes-main`, as `jellybase_hermes` is a remote implementation worker that should remember reusable Jellybase worker patterns. | When: 2026-08-08 | In…
10. `7e1d0543-bef4-4e55-a4be-98c5dca5e972` `world` 2026-08-08T00:24:40.714067+00:00 — User is recommended to add the config file at `/home/jellybot/.hermes/profiles/jellybase_hermes/hindsight/config.json`. | When: 2026-08-08 | Involving: user
11. `184cefe8-76c8-44ea-a685-80bb0ab30e9f` `observation` 2026-08-07T21:20:27.951676+00:00 — User needs to configure `jellybase_hermes` due to a config bug where the profile states Hindsight provider, but it is unavailable and lacks profile-local Hindsight config. User is recommended to add the config file at `/…
12. `c43b9723-990a-4559-9370-768398a16a33` `world` 2026-08-08T00:24:40.704067+00:00 — User needs to configure `jellybase_hermes` due to a config bug where the profile states Hindsight provider, which is unavailable, and lacks profile-local Hindsight config. | When: 2026-08-08 | Involving: user

## Stale `0.6.2` current-state candidates

These are the highest-priority cleanup candidates because Hindsight is now verified at `0.9.0`.

1. `e43953e2-b3db-4018-a0bb-fc0504317f5e` `world` 2026-08-08T00:24:40.684067+00:00 — User identified that current-state facts stating version 0.6.2 of Hindsight are problematic and should be removed or neutralized. | Involving: user | To ensure accurate representation of the current version of Hindsight.
2. `781b786c-ac87-47d6-a5b3-f82853674ada` `observation` 2026-08-07T21:20:27.931676+00:00 — User identified that current-state facts stating version 0.6.2 of Hindsight are problematic and should be removed or neutralized to ensure accurate representation of the current version of Hindsight.
3. `65c1a016-f23e-4116-977e-78848d487927` `observation` 2026-08-07T21:06:04.959471+00:00 — Current bank evidence shows that 'hermes-main' has 5179 facts and returns stale 'Hindsight 0.6.2' facts alongside new '0.9.0' facts, while 'home-network-main' has only 36 facts.
4. `aef6b237-439d-4c9c-a32e-8ee46bd20d4e` `world` 2026-08-07T21:06:04.959471+00:00 — Current bank evidence shows that 'hermes-main' has 5179 facts and returns stale 'Hindsight 0.6.2' facts alongside new '0.9.0' facts, while 'home-network-main' has only 36 facts.
5. `6cf3819d-c58b-42a7-9a6d-6ef5ed9a3271` `experience` 2026-08-07T20:16:39.226430+00:00 — User was informed that the latest release of Hindsight is v0.9.0, published on August 7, 2026. | When: 2026-08-07T20:08:02.905878+00:00 | Involving: user, assistant | User's current version is 0.6.2, indicating they are …
6. `a5eead66-8d35-4732-bfa4-a3f8f19b6648` `experience` 2026-08-07T20:16:39.226423+00:00 — User asked for the latest version of Hindsight, and Assistant informed that the latest release is v0.9.0, noting that the current version in use is 0.6.2. | When: 2026-08-07T20:08:02.905878+00:00 | Involving: user, herme…
7. `abbeefbe-cf82-40b0-bd30-003f33b689ea` `observation` 2026-08-07T20:16:39.216423+00:00 — The current version of Hindsight is 0.6.2.
8. `67ba2311-8aaa-46db-87fc-34a1529475c7` `experience` 2026-08-07T20:16:39.216430+00:00 — User asked how to determine the version of Hindsight currently running, and it was revealed that it is version 0.6.2. | When: 2026-08-07T20:06:03.318005+00:00 | Involving: user, assistant
9. `b6de92f1-41c2-4b6a-9163-be526f6dc458` `experience` 2026-08-07T20:16:39.216423+00:00 — User asked how to determine the version of Hindsight currently running, and Assistant provided methods to check, confirming it is running version 0.6.2. | When: 2026-08-07T20:06:03.318005+00:00 | Involving: user, hermes-…
10. `6612f33c-9328-44f9-ae75-dce743bffc3b` `observation` 2026-06-13T17:47:15.886247+00:00 — Hindsight v0.6.2 runs on jellyhome with API available at http://192.168.1.1:18888 on LAN and http://100.90.175.59:18888 on Tailscale.
11. `c709f911-8515-454f-80ee-cdde738c6223` `experience`  — Hindsight v0.6.2 runs on jellyhome with API available at http://192.168.1.1:18888 on LAN and http://100.90.175.59:18888 on Tailscale.

## Historical `0.6.2` facts

These can remain if framed as upgrade history rather than current state.

1. `3a6291c7-c6fa-4415-b20e-5130ee504e63` `world` 2026-08-07T21:06:04.809471+00:00 — Hindsight version was updated from 0.6.2 to 0.9.0. | When: 2026-08-07
2. `0fa7d9fc-d45b-4572-ae65-4092cf664163` `world` 2026-08-07T21:06:04.739471+00:00 — Major changes from version 0.6.2 to 0.9.0 include new pluggable memories storage backend, client-managed knowledge pages, and improved memory curation.
3. `480bf52c-250b-4f6f-ae1a-bd1f920c3d7f` `observation` 2026-08-07T20:26:15.465856+00:00 — Major changes from version 0.6.2 to 0.9.0 include new pluggable memories storage backend, client-managed knowledge pages, and improved memory curation.
4. `86eee821-cbe0-4147-ad72-1f78f3aa0c4f` `world` 2026-08-07T20:26:15.049739+00:00 — Hindsight upgraded from version 0.6.2 to 0.9.0 with runtime host jellyhome and image ghcr.io/vectorize-io/hindsight:0.9.0. | When: 2026-08-07T20:26:15.039739+00:00
5. `d463b560-9aee-4edc-b8a6-19ec5f537232` `observation` 2026-08-07T20:26:15.049739+00:00 — Hindsight upgraded from version 0.6.2 to 0.9.0 with runtime host jellyhome and image ghcr.io/vectorize-io/hindsight:0.9.0.
6. `746e6ab0-f1aa-49b6-a408-8d6e6acb1c17` `observation` 2026-08-07T20:52:26.657348+00:00 — `hermes-main` has 5179 facts and returns stale `Hindsight 0.6.2` facts alongside new `0.9.0` facts, while `home-network-main` has only 36 facts, indicating that too much operational/project memory has probably been retai…
7. `f3049d01-973f-4174-b540-2ea10495e0d0` `world` 2026-08-07T20:52:26.657348+00:00 — `hermes-main` has 5179 facts and returns stale `Hindsight 0.6.2` facts alongside new `0.9.0` facts, while `home-network-main` has only 36 facts. | Too much operational/project memory has probably been retained into `herm…
8. `98b426b1-02ec-41dc-831e-862c3300fe83` `observation` 2026-08-07T20:26:15.475856+00:00 — Jellyhome Hindsight version updated to 0.9.0 and local memory entry replaced from 0.6.2 to 0.9.0.
9. `d98de558-d1b8-4751-9935-541b87d3a18d` `world` 2026-08-07T20:26:15.475856+00:00 — Jellyhome Hindsight version updated to 0.9.0 and local memory entry replaced from 0.6.2 to 0.9.0. | When: 2026-08-07
10. `31f99086-f1d2-43ce-be5e-c7959b0de183` `world` 2026-08-07T20:26:15.465856+00:00 — Major changes from version 0.6.2 to 0.9.0 include new pluggable memories storage backend, client-managed knowledge pages, and improved recall/retain quality.
11. `597df4b9-072e-4233-a071-df42e058a2b7` `world` 2026-08-07T20:26:15.049739+00:00 — Hindsight upgraded from version 0.6.2 to 0.9.0 with runtime host jellyhome and image ghcr.io/vectorize-io/hindsight:0.9.0. | When: 2026-08-07T20:26:15.039739+00:00
12. `36c145ec-ce5a-4bea-ac52-96fc03de6c1e` `observation` 2026-08-07T00:00:00+00:00 — Hindsight central memory on jellyhome was upgraded from version 0.6.2 to 0.9.0 via the home-network repo; the source-of-truth commit for the upgrade is dc6c569 with the message 'chore: upgrade hindsight to 0.9.0'; the ru…

## Perishable operational-state candidates

These are examples of facts that may age badly: PIDs, `/tmp` paths, one-off task IDs, current board counts, one-off health checks, and similar status snapshots.

1. `16673a15-de56-476a-8661-4f6e4d90f1bd` `world` 2026-08-08T00:28:05.838492+00:00; reasons=running_counts — Hermes web/dashboard interface is running on multiple addresses including local, LAN, and Tailscale. | When: 2026-08-08T00:26:42.864381+00:00 | Involving: assistant | To provide access information for the Hermes web inte…
2. `f07940ac-19ae-492b-a7b8-22a630aaba99` `world` 2026-08-08T00:24:40.614067+00:00; reasons=running_counts — Assistant confirmed that cleaning up pollution is possible but should be done as a controlled memory-hygiene job, not by bulk-deleting. | When: 2026-08-07T21:20:27.417887+00:00 | Involving: Assistant
3. `521d74b0-8f69-439c-bf95-862e8bb04391` `observation` 2026-08-08T00:12:03.469779+00:00; reasons=commit_sha — Non-git project/activity folders moved to '/home/jellybot/projects/' including 'ab-900-prep', 'caminao-prep', 'cert-study-hub', 'hindsight-cleanup', 'home-network.kanban-homepage-20260522-223209', 'image-pastebin', 'ms-1…
4. `1d2c416c-87eb-42c7-b9a2-5f36ee707515` `world` 2026-08-08T00:12:03.469779+00:00; reasons=commit_sha — Non-git project/activity folders moved to '/home/jellybot/projects/' including 'ab-900-prep', 'caminao-prep', 'cert-study-hub', 'hindsight-cleanup', 'home-network.kanban-homepage-20260522-223209', 'image-pastebin', 'ms-1…
5. `30f937bd-01f9-4746-9b15-e9ad23b56afc` `world` 2026-08-07T21:06:05.009471+00:00; reasons=running_counts — Profile memory config changes do not reliably apply to already-running sessions, so fresh sessions or gateway restarts are needed. | When: 2026-08-07 | Involving: user | To ensure proper application of configuration chan…
6. `90e22405-fef5-4a4c-8ee8-c1dfe92e4dc5` `world` 2026-08-07T21:06:04.949471+00:00; reasons=one_off_health — Do not retain transient states like 'review currently running', PR/commit/task transient state, temporary TODOs, one-off command outputs, stale 'current version' facts unless updating/removing the old one, and noisy raw …
7. `e5ccf977-4313-4a56-91f2-ce25d18b728b` `observation` 2026-08-07T20:52:26.647348+00:00; reasons=one_off_health — Do not retain transient states like 'review currently running', PR/commit/task transient state, temporary TODOs, one-off command outputs, stale 'current version' facts unless updating/removing the old one, and noisy raw …
8. `ea78aca8-68a0-41fb-8737-c8474594a3e1` `world` 2026-08-07T20:52:26.647348+00:00; reasons=one_off_health — Do not retain transient states like 'review currently running', PR/commit/task transient state, temporary TODOs, one-off command outputs, stale 'current version' facts unless updating/removing the old one, and noisy raw …
9. `36c145ec-ce5a-4bea-ac52-96fc03de6c1e` `observation` 2026-08-07T00:00:00+00:00; reasons=commit_sha — Hindsight central memory on jellyhome was upgraded from version 0.6.2 to 0.9.0 via the home-network repo; the source-of-truth commit for the upgrade is dc6c569 with the message 'chore: upgrade hindsight to 0.9.0'; the ru…
10. `77d3e3ed-a0a4-4275-8fcf-d9a8db773e7a` `world` 2026-08-07T20:24:54.063698+00:00; reasons=commit_sha — Source-of-truth commit for the upgrade is dc6c569 with the message 'chore: upgrade hindsight to 0.9.0'.
11. `67ba2311-8aaa-46db-87fc-34a1529475c7` `experience` 2026-08-07T20:16:39.216430+00:00; reasons=running_counts,one_off_health — User asked how to determine the version of Hindsight currently running, and it was revealed that it is version 0.6.2. | When: 2026-08-07T20:06:03.318005+00:00 | Involving: user, assistant
12. `b6de92f1-41c2-4b6a-9163-be526f6dc458` `experience` 2026-08-07T20:16:39.216423+00:00; reasons=running_counts,one_off_health — User asked how to determine the version of Hindsight currently running, and Assistant provided methods to check, confirming it is running version 0.6.2. | When: 2026-08-07T20:06:03.318005+00:00 | Involving: user, hermes-…

## Desktop cleanup session entries

The Desktop session did write new memory into `hermes-main`. Some of this may be durable path-layout context; some may be too operational. Review before deletion.

1. `054eaf30-e835-4299-93f7-d0187ba11883` `world` 2026-08-08T00:28:05.878492+00:00 — The file `/home/jellybot/.local/share/hermes/secrets/opencode-serve.env` contains OpenCode serve credentials, not the Hermes dashboard login.
2. `8e474cb6-9781-40db-85dc-8ccc317436b7` `observation` 2026-08-08T00:25:20.028879+00:00 — The file `/home/jellybot/.local/share/hermes/secrets/opencode-serve.env` contains OpenCode serve credentials, not the Hermes dashboard login.
3. `44245b7c-503c-41a5-9372-734e358951e2` `world` 2026-08-08T00:28:05.868492+00:00 — To view Hermes dashboard credentials safely on Jellyberry, use the command `grep '^HERMES_DASHBOARD_BASIC_AUTH_' ~/.hermes/.env`.
4. `ce7bff7f-ef73-46d9-8a35-901e62e602b6` `world` 2026-08-08T00:28:05.858492+00:00 — The systemd service loads the credentials file from `/home/jellybot/.config/systemd/user/hermes-dashboard.service`.
5. `c308a78b-15a7-474e-af06-94900b84b25f` `world` 2026-08-08T00:28:05.848492+00:00 — Hermes dashboard credentials are located in `/home/jellybot/.hermes/.env` with relevant keys: HERMES_DASHBOARD_BASIC_AUTH_USERNAME, HERMES_DASHBOARD_BASIC_AUTH_PASSWORD, HERMES_DASHBOARD_BASIC_AUTH_SECRET. | Involving: u…
6. `c1af3267-9559-48b5-9169-f87cd6d5619b` `observation` 2026-08-08T00:12:05.307678+00:00 — Hermes dashboard credentials are located in `/home/jellybot/.hermes/.env` with relevant keys: HERMES_DASHBOARD_BASIC_AUTH_USERNAME, HERMES_DASHBOARD_BASIC_AUTH_PASSWORD, HERMES_DASHBOARD_BASIC_AUTH_SECRET.
7. `16673a15-de56-476a-8661-4f6e4d90f1bd` `world` 2026-08-08T00:28:05.838492+00:00 — Hermes web/dashboard interface is running on multiple addresses including local, LAN, and Tailscale. | When: 2026-08-08T00:26:42.864381+00:00 | Involving: assistant | To provide access information for the Hermes web inte…
8. `88e7b697-9fc2-41ea-9887-95d312488b95` `observation` 2026-08-08T00:26:43.336556+00:00 — Hermes web/dashboard interface is running on multiple addresses including local, LAN, and Tailscale.
9. `fbf1ff67-3b15-4f79-9b4f-2fce7d2fb2a2` `world` 2026-08-08T00:25:19.608245+00:00 — Assistant created a migration/reference document in the hermes-ops docs directory and updated several other documents. | When: 2026-08-08T00:25:19.598245+00:00 | Involving: assistant | To provide a reference for future o…
10. `3168b8df-2597-462c-b548-c40967d957a8` `observation` 2026-08-08T00:25:20.038879+00:00 — Assistant created a migration/reference document in the hermes-ops docs directory and updated several other documents, recording conventions, folder structures, workspace mappings, updates, verification results, and futu…
11. `bbe19aea-49e4-41f9-8057-34b46914a8b7` `world` 2026-08-08T00:28:05.818492+00:00 — User requested a summary of actions taken in the hermes-ops docs directory for future reference. | When: 2026-08-08T00:25:19.598245+00:00 | Involving: user
12. `92920b3f-5427-4962-853f-d4dce53df62a` `observation` 2026-08-08T00:26:43.356556+00:00 — Addresses to access Hermes dashboard: Local on Jellyberry: http://127.0.0.1:9119, LAN: http://192.168.1.159:9119, Tailscale: http://100.68.81.120:9119.

## Top duplicate clusters

1. 16 copies — sample: `dd82c5b3-0f0b-4c22-8462-594ef38dce50` — User completed an async delegation batch with one subagent, which finished running in parallel and provided consolidated results. | When: 2026-08-06T22:31:23 | Involving: user
2. 6 copies — sample: `f5d44080-9cb9-418b-abbc-35f6d2250e1a` — User completed an async delegation batch with one subagent, which finished running in parallel and provided consolidated results.
3. 5 copies — sample: `12445e9c-f034-4a9c-b11f-0297412d74e5` — User completed an async delegation batch with one subagent dispatched, which finished running in parallel. | When: 2026-08-05T18:21:49 | Involving: user
4. 5 copies — sample: `a3d73e36-ccd4-4ada-8743-a193a9aee7fa` — Comma-separated list of collectors to use defaults to all if not specified.
5. 4 copies — sample: `1fed888d-2dff-4d3e-814e-b72232cf4733` — Before sharing a Project path, check the execution environment of the target profile, which may use either Jellyberry’s local backend or an SSH backend.
6. 4 copies — sample: `7ccb4954-3d3a-4736-9f2d-15634c815f20` — A worker can manage a remote machine through SSH commands, an SSH terminal backend, remote APIs, Home Assistant, Git, messaging, and purpose-built MCP tools.
7. 4 copies — sample: `94d89b0e-b213-418a-899a-ae3cfbfd11b8` — User completed an async delegation batch with 2 subagents dispatched, which finished running in parallel. | When: 2026-08-06T22:38:21 | Involving: user
8. 4 copies — sample: `6ec20166-51ce-406e-9bf0-16d32d955b47` — User completed an async delegation batch with 1 subagent, which finished running in parallel and provided consolidated results. | When: 2026-08-06T12:19:10 | Involving: user

## Recommended next action

Do not delete anything yet.

1. Review `/home/jellybot/projects/hindsight-cleanup/hermes-main-cleanup-candidates-20260808T003100Z.json`.
2. Select a very small pilot batch:
   - stale `0.6.2` current-state observations first;
   - obvious exact duplicates second;
   - home-network facts only after checking whether they should be retained into `home-network-main`.
3. For every selected deletion/edit, record memory ID and reason.
4. Verify recall before and after:
   - `current Hindsight version`
   - `home-network source path`
   - `jellybase_hermes memory bank`
   - `how should Hermes route Hindsight banks`
