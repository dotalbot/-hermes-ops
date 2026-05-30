# Gmail Reusable Prompt Patterns

**Status:** Final — read-only search patterns, no auto-sending
**Date:** 2026-05-30
**Auth:** Google Workspace OAuth2 — `~/.hermes/google_token.json`
**Task:** t_49146f04 — Document 3 reusable Gmail workflow prompt patterns
**Related:** `docs/runbooks/gmail-workflows.md` (operational runbook with setup, test results, and send-safety checklist)

---

## Overview

These patterns move beyond ad-hoc Gmail search. Each is a reusable prompt template with a defined purpose, required inputs, expected output, and search strategy. **None of these patterns send or modify email** — they read only, present results as text, and leave drafts/compose actions to explicit user approval.

For auth setup, token refresh, and the full send-safety checklist, see the companion runbook: `docs/runbooks/gmail-workflows.md`.

Core tools (alias `GAPI`):
```bash
GAPI="${HOME}/.hermes/hermes-agent/venv/bin/python3 ${HOME}/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
```

---

## Pattern 1: Topic Email Summary & Action Items

### Purpose
Find recent emails about a specific topic and extract action items, decisions, and follow-ups.

### Required Inputs
- Topic keywords (one or more, OR-joined)
- Time range (default: 14 days)
- Optional: sender filter (e.g. `from:github.com`)

### Example User Prompt
> "Search my email for messages about 'home-network' or 'Prometheus' from the last 14 days. Summarise any action items, decisions, or follow-ups mentioned."

### Gmail Search Strategy
```
(home-network OR Prometheus OR Alertmanager) newer_than:14d
```
Adjust operators (`OR` / `AND`) and time window as needed. Appending `-label:CATEGORY_PROMOTIONS -label:CATEGORY_SOCIAL` filters noise.

### Expected Output Format
```
Topic: Prometheus/home-network monitoring
- [2026-05-28] Alertmanager Discord webhook config — action item: verify webhook URL
- [2026-05-25] Prometheus rule review — no action needed
- [2026-05-22] Home Network dashboard query help — resolved
```

### Failure / Ambiguity Handling
- **Too many results** — narrow by date (`newer_than:7d`) or add a sender filter (`from:notifications@github.com`).
- **Too few results** — broaden keywords, try synonyms, or extend the time range.
- **No structured action items** — report "no explicit action items found" and summarise email snippets anyway.

### Send-Safety Warning
**This pattern reads email only. It must never send replies, forward messages, or compose drafts automatically. All results are presented as plain text for human review.**

---

## Pattern 2: Draft Reply Without Sending

### Purpose
Locate an email, understand the context, and draft a suggested reply for the user to review and approve before sending.

### Required Inputs
- Email search criteria (topic, sender, date)
- Optional: tone/style guidance for the draft

### Example User Prompt
> "Find the latest email from Alice about the deployment schedule. Read it, understand the context, and draft a reply that confirms Wednesday works for the rollback window. Show me the draft and do not send it."

### Gmail Search Strategy
First, locate the email:
```
(from:alice@ OR "deployment schedule") newer_than:7d
```
Then fetch the full message body with `$GAPI gmail get MESSAGE_ID`. Parse context from the snippet and body.

### Expected Output Format
```
Subject: Re: Deployment schedule (March 3-5)
To: Alice <alice@example.com>
Draft:
---
Hi Alice,

Wednesday, March 5 works for the rollback window on my side. Let me know
if you need me to coordinate with the infra team beforehand.

Best,
Chuck
---
Status: DRAFT — Not sent. Review and confirm before sending.
```

### Failure / Ambiguity Handling
- **Email not found** — widen the search, try sender variants or date range.
- **Thread with multiple messages** — default to the latest or ask which message to reply to.
- **Ambiguous context** — state what you inferred and flag uncertainty in the draft.

