# Read-Only Evaluation Questions

Ten realistic, multi-tool, verifiable questions. All read-only (no mutations).
Each requires the MCP server to be seeded with OAuth tokens and reachable.

---

## 1. Email triage across two providers

**Question:** "What are the 5 most recent unread emails in my Outlook inbox and
the 5 most recent unread emails in my Gmail? List subject, sender, and date
for each, grouped by provider."

**Tools:** `outlook_list_messages` (folder_id=None, limit=5) → `gmail_list_messages`
(q="is:unread", max_results=5) → `gmail_get_message` (for each, to get sender/subject)

**Verification:** Both providers return results. Dates are within expected range.
Senders and subjects match actual emails.

---

## 2. Calendar conflict check

**Question:** "Do I have any overlapping meetings on my calendar between 9 AM and
5 PM Eastern tomorrow? Check both my Outlook calendar and my Google Calendar.
List any conflicts with title, start time, and end time."

**Tools:** `outlook_list_events` (start=tomorrow_9am_ET, end=tomorrow_5pm_ET) →
`gcal_list_events` (calendar_id=primary, time_min=tomorrow_9am_ET, time_max=tomorrow_5pm_ET)

**Verification:** Both calendars return events. Overlaps are correctly identified
(events where start < other.end and end > other.start).

---

## 3. Customer financial snapshot

**Question:** "Find the customer 'Acme Corp' in QuickBooks. How many unpaid
invoices do they have, and what is the total outstanding balance? Also check
HubSpot — is there a matching company, and what is the deal stage of any open
deals associated with it?"

**Tools:** `qbo_query` (entity=Customer, where="CompanyName like '%Acme%'") →
`qbo_query` (entity=Invoice, where="CustomerRef = '<id>' AND Balance > '0'") →
`hubspot_search_objects` (object_type=companies, query="Acme Corp") →
`hubspot_list_associations` (object_type=companies, to_object_type=deals)

**Verification:** Customer found in QBO. Invoice balances summed correctly.
HubSpot company found (or not). Deal stages match actual CRM data.

---

## 4. SharePoint document inventory

**Question:** "List all SharePoint sites I have access to. For the site named
'Team Hub', list all document libraries and count the files in the root of each
library. Report any libraries with more than 50 files."

**Tools:** `sharepoint_list_sites` → find site by display name →
`sharepoint_list_drives` (site_id=<id>) → for each drive:
`sharepoint_list_drive_items` (drive_id=<id>, limit=100)

**Verification:** Sites listed correctly. Drive items counted. Libraries with
>50 files correctly identified.

---

## 5. Cross-provider contact reconciliation

**Question:** "I have a contact 'Sarah Chen' in HubSpot. Check if she's also a
customer in QuickBooks and if her email appears in my Gmail sent items from the
last 30 days. Summarize all three data points."

**Tools:** `hubspot_search_objects` (object_type=contacts, query="Sarah Chen") →
extract email → `qbo_query` (entity=Customer, where="PrimaryEmailAddr = '<email>'
OR DisplayName like '%Sarah Chen%'") → `gmail_list_messages`
(q="from:sarah@example.com newer_than:30d" or q="to:sarah@example.com newer_than:30d")

**Verification:** HubSpot contact found. QBO customer match (or no match).
Gmail sent items found (or none). Email addresses match across providers.

---

## 6. Workforce + billing cross-reference

**Question:** "How many active users do I have in Connecteam? List their names.
Then check QuickBooks — are any of them also customers with outstanding balances?
Report any matches."

**Tools:** `connecteam_list_users` (limit=200) → for each user, check if they
appear in QBO → `qbo_query` (entity=Customer, where="DisplayName like '%<name>%'")
→ filter for Balance > 0

**Verification:** Connecteam user count matches. QBO customer matches correctly
identified. Outstanding balances reported accurately.

---

## 7. Meeting preparation brief

**Question:** "I have a meeting tomorrow at 2 PM with 'jane@contoso.com'.
Pull together a brief: what is the subject of that Outlook calendar event?
Also search my Gmail for any emails from jane@contoso.com in the last 14 days —
what were the subjects? And is there a matching contact in HubSpot with any
notes or recent activity?"

**Tools:** `outlook_list_events` (start=tomorrow_start, end=tomorrow_end) →
filter for events with attendee jane@contoso.com → `gmail_list_messages`
(q="from:jane@contoso.com newer_than:14d") → `hubspot_search_objects`
(object_type=contacts, query="jane@contoso.com")

**Verification:** Outlook event found with the correct attendee. Gmail emails
listed. HubSpot contact found (or not) with notes/activity.

---

## 8. Task and time clock audit

**Question:** "List all open tasks in Connecteam and the 10 most recent time
clock entries. Are any tasks assigned to users who clocked in today? Cross-reference
and report."

**Tools:** `connecteam_list_tasks` (limit=100) → `connecteam_list_time_clock`
(limit=10) → match user IDs between tasks and time clock entries

**Verification:** Tasks listed. Time clock entries listed. User ID cross-reference
correctly identifies any overlaps.

---

## 9. Pipeline health dashboard

**Question:** "List all deal pipelines in HubSpot. For the 'default' pipeline,
how many deals are in each stage? What is the total value of deals in each stage?
Also, for any deals in the 'closed won' stage, check if there is a matching
invoice in QuickBooks."

**Tools:** `hubspot_list_pipelines` (object_type=deals) → for default pipeline:
`hubspot_search_objects` (object_type=deals, filters by pipeline) → group by
stage → sum deal amounts → for closed won deals: `qbo_query`
(entity=Invoice, where="CustomerRef = '<customer_id>'")

**Verification:** Pipelines listed. Deal counts per stage correct. Total values
summed accurately. QBO invoice matches found (or not).

---

## 10. Full connectivity audit

**Question:** "Run a connectivity check against all providers. Which ones are
healthy? For any that fail, what is the error? Also list the total number of
labels in Gmail and the total number of mail folders in Outlook."

**Tools:** `check_provider_connectivity` (providers=all) →
`gmail_list_labels` → `outlook_list_mail_folders`

**Verification:** All five providers checked. Status (ok/error) reported for each.
Label count and folder count match actual values. Error messages are actionable
(if any).