---
name: jellyssh-controller-evidence-review
description: Review JellySSH from bounded controller evidence with no model tools.
version: 0.1.0
metadata:
  owner: jellyssh-project
  authority: control-plane-phase2
  execution_mode: controller-precollected-evidence
---

# JellySSH controller evidence review

Use only the trusted controller instructions and bounded evidence packet supplied in the prompt. Do not request tools, repository discovery, subagents, edits, or additional context.

## Required method

1. Confirm the evidence identifies the exact base commit, target commit, requested path prefixes, reviewer root, remote host identity, and expected clean `main` checkout.
2. Confirm all six MCP tools have read-only annotations and the controller supplied the complete base-to-target diff.
3. Treat every controller check with `ok=false` as a blocking condition. Never infer PASS from process exit status alone.
4. Review the supplied diff along two independent axes:
   - standards/code quality: correctness, deterministic behavior, cleanup, errors, tests, maintainability, and documentation accuracy;
   - specification compliance: requested behavior, scope, authority, routing, evidence, and explicit non-goals.
5. Use only exact tracked regular-file paths present under the requested prefixes for findings. A requested directory prefix such as `app` is not itself a valid finding path. If the evidence does not identify an exact file for a failed check, omit the finding and record the failure only in `checks`. Do not cite virtual controller labels as files.
6. Return only the controller-required JSON contract. Report `PASS` only when evidence is complete, all mandatory checks pass, and no blocking/high finding remains; otherwise report `BLOCK`.

## Boundary

The controller, not the model, performs repository access and fixed checks. This procedure is deliberately executable without model tools or delegation.
