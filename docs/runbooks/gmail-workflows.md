# Gmail Workflow Runbook

**Status:** Final — read-only workflows, approval-gated sending  
**Date:** 2026-05-30  
**Auth:** Google Workspace OAuth2 — `AUTHENTICATED` (token at `~/.hermes/google_token.json`)  
**Task:** t_dc60e372 — Finalize Gmail workflow runbook  
**Related:** t_49146f04 (prompt patterns), t_6e42ae25 (send safeguards), t_66afb058 (tested on demand)

> **Standalone prompt patterns reference:** `docs/runbooks/gmail-prompt-patterns.md`  
> Each pattern there includes a full send-safety warning and is kept separately for easy reuse without the full runbook context.

---

## Quick Start

```bash
# Shorthand
GAPI="${HOME}/.hermes/hermes-agent/venv/bin/python3 ${HOME}/.hermes/skills/productivity/google-workspace/scripts/google_api.py"

# Check auth
$GAPI gmail search "is:unread" --max 3

# Read a specific message
$GAPI gmail get MESSAGE_ID
```

Prerequisites: Google Workspace OAuth2 setup (run `setup.py` if `--check` fails).

---

## Send-Safety Reference

**Rule: Never send email automatically. All draft/reply/send operations require explicit user confirmation.**

The canonical approval-gated email sending safeguards are defined in:
`docs/specs/approval-gated-email-safeguards.md`

### Quick checklist (see spec for full detail)

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

**Approval gate:** If any check is unchecked, do NOT send. Present the draft for review or abort.

---

## Reusable Prompt Patterns

### Pattern 1: Project/Topic Email Summary

**Purpose:** Find recent emails about a specific topic and summarise action items.

**Input:** Topic keywords, time range, optional sender filter.

**Example prompt:**
> "Search my email for messages about 'home-network' or 'Prometheus' from the last 14 days. Summarise any action items, decisions, or follow-ups mentioned."

**Gmail search:** `(home-network OR Prometheus OR Alertmanager) newer_than:14d`

**Expected output:**
```
Topic: Prometheus/home-network monitoring
- [2026-05-28] Alertmanager Discord webhook config — action item: verify webhook URL
- [2026-05-25] Prometheus rule review — no action needed
- [2026-05-22] Home Network dashboard query help — resolved
```

**Failure handling:** If search returns too many results, narrow by date or sender. If too few, broaden keywords.

**Send-safety warning:** This pattern reads email only. It must never send replies, forward messages, or compose drafts automatically. All results are presented as plain text for human review. No email is ever sent or modified.

---

### Pattern 2: Invoice/Subscription/Renewal Search

**Purpose:** Find invoices, receipts, payment confirmations, and subscription renewals.

**Input:** Time range (default 30 days), optional vendor or amount filter.

**Example prompt:**
> "Find any invoices or receipts in my email from the last month. List them with date, sender, and amount if visible."

**Gmail search:** `subject:(invoice OR receipt OR payment OR "your receipt" OR subscription) newer_than:30d`

**Expected output:**
```
Invoices (last 30 days):
- [2026-05-15] Adobe Creative Cloud — receipt (noreply@adobe.com)
- [2026-05-01] DigitalOcean — invoice #INV123 (billing@digitalocean.com)
- [2026-04-28] GitHub Copilot — receipt (receipts@github.com)
```

**Failure handling:** Use broader subject terms (`billing`, `order confirmation`, `thanks for your purchase`). If too many results, filter by `from:` common billing domains.

**Send-safety warning:** This pattern searches and reads only. It must never open attachments, follow payment links, or interact with billing portals automatically. All results are presented as plain text for human review. No purchase, unsubscribe, or confirm action is ever taken.

---

### Pattern 3: Meeting/Action Digest

**Purpose:** Compile a digest of recent meeting-related emails, calendar invites, and time-sensitive action items.

**Input:** Time range (default 7 days), optional project/team filter.

**Example prompt:**
> "Check my email for meeting notes, calendar invites, or 'action required' messages from this week. Give me a digest of what needs my attention."

**Gmail search:** `(meeting OR "action required" OR "next steps" OR calendar OR "follow-up") newer_than:7d`

**Expected output:**
```
Meeting Digest (last 7 days):
- [2026-05-29] Architecture review — follow-up: approve ADR document (from: tech-lead@company.com)
- [2026-05-28] Sprint planning — action: update task estimates
- [2026-05-26] 1:1 with manager — no action needed
```

