# Skill Control Plane — Phase 2 minimum

This directory is the Git-backed authority for the isolated JellySSH pilot. It does not mutate global skills or make a project routable by itself.

## Layout

- `catalog.yaml` — release, capability-pack, and project index.
- `releases/core-development/0.1.0/` — immutable snapshots of the eight Phase 1-approved shared workflow skills.
- `packs/` — optional database/data and Flutter/mobile capability packs.
- `projects/jellyssh/project.yaml` — schema-validated project declaration with exact artifact hashes.
- `projects/jellyssh/runtime.yaml` — observed setup state and explicit blockers.
- `projects/jellyssh/overlays/` — uniquely named, project-specific overlays held by the Phase 2 control-plane authority; mirroring them into the JellySSH repository is deferred until repository governance and authentication are authorized.
- `schemas/` — authoritative project and runtime-evidence schemas used by the CLI.
- `scripts/projectctl.py` — read-only scan, verify, audit, plan, dry-run initialization, and status projection.
- `scripts/review_boundary.py` and `scripts/jellyssh_review_mcp.py` — six-tool, read-only adapter over SSH to the isolated Jellybase review checkout; tracked blobs are read from the exact commit, not the worktree, and Git refs are limited to the exact target plus the transient controller-supplied base (target-only for interactive profile use).
- `scripts/reviewctl.py` — validates one immutable profile/host/model/commit snapshot, pins controller and project-authority hashes, loads and hash-verifies an execution-compatible specialist procedure into the model prompt, launches MCP from a private verified snapshot, calls exactly six MCP tools, semantically revalidates metadata/checks before and after collection, materializes regular blobs independently of `.gitattributes`, and runs fixed Flutter checks in a digest-pinned `--network none`, read-only-root Docker sandbox with no host home/runtime sockets. Final/code-quality review uses the no-tools `jellyssh-controller-evidence-review` adapter over the controller-collected diff/checks; exact no-fallback DeepSeek final-review and Gemini conditional mobile-UX routes return bounded JSON and never write board state.
- `tests/` — standard-library unit and negative-boundary tests.
- `generated/` — derived status only; manifests remain authoritative.

## Commands

```bash
python3 skills-control-plane/scripts/projectctl.py scan
python3 skills-control-plane/scripts/projectctl.py plan
python3 skills-control-plane/scripts/projectctl.py project-init --dry-run
python3 skills-control-plane/scripts/projectctl.py verify
python3 skills-control-plane/scripts/projectctl.py audit
python3 skills-control-plane/scripts/projectctl.py status \
  --output skills-control-plane/generated/jellyssh-status.md
python3 skills-control-plane/scripts/projectctl.py status --format json \
  --output skills-control-plane/generated/jellyssh-status.json
python3 -m unittest discover -s skills-control-plane/tests -v
/home/jellybot/.hermes/hermes-agent/venv/bin/python \
  skills-control-plane/scripts/reviewctl.py REVIEW_SPEC.json
```

`project-init` deliberately has no apply mode in this Phase 2 minimum. Calling it without `--dry-run` fails closed. Runtime side effects are performed only after the plan is reviewed and are then reconciled back into `runtime.yaml` with evidence. `plan`, dry-run initialization, and `status` return exit `1` while required live gates remain blocked; status files are still generated so the blockers are inspectable.

## Hash contract

Skill-package hashes use:

```text
sha256(sorted(u64be(path-byte-length) + UTF-8-relative-path
              + u64be(content-byte-length) + content-bytes))
```

This is the Phase 1 inventory algorithm, retained for compatibility with the
accepted upstream skill hashes. Symlinks and non-regular files are rejected.

Release/pack aggregate hashes use canonical JSON over artifact name, version, and sorted skill name/hash pairs. A second descriptor hash covers governance metadata, provenance, ownership, compatibility, approvals, state, and the aggregate hash. The catalogue and project manifest pin both values. Content or metadata drift therefore requires a new reviewed version; changing an immutable directory in place is not an update path.

## Routing state

The Phase 2 schemas do not contain a routable runtime state, and semantic validation rejects `project.state=routable`; `promotion.candidate_routable` must remain false. A later phase would require a separately reviewed schema/manifest change after every live gate passes. Phase 2 creates no development card.