### Send-Safety Warning
**This pattern must never send email automatically. It produces a text draft only. The draft must be clearly labelled "DRAFT — Not sent" and requires explicit user confirmation before any send operation.**

---

## Pattern 3: Invoice / Subscription / Renewal Search

### Purpose
Find invoices, receipts, payment confirmations, and subscription renewal notices in email.

### Required Inputs
- Time range (default: 30 days)
- Optional: vendor, amount range, or subject keyword

### Example User Prompt
> "Find any invoices or receipts in my email from the last month. List them with date, sender, and amount if visible."

### Gmail Search Strategy
```
subject:(invoice OR receipt OR payment OR "your receipt" OR subscription) newer_than:30d
```
For recurring bills: add `from:domain` or common billing addresses. For renewal notices: `subject:(renewal OR "auto-renew" OR "your subscription")`.

### Expected Output Format
```
Invoices & Receipts (last 30 days):
- [2026-05-15] Adobe Creative Cloud — receipt (noreply@adobe.com)
- [2026-05-01] DigitalOcean — invoice #INV123 (billing@digitalocean.com)
  Amount: $24.00
- [2026-04-28] GitHub Copilot — receipt (receipts@github.com)
```

### Failure / Ambiguity Handling
- **No results** — use broader subject terms (`billing`, `order confirmation`, `thank you for your purchase`).
- **Too many results** — filter by common billing domains (`from:paypal@`, `from:billing@`, etc.).
- **Amount not extracted** — show date/sender/subject only; do not follow links or open attachments.

### Send-Safety Warning
**This pattern searches and reads only. It must never open attachments, follow payment links, or interact with billing portals. All results are presented as plain text for human review.**

---

## Pattern 4: Meeting / Action Digest

### Purpose
Compile a digest of recent meeting-related emails, calendar invites, and time-sensitive action items.

### Required Inputs
- Time range (default: 7 days)
- Optional: project or team filter

### Example User Prompt
> "Check my email for meeting notes, calendar invites, or 'action required' messages from this week. Give me a digest of what needs my attention."

### Gmail Search Strategy
```
(meeting OR "action required" OR "next steps" OR calendar OR "follow-up") newer_than:7d
```
Exclude noise: `-label:CATEGORY_PROMOTIONS -label:CATEGORY_SOCIAL`. For calendar invites specifically: `filename:ics` or `has:attachment`.

### Expected Output Format
```
Meeting Digest (last 7 days):
- [2026-05-29] Architecture review — follow-up: approve ADR document (from: tech-lead@company.com)
- [2026-05-28] Sprint planning — action: update task estimates
- [2026-05-26] 1:1 with manager — no action needed
```

### Failure / Ambiguity Handling
- **Noisy results** — exclude promotions/social labels. Use `is:important` or `from:` to filter by known contacts.
- **No meeting-related results** — search for calendar invites separately with `filename:ics` or `subject:(invitation OR cancelled OR updated)`.
- **Action items ambiguous** — present what you found and mark each as "action item ✓" vs "FYI only" based on subject keywords.

### Send-Safety Warning
**This pattern reads email only. It must never reply to threads, send follow-up reminders, or compose messages automatically. All results are presented as plain text for human review.**

---

## Using These Patterns

1. **Choose a pattern** based on your goal (topic summary, draft reply, financial search, or meeting digest).
2. **Fill in the inputs** (keywords, time range, sender filters).
3. **Run the Gmail search** using the alias or direct API call.
4. **Review the output** — all patterns return text-only results for human judgment.
5. **For drafts** (Pattern 2): review the generated draft, then explicitly instruct the tool to send it. No email is sent automatically.

## Safety Rules (Always Apply)

| Rule | Description |
|------|-------------|
| No auto-send | Every send-capable operation requires explicit user confirmation. Draft = never sent. |
| No attachment execution | Never open or execute attachments automatically. |
| No account changes | Never mark as spam, archive in bulk, or change filters. |
| Plain text output | Present financial/actionable info as text; do not follow links. |
