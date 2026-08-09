---
name: jellyssh-ssh-security-review
description: Use for JellySSH credential, host-key, forwarding, process, network, and sensitive-log changes.
version: 0.1.0
metadata:
  hermes:
    ownership: project-overlay
    project: jellyssh
    approval_state: phase2-isolated-test
---

# JellySSH SSH security review

Read-only project review. Treat JellySSH repository authority and the exact reviewed commit as inputs; never modify the implementation checkout.

Hard checks:

1. Host-key verification fails closed and trust-state transitions are explicit.
2. Credentials, passphrases, private keys, tokens, and decrypted material do not enter logs, prompts, fixtures, snapshots, or version control.
3. Authentication-agent and forwarding behavior is opt-in, scoped, and visible.
4. External process invocation uses fixed argument boundaries; no shell interpolation of untrusted data.
5. Network forwarding and URI parsing validate destinations and privilege-sensitive ports.
6. Cancellation, timeout, cleanup, reconnect, and partial-failure paths preserve session integrity.
7. Security-critical behavior has negative tests, not only happy-path tests.

Return trigger, exact commit, evidence, severity-ordered findings, unresolved hard stops, and `PASS` or `BLOCK`.
