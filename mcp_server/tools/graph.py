"""
Microsoft Graph MCP tools — SharePoint + Outlook mail + Outlook calendar.
Delegated user OAuth (Entra app registration), acts as owner.
https://learn.microsoft.com/en-us/graph/api/overview

sharepoint_* and outlook_* tools resolve to a microsoft:* login.
"""
from pydantic import Field

from src.clients import get_client, resolve_account
from src.mcp_instance import DESTRUCTIVE, IDEMPOTENT, RO, WRITE, mcp
from src.models import BaseToolInput, DryRunInput


# ═══════════════════════════════════════════════════
# SharePoint
# https://learn.microsoft.com/en-us/graph/api/resources/sharepoint
# ═══════════════════════════════════════════════════

class SharepointListSitesInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List SharePoint sites.")
async def sharepoint_list_sites(input: SharepointListSitesInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_sites(alias, limit=input.limit)
    return client.format(result, input.response_format)


class SharepointGetSiteInput(BaseToolInput):
    site_id: str = Field(description="Site ID or hostname:path.", examples=["root"])


@mcp.tool(annotations=RO, description="Get a SharePoint site by ID.")
async def sharepoint_get_site(input: SharepointGetSiteInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.get_site(input.site_id, alias)
    return client.format(result, input.response_format)


class SharepointListDrivesInput(BaseToolInput):
    site_id: str = Field(description="Site ID.", examples=["root"])
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List document libraries (drives) in a SharePoint site.")
async def sharepoint_list_drives(input: SharepointListDrivesInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_drives(input.site_id, alias, limit=input.limit)
    return client.format(result, input.response_format)


class SharepointListDriveItemsInput(BaseToolInput):
    drive_id: str = Field(description="Drive ID.", examples=["b!abc123"])
    item_id: str | None = Field(default=None, description="Parent item ID (root if None).")
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List items in a drive folder (root if item_id is None).")
async def sharepoint_list_drive_items(input: SharepointListDriveItemsInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_drive_items(input.drive_id, alias, input.item_id, limit=input.limit)
    return client.format(result, input.response_format)


class SharepointUploadFileInput(BaseToolInput, DryRunInput):
    drive_id: str = Field(description="Drive ID.")
    parent_item_id: str = Field(description="Parent folder item ID.")
    filename: str = Field(description="Filename for the uploaded file.", examples=["report.pdf"])
    content_b64: str = Field(description="File content as base64-encoded string.")


@mcp.tool(annotations=WRITE, description="Upload a file to a SharePoint drive folder (small files < 4MB).")
async def sharepoint_upload_file(input: SharepointUploadFileInput) -> str:
    import base64
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would upload {input.filename} to drive {input.drive_id}/{input.parent_item_id}"
    content = base64.b64decode(input.content_b64)
    result = await client.upload_file(input.drive_id, input.parent_item_id, input.filename, content, alias)
    return client.format(result, input.response_format)


class SharepointDownloadFileInput(BaseToolInput):
    drive_id: str = Field(description="Drive ID.")
    item_id: str = Field(description="File item ID to download.")


@mcp.tool(annotations=RO, description="Download a file from SharePoint (returns base64-encoded content).")
async def sharepoint_download_file(input: SharepointDownloadFileInput) -> str:
    import base64
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    content = await client.download_file(input.drive_id, input.item_id, alias)
    return base64.b64encode(content).decode()


class SharepointListListsInput(BaseToolInput):
    site_id: str = Field(description="Site ID.", examples=["root"])
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List SharePoint lists in a site.")
async def sharepoint_list_lists(input: SharepointListListsInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_lists(input.site_id, alias, limit=input.limit)
    return client.format(result, input.response_format)


class SharepointListListItemsInput(BaseToolInput):
    site_id: str = Field(description="Site ID.")
    list_id: str = Field(description="List ID.")
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List items in a SharePoint list.")
async def sharepoint_list_list_items(input: SharepointListListItemsInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_list_items(input.site_id, input.list_id, alias, limit=input.limit)
    return client.format(result, input.response_format)


# ═══════════════════════════════════════════════════
# Outlook Mail
# https://learn.microsoft.com/en-us/graph/api/resources/message
# ═══════════════════════════════════════════════════

class OutlookListMessagesInput(BaseToolInput):
    folder_id: str | None = Field(default=None, description="Mail folder ID (inbox if None).")
    limit: int = Field(default=25, ge=1, le=50)
    select: list[str] | None = Field(default=None, description="Fields to select.")


@mcp.tool(annotations=RO, description="List Outlook messages (default: inbox).")
async def outlook_list_messages(input: OutlookListMessagesInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_messages(alias, folder_id=input.folder_id,
                                        limit=input.limit, select=input.select)
    return client.format(result, input.response_format)


class OutlookGetMessageInput(BaseToolInput):
    message_id: str = Field(description="Message ID.", examples=["AAMkADQ..."])


@mcp.tool(annotations=RO, description="Get a single Outlook message by ID.")
async def outlook_get_message(input: OutlookGetMessageInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.get_message(input.message_id, alias)
    return client.format(result, input.response_format)


class OutlookSendMailInput(BaseToolInput, DryRunInput):
    to_recipients: list[str] = Field(description="Recipient email addresses.", examples=[["jane@example.com"]])
    subject: str = Field(description="Email subject.", examples=["Hello"])
    body: str = Field(description="Email body (HTML or text).", examples=["<p>Hello world</p>"])
    body_type: str = Field(default="HTML", description="Body content type: HTML or Text.")
    cc_recipients: list[str] | None = Field(default=None)
    bcc_recipients: list[str] | None = Field(default=None)
    save_to_sent_items: bool = Field(default=True)


@mcp.tool(annotations=WRITE, description="Send an Outlook email immediately. Use dry_run=true to validate.")
async def outlook_send_mail(input: OutlookSendMailInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would send mail to {input.to_recipients}: {input.subject}"
    message = {
        "subject": input.subject,
        "body": {"contentType": input.body_type, "content": input.body},
        "toRecipients": [{"emailAddress": {"address": a}} for a in input.to_recipients],
    }
    if input.cc_recipients:
        message["ccRecipients"] = [{"emailAddress": {"address": a}} for a in input.cc_recipients]
    if input.bcc_recipients:
        message["bccRecipients"] = [{"emailAddress": {"address": a}} for a in input.bcc_recipients]
    result = await client.send_mail(message, alias, input.save_to_sent_items)
    return client.format(result or {"status": "sent"}, input.response_format)


class OutlookCreateDraftInput(BaseToolInput, DryRunInput):
    subject: str = Field(default="", description="Draft subject.")
    body: str = Field(default="", description="Draft body (HTML).")
    to_recipients: list[str] | None = Field(default=None)


@mcp.tool(annotations=WRITE, description="Create an Outlook draft message.")
async def outlook_create_draft(input: OutlookCreateDraftInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create draft: {input.subject}"
    message: dict = {"subject": input.subject, "body": {"contentType": "HTML", "content": input.body}}
    if input.to_recipients:
        message["toRecipients"] = [{"emailAddress": {"address": a}} for a in input.to_recipients]
    result = await client.create_draft(message, alias)
    return client.format(result, input.response_format)


class OutlookReplyToMessageInput(BaseToolInput, DryRunInput):
    message_id: str = Field(description="Message ID to reply to.")
    comment: str = Field(description="Reply text.", examples=["Thanks for the update!"])


@mcp.tool(annotations=WRITE, description="Reply to an Outlook message.")
async def outlook_reply_to_message(input: OutlookReplyToMessageInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would reply to {input.message_id}: {input.comment}"
    result = await client.reply_to_message(input.message_id, input.comment, alias)
    return client.format(result or {"status": "replied"}, input.response_format)


class OutlookForwardMessageInput(BaseToolInput, DryRunInput):
    message_id: str = Field(description="Message ID to forward.")
    to_recipients: list[str] = Field(description="Forward-to addresses.")
    comment: str = Field(default="", description="Forward comment.")


@mcp.tool(annotations=WRITE, description="Forward an Outlook message.")
async def outlook_forward_message(input: OutlookForwardMessageInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would forward {input.message_id} to {input.to_recipients}"
    result = await client.forward_message(input.message_id, input.to_recipients, input.comment, alias)
    return client.format(result or {"status": "forwarded"}, input.response_format)


class OutlookListMailFoldersInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List Outlook mail folders.")
async def outlook_list_mail_folders(input: OutlookListMailFoldersInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_mail_folders(alias, limit=input.limit)
    return client.format(result, input.response_format)


class OutlookListCategoriesInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="List Outlook categories.")
async def outlook_list_categories(input: OutlookListCategoriesInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_message_categories(alias)
    return client.format(result, input.response_format)


class OutlookListRulesInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="List Outlook message rules.")
async def outlook_list_rules(input: OutlookListRulesInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_message_rules(alias)
    return client.format(result, input.response_format)


# ═══════════════════════════════════════════════════
# Outlook Calendar
# https://learn.microsoft.com/en-us/graph/api/resources/calendar
# ═══════════════════════════════════════════════════

class OutlookListCalendarsInput(BaseToolInput):
    limit: int = Field(default=50, ge=1, le=100)


@mcp.tool(annotations=RO, description="List Outlook calendars.")
async def outlook_list_calendars(input: OutlookListCalendarsInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_calendars(alias, limit=input.limit)
    return client.format(result, input.response_format)


class OutlookListEventsInput(BaseToolInput):
    calendar_id: str | None = Field(default=None, description="Calendar ID (default if None).")
    limit: int = Field(default=25, ge=1, le=50)
    start: str | None = Field(default=None, description="ISO 8601 start datetime.", examples=["2025-07-15T00:00:00Z"])
    end: str | None = Field(default=None, description="ISO 8601 end datetime.", examples=["2025-07-22T00:00:00Z"])


@mcp.tool(annotations=RO, description="List Outlook calendar events.")
async def outlook_list_events(input: OutlookListEventsInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.list_events(alias, calendar_id=input.calendar_id,
                                      limit=input.limit, start=input.start, end=input.end)
    return client.format(result, input.response_format)


class OutlookGetEventInput(BaseToolInput):
    event_id: str = Field(description="Event ID.")


@mcp.tool(annotations=RO, description="Get an Outlook calendar event by ID.")
async def outlook_get_event(input: OutlookGetEventInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.get_event(input.event_id, alias)
    return client.format(result, input.response_format)


class OutlookCreateEventInput(BaseToolInput, DryRunInput):
    subject: str = Field(description="Event subject.", examples=["Team Meeting"])
    start: str = Field(description="ISO 8601 start.", examples=["2025-07-15T10:00:00"])
    end: str = Field(description="ISO 8601 end.", examples=["2025-07-15T11:00:00"])
    start_timezone: str = Field(default="UTC")
    end_timezone: str = Field(default="UTC")
    body: str = Field(default="", description="Event body (HTML).")
    attendees: list[str] | None = Field(default=None, description="Attendee email addresses.")
    location: str | None = Field(default=None, description="Event location.")
    calendar_id: str | None = Field(default=None, description="Calendar ID (default if None).")


@mcp.tool(annotations=WRITE, description="Create an Outlook calendar event. Use dry_run=true to validate.")
async def outlook_create_event(input: OutlookCreateEventInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would create event '{input.subject}' on {input.start}"
    event = {
        "subject": input.subject,
        "body": {"contentType": "HTML", "content": input.body},
        "start": {"dateTime": input.start, "timeZone": input.start_timezone},
        "end": {"dateTime": input.end, "timeZone": input.end_timezone},
    }
    if input.attendees:
        event["attendees"] = [{"emailAddress": {"address": a}, "type": "required"} for a in input.attendees]
    if input.location:
        event["location"] = {"displayName": input.location}
    result = await client.create_event(event, alias, input.calendar_id)
    return client.format(result, input.response_format)


class OutlookUpdateEventInput(BaseToolInput, DryRunInput):
    event_id: str = Field(description="Event ID to update.")
    event: dict = Field(description="Fields to update.", examples=[{"subject": "Updated Subject"}])


@mcp.tool(annotations=IDEMPOTENT, description="Update an Outlook calendar event.")
async def outlook_update_event(input: OutlookUpdateEventInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would update event {input.event_id}: {input.event}"
    result = await client.update_event(input.event_id, input.event, alias)
    return client.format(result, input.response_format)


class OutlookDeleteEventInput(BaseToolInput, DryRunInput):
    event_id: str = Field(description="Event ID to delete.")
    confirm: bool = Field(default=False, description="Must be true to execute.")


@mcp.tool(annotations=DESTRUCTIVE, description="Delete an Outlook calendar event. DESTRUCTIVE — requires confirm=true.")
async def outlook_delete_event(input: OutlookDeleteEventInput) -> str:
    if not input.confirm:
        return "Deletion requires confirm=true."
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    if input.dry_run:
        return f"[DRY RUN] Would delete event {input.event_id}"
    result = await client.delete_event(input.event_id, alias)
    return client.format(result or {"status": "deleted"}, input.response_format)


class OutlookGetFreeBusyInput(BaseToolInput):
    schedules: list[str] = Field(description="Email addresses to check.", examples=[["jane@contoso.com"]])
    start: str = Field(description="ISO 8601 start.", examples=["2025-07-15T00:00:00Z"])
    end: str = Field(description="ISO 8601 end.", examples=["2025-07-15T23:59:59Z"])
    timezone: str = Field(default="UTC")


@mcp.tool(annotations=RO, description="Get free/busy information for Outlook users.")
async def outlook_get_free_busy(input: OutlookGetFreeBusyInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.get_free_busy(input.schedules, input.start, input.end, alias, input.timezone)
    return client.format(result, input.response_format)


# ── Graph escape-hatch ──

class GraphRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PATCH", "DELETE"])
    path: str = Field(description="Graph path after /v1.0 (starts with /).", examples=["/me"])
    query: dict | None = Field(default=None, description="Query parameters ($select, $filter, $top, etc.).")
    body: dict | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call ANY Microsoft Graph endpoint. Escape-hatch for full Graph API coverage.")
async def graph_request(input: GraphRequestInput) -> str:
    client = get_client("microsoft")
    alias = resolve_account("microsoft", input.account)
    result = await client.generic_request(input.method, input.path, alias,
                                          query=input.query, body=input.body)
    return client.format(result, input.response_format)