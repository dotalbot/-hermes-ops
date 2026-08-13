# Reviewer capability fixture

This fixture is the deterministic/offline conformance source for the certified warm path. It is intentionally not a product specification and cannot authorize a semantic verdict.

Offline tests must prove:

- exact full lowercase base/specification/target refs only;
- explicit target-tree binding;
- approved specification bytes and SHA-256 derive from one bounded snapshot;
- source/profile/MCP evidence digests reject tamper;
- capability evidence rejects replay across attempt, commit, tree, specification path/digest, or controller bytes;
- semantic review verdicts are never cached in capability evidence;
- timing intervals are non-overlapping and total exactly;
- review and acceptance binders reject non-terminal cards, findings, failed axes/checks, and substituted IDs.

The live canary uses a real immutable product target and restricted MCP checks. It is separately timed and remains non-semantic until a fresh independent reviewer returns its own exact-target verdict.
