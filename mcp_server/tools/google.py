"""
Google MCP tools — Gmail + Google Calendar.
Delegated OAuth, acts as owner. https://developers.google.com/identity/protocols/oauth2

gmail_* and gcal_* tools resolve to a google:* login.
RESTRICTED SCOPE: https://mail.google.com/ — an unverified OAuth app
issues refresh tokens that expire ~7 days. See README for mitigation.
"""
from pydantic import Field

from src.clients import get_client, resolve_account
from src.mcp_instance import DESTRUCTIVE, IDEMPOTENT, RO, WRITE, mcp
from src.models import BaseToolInput, DryRunInput


# ═══════════════════════════════════════════════════
# Gmail
# https://developers.google.com/gmail/api/reference/rest
# ═══════════════════════════════════════════════════

class GmailListMessagesInput(BaseToolInput):
    q: str = Field(default="", description="Gmail search query.", examples=["from:jane@example.com is:unread"])
    max_results: int = Field(default=20, ge=1, le=100)
    label_ids: list[str] | None = Field(default=None, description="Label IDs to filter by.")


@mcp.tool(annotations=RO, description="List Gmail messages (metadata only; use gmail_get_message for full content).")
async def gmail_list_messages(input: GmailListMessagesInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_messages(alias, q=input.q, max_results=input.max_results,
                                        label_ids=input.label_ids)
    return client.format(result, input.response_format)


class GmailGetMessageInput(BaseToolInput):
    message_id: str = Field(description="Message ID.", examples=["18c1f2e3..."])
    format: str = Field(default="full", description="Format: full | metadata | minimal | raw")


@mcp.tool(annotations=RO, description="Get a full Gmail message by ID.")
async def gmail_get_message(input: GmailGetMessageInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.get_message(input.message_id, alias, format=input.format)
    return client.format(result, input.response_format)


class GmailSendMessageInput(BaseToolInput, DryRunInput):
    to: str = Field(description="Recipient email.", examples=["jane@example.com"])
    subject: str = Field(description="Email subject.", examples=["Hello"])
    body: str = Field(description="Email body (plain text).", examples=["Hello world"])
    cc: str | None = Field(default=None, description="CC recipients (comma-separated).")
    bcc: str | None = Field(default=None, description="BCC recipients (comma-separated).")


@mcp.tool(annotations=WRITE, description="Send a Gmail message. Use dry_run=true to validate without sending.")
async def gmail_send_message(input: GmailSendMessageInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would send to {input.to}: {input.subject}"
    # Build RFC 822 message
    headers = f"To: {input.to}\r\nSubject: {input.subject}\r\n"
    if input.cc:
        headers += f"Cc: {input.cc}\r\n"
    if input.bcc:
        headers += f"Bcc: {input.bcc}\r\n"
    raw_rfc822 = f"{headers}Content-Type: text/plain; charset=utf-8\r\n\r\n{input.body}"
    result = await client.send_message(raw_rfc822, alias)
    return client.format(result, input.response_format)


class GmailListThreadsInput(BaseToolInput):
    q: str = Field(default="", description="Gmail search query.")
    max_results: int = Field(default=20, ge=1, le=100)


@mcp.tool(annotations=RO, description="List Gmail threads.")
async def gmail_list_threads(input: GmailListThreadsInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_threads(alias, q=input.q, max_results=input.max_results)
    return client.format(result, input.response_format)


class GmailGetThreadInput(BaseToolInput):
    thread_id: str = Field(description="Thread ID.", examples=["18c1f2e3..."])


@mcp.tool(annotations=RO, description="Get a Gmail thread by ID.")
async def gmail_get_thread(input: GmailGetThreadInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.get_thread(input.thread_id, alias)
    return client.format(result, input.response_format)


class GmailListLabelsInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="List Gmail labels.")
async def gmail_list_labels(input: GmailListLabelsInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_labels(alias)
    return client.format(result, input.response_format)


class GmailCreateLabelInput(BaseToolInput, DryRunInput):
    name: str = Field(description="Label name.", examples=["My Label"])


@mcp.tool(annotations=WRITE, description="Create a Gmail label.")
async def gmail_create_label(input: GmailCreateLabelInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create label: {input.name}"
    result = await client.create_label({"name": input.name}, alias)
    return client.format(result, input.response_format)


class GmailCreateDraftInput(BaseToolInput, DryRunInput):
    to: str = Field(description="Recipient email.", examples=["jane@example.com"])
    subject: str = Field(description="Draft subject.", examples=["Draft subject"])
    body: str = Field(description="Draft body (plain text).")


@mcp.tool(annotations=WRITE, description="Create a Gmail draft.")
async def gmail_create_draft(input: GmailCreateDraftInput) -> str:
    import base64
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create draft to {input.to}: {input.subject}"
    raw = f"To: {input.to}\r\nSubject: {input.subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{input.body}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    result = await client.create_draft({"message": {"raw": encoded}}, alias)
    return client.format(result, input.response_format)


class GmailListFiltersInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="List Gmail filters.")
async def gmail_list_filters(input: GmailListFiltersInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_filters(alias)
    return client.format(result, input.response_format)


class GmailGetVacationSettingsInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="Get Gmail vacation responder settings.")
async def gmail_get_vacation_settings(input: GmailGetVacationSettingsInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.get_vacation_settings(alias)
    return client.format(result, input.response_format)


# ═══════════════════════════════════════════════════
# Google Calendar
# https://developers.google.com/calendar/api/v3/reference
# ═══════════════════════════════════════════════════

class GcalListCalendarsInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="List Google Calendar calendars (calendarList).")
async def gcal_list_calendars(input: GcalListCalendarsInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_calendars(alias)
    return client.format(result, input.response_format)


class GcalListEventsInput(BaseToolInput):
    calendar_id: str = Field(default="primary", description="Calendar ID.", examples=["primary"])
    max_results: int = Field(default=25, ge=1, le=250)
    time_min: str | None = Field(default=None, description="ISO 8601 lower bound.", examples=["2025-07-15T00:00:00Z"])
    time_max: str | None = Field(default=None, description="ISO 8601 upper bound.")
    q: str | None = Field(default=None, description="Full-text search query.")


@mcp.tool(annotations=RO, description="List events on a Google Calendar.")
async def gcal_list_events(input: GcalListEventsInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.list_events(input.calendar_id, alias, max_results=input.max_results,
                                      time_min=input.time_min, time_max=input.time_max, q=input.q)
    return client.format(result, input.response_format)


class GcalGetEventInput(BaseToolInput):
    calendar_id: str = Field(default="primary", description="Calendar ID.")
    event_id: str = Field(description="Event ID.", examples=["abc123"])


@mcp.tool(annotations=RO, description="Get a Google Calendar event by ID.")
async def gcal_get_event(input: GcalGetEventInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.get_event(input.calendar_id, input.event_id, alias)
    return client.format(result, input.response_format)


class GcalCreateEventInput(BaseToolInput, DryRunInput):
    calendar_id: str = Field(default="primary", description="Calendar ID.")
    summary: str = Field(description="Event title.", examples=["Team Meeting"])
    start: str = Field(description="ISO 8601 start datetime.", examples=["2025-07-15T10:00:00"])
    end: str = Field(description="ISO 8601 end datetime.", examples=["2025-07-15T11:00:00"])
    timezone: str = Field(default="UTC", description="Timezone.")
    description: str | None = Field(default=None, description="Event description.")
    attendees: list[str] | None = Field(default=None, description="Attendee emails.")
    location: str | None = Field(default=None, description="Event location.")


@mcp.tool(annotations=WRITE, description="Create a Google Calendar event. Use dry_run=true to validate.")
async def gcal_create_event(input: GcalCreateEventInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create event '{input.summary}' on {input.start}"
    event: dict = {
        "summary": input.summary,
        "start": {"dateTime": input.start, "timeZone": input.timezone},
        "end": {"dateTime": input.end, "timeZone": input.timezone},
    }
    if input.description:
        event["description"] = input.description
    if input.attendees:
        event["attendees"] = [{"email": a} for a in input.attendees]
    if input.location:
        event["location"] = input.location
    result = await client.create_event(input.calendar_id, event, alias)
    return client.format(result, input.response_format)


class GcalUpdateEventInput(BaseToolInput, DryRunInput):
    calendar_id: str = Field(default="primary")
    event_id: str = Field(description="Event ID to update.")
    event: dict = Field(description="Fields to update.", examples=[{"summary": "Updated Title"}])


@mcp.tool(annotations=IDEMPOTENT, description="Update a Google Calendar event (PATCH).")
async def gcal_update_event(input: GcalUpdateEventInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would update event {input.event_id}: {input.event}"
    result = await client.update_event(input.calendar_id, input.event_id, input.event, alias)
    return client.format(result, input.response_format)


class GcalDeleteEventInput(BaseToolInput, DryRunInput):
    calendar_id: str = Field(default="primary")
    event_id: str = Field(description="Event ID to delete.")
    confirm: bool = Field(default=False, description="Must be true to execute.")


@mcp.tool(annotations=DESTRUCTIVE, description="Delete a Google Calendar event. DESTRUCTIVE — requires confirm=true.")
async def gcal_delete_event(input: GcalDeleteEventInput) -> str:
    if not input.confirm:
        return "Deletion requires confirm=true."
    client = get_client("google")
    alias = resolve_account("google", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would delete event {input.event_id} from {input.calendar_id}"
    result = await client.delete_event(input.calendar_id, input.event_id, alias)
    return client.format(result or {"status": "deleted"}, input.response_format)


class GcalGetFreeBusyInput(BaseToolInput):
    time_min: str = Field(description="ISO 8601 start.", examples=["2025-07-15T00:00:00Z"])
    time_max: str = Field(description="ISO 8601 end.", examples=["2025-07-15T23:59:59Z"])
    calendar_ids: list[str] | None = Field(default=None, description="Calendar IDs (primary if None).")


@mcp.tool(annotations=RO, description="Get free/busy information from Google Calendar.")
async def gcal_get_free_busy(input: GcalGetFreeBusyInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.get_free_busy(input.time_min, input.time_max, alias, input.calendar_ids)
    return client.format(result, input.response_format)


# ── Escape-hatch ──

class GoogleRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PUT", "DELETE"])
    path: str = Field(description="API path after base URL.", examples=["/users/me/messages"])
    service: str = Field(default="gmail", description="API service: 'gmail' or 'calendar'.")
    query: dict | None = Field(default=None, description="Query parameters.")
    body: dict | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call ANY Google API endpoint (Gmail or Calendar). Escape-hatch for full API coverage.")
async def google_request(input: GoogleRequestInput) -> str:
    client = get_client("google")
    alias = resolve_account("google", input.account)
    result = await client.generic_request(input.method, input.path, alias,
                                          query=input.query, body=input.body, service=input.service)
    return client.format(result, input.response_format)