# Non-routable skill candidates

Each candidate is materialized under `releases/<name>/<version>/` or `packs/<name>/<version>/` by an approval-bound candidate plan. Candidate bytes are immutable, are not referenced by the active catalogue, and cannot be promoted in place. Promotion copies the exact candidate tree into the corresponding immutable release/pack path only after impact, compatibility and canary evidence gates pass.