**Failure handling:** If results are noisy, exclude newsletters and promotions by filtering labels: `-label:CATEGORY_PROMOTIONS -label:CATEGORY_SOCIAL`. Use `has:attachment` to find meeting notes documents.

**Send-safety warning:** This pattern reads email only. It must never reply to threads, send meeting reminders, or compose follow-up messages automatically. All results are presented as plain text for human review.

---

### Pattern 4: Project-Related Email Clustering (Bonus)

**Purpose:** Group recent emails by project or repository to get a per-project overview.

**Input:** Project keywords, time range.

**Example prompt:**
> "Cluster my email from the last 7 days by project: portfolio-intel, home-network, and logk. Count emails per project and list the most recent one for each."

**Gmail search (per project):**
```
(portfolio-intel OR "portfolio intel") newer_than:7d
(home-network OR jellyberry OR jellyhome OR jellybase) newer_than:7d AND from:notifications@github.com
logk newer_than:7d
```

**Expected output:**
```
portfolio-intel: 3 emails (latest: PR #12 review request)
home-network:    8 emails (latest: Docker config comment)
logk:            1 email  (latest: issue #5 update)
```

**Failure handling:** Adjust project-specific keywords if a project uses different names in notifications.

**Send-safety warning:** This pattern searches and reads email only. It must never send notifications, create labels, archive threads, or modify mailbox state automatically. All results are presented as plain text for human review.

---

## Test Results: On-Demand Workflow

**Tested:** 2026-05-30  
**Pattern used:** Pattern 3 — Invoice/Subscription/Renewal Search (full workflow: search + individual message reads)

**Exact user prompt used:**
> "Find any invoices or receipts in my email from the last 2 months. List them with date, sender, amount, and what they're for."

**Commands executed:**
```bash
# Step 1: Broad invoice/subscription search
$GAPI gmail search "subject:(invoice OR receipt OR payment OR \"your receipt\" OR subscription OR billing) newer_than:60d" --max 10

# Step 2: Read full bodies for amount extraction
$GAPI gmail get 19e57115a970abe6   # LogicServers invoice
$GAPI gmail get 19e4db2d00447787   # Apple credit note
$GAPI gmail get 19e4d03e7dbd6797   # Atlassian Confluence warning
```

**Extracted results:**

| Date | Sender | Subject | Amount | Notes |
|------|--------|---------|--------|-------|
| 2026-05-24 | LogicServers | Customer Invoice | £7.92 | Minecraft server (Iron, £6.60 + VAT). Due 3 Jun, auto-pay Visa-9032 |
| 2026-05-22 | Apple | Your invoice from Apple | -£19.99 (credit) | Blink Shell Blink+ Annual cancellation refund. Visa-9032 |
| 2026-05-22 | Atlassian | [Action Required] Jump back in | N/A | Confluence subscription deactivating 2026-06-05 due to inactivity |
| 2026-05-28 | OpenAI (incident.io) | Business plan subscription checkout issues | N/A | Status incident (resolved) |
| 2026-05-29 | Daily Maverick | This is not a subscription. | N/A | Promotional email (matched keyword, not a real invoice) |

**Verified:**
- Full JSON output format: `[{id, threadId, from, to, subject, date, snippet, labels, body}]`
- Auth token refresh works automatically (no credential prompts)
- Full message body extraction works for both plain-text (LogicServers) and HTML-rich (Apple) emails
- No emails were sent, modified, or marked read during testing
- Send-safety checklist (spec §4) satisfied: no draft created, no reply composed, no auto-send

**Refinements found:**
1. Subject-only search misses receipts with subjects like "Customer Invoice" or "Credit note" — the base pattern helped here, but adding `newer_than:Nd` with a broader query improves recall.
2. Promotional/fundraising emails with "subscription" in subject are false positives — add `-label:CATEGORY_PROMOTIONS -label:CATEGORY_SOCIAL` to filter noise.
3. Amount extraction requires get-by-id (step 2) since the snippet often truncates financial data — this is correct per the pattern but should be explicit in step documentation.

---

## Runbook Maintenance

- Run `$GSETUP --check` periodically (auto-refresh handles token expiry)
- If auth fails: `$GSETUP --revoke` then re-run setup steps 3-5
- New workflow patterns should be documented here and cross-referenced with Kanban tasks
- Send-safety checklist in `docs/specs/approval-gated-email-safeguards.md` applies to every new workflow — do not skip it
