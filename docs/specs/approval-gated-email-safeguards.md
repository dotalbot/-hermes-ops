# Approval-Gated Email Sending Safeguards

**Status:** Adopted
**Date:** 2026-05-30
**Scope:** All Gmail workflows driven through the Hermes Google Workspace API adapter (google_api.py), the Himalaya CLI, or any future email-sending capability.
**Task:** t_6e42ae25
**Related:** t_dc60e372 (Gmail workflow runbook), t_66afb058 (tested on demand)

---

## 1. Golden Rule

**Never send email automatically. No agent, script, or automation may call a send/deliver action without an explicit human "yes" in the same session.**

This applies to:
- Sending a new email
- Replying to an email
- Forwarding an email
- Approving a draft for delivery
- Any API call with `send`, `deliver`, `transmit`, or equivalent semantics

---

## 2. Draft-Only Protocol

Every generated or derived email must remain a **draft** (unsent) until the human explicitly approves sending. The protocol has two phases.

### Phase A: Generation

When an agent produces email content (summary, reply draft, new message), the output must be:

1. **Stored only in-memory or as an unsent draft object.** Never pass the generated content directly to a send-capable endpoint.
2. **Labelled as `DRAFT — Review before sending`** in the preview context so it's visually unmistakable from a sent or ready-to-send message.
3. **Presented with recipient, subject, and full body visible** to the user in a single review block.

Example presentation format:

```
━━━ DRAFT — Review before sending ━━━
To:      user@example.com
Subject: Re: Weekly sync notes
Body:
  Thanks for the update. I'll review the
  ADR by Thursday and follow up on Slack.

━━━ End draft — awaiting approval ━━━
```

### Phase B: Approval Gate

Before any send action may proceed, ALL of the following must be true:

| # | Condition | Met? |
|---|-----------|------|
| 1 | Recipient address(es) shown to user for confirmation | ☐ |
| 2 | Subject line shown to user | ☐ |
| 3 | Full body content shown to user | ☐ |
| 4 | Content is labelled `DRAFT — Review before sending` | ☐ |
| 5 | User has explicitly said "yes", "send it", or equivalent affirmative confirmation | ☐ |
| 6 | Not sending to a mailing list, group alias, or distribution list (confirmed by user) | ☐ |
| 7 | If replying: original message context/snippet is included in the draft preview | ☐ |
| 8 | If forwarding: forward targets are visible and confirmed | ☐ |

If **any** condition is unmet, the agent must **not** call a send action — instead, it must present the draft for further review or abort.

---

## 3. Technical Safeguards

### 3.1 API-Level Guards

Any Hermes tool or script that can send email MUST:

- **Default to draft-only.** The script/tool must not expose a `send` action as the default mode. Drafting must be the primary, documented workflow.
- **Require a `--confirm` flag or explicit parameter** to execute a send. The flag must be impossible to set by accident (no `-y` / `--yes` shorthand, must be the full word or an unambiguous long flag).
- **Log every send attempt** to stdout before executing: recipient, subject, body preview (first 200 chars), and timestamp. The human must see this log line before confirming.

### 3.2 Pipeline Isolation

- **No send-capable pipeline may be triggered by:**
  - A cron job or scheduled script
  - An inbound webhook or notification
  - A subagent or delegated task (subagents cannot call send actions)
  - A Kanban task completion handler
  - A chat gateway command without explicit user context
- **Send-capable logic must live in an interactive session only**, where the user has issued a direct request and is present to confirm.

### 3.3 Retry Safety

If a send action fails (network error, SMTP rejection, auth timeout), the agent must:

1. Report the failure to the user with the error details.
2. **Not retry** the send automatically.
3. Present the unsent draft for the user to decide: retry, modify, or abandon.

This prevents double-sends (the email goes through on a retry even though the first attempt also succeeded after the timeout).

---

## 4. Reusable Checklist Block

Copy the following block verbatim into any Gmail workflow runbook, prompt pattern, or task spec that could generate or send an email:

```markdown
### Send-Safety Checklist

**Rule: Never send email automatically. All draft/reply/send operations require explicit user confirmation.**

| # | Check | Pass |
|---|-------|------|
| 1 | Recipient address(es) shown to user for confirmation | ☐ |
| 2 | Subject line shown to user | ☐ |
| 3 | Full body content shown to user | ☐ |
| 4 | Content labelled `DRAFT — Review before sending` | ☐ |
| 5 | User has explicitly confirmed "yes, send this" | ☐ |
| 6 | Not sending to a mailing list or group alias by accident | ☐ |
| 7 | If replying: original message context/snippet included | ☐ |
| 8 | If forwarding: forward targets visible and confirmed | ☐ |

**Approval gate:** If any check is ☐ (unchecked), do NOT send. Present the draft for review or abort.
```

---

## 5. Non-Compliance Example

The following pattern is **forbidden**:

```
❌ User: "Reply to John's email about the meeting"
❌ Agent: [calls gmail send directly with reply text]
❌ Agent: "Sent!"
```

Correct pattern:

```
✅ User: "Reply to John's email about the meeting"
✅ Agent: [reads original email, composes draft]

  ━━━ DRAFT — Review before sending ━━━
  To:      john@example.com
  Subject: Re: Meeting tomorrow
  Body:
    Hi John, tomorrow at 2 PM works for me.
    See you then.
  ━━━ End draft ━━━

✅ Agent: "Shall I send this reply? Type 'yes' to send, or ask me to revise."
✅ User: "yes"
✅ Agent: [calls gmail send] "Sent!"
```

---

## References

- Gmail Workflow Runbook: `docs/runbooks/gmail-workflows.md`
- Google Workspace API scripts: `~/.hermes/skills/productivity/google-workspace/`
- Himlaya CLI: `skill:himalaya`
- Parent design review: `docs/reviews/guarded-approval-design-release-readiness.md`
