"""
Microsoft Graph client — delegated user OAuth (Entra app registration).
Acts AS THE OWNER, not app-only. Separate from the managed identity
(which is for Table Storage only and NEVER used for Graph calls).
https://learn.microsoft.com/en-us/graph/api/overview
Base URL: https://graph.microsoft.com/v1.0

Covers:
  - SharePoint: sites, drives, driveItems, lists, list items, search, upload/download
  - Outlook mail: messages, mailFolders, drafts, send, reply, forward, attachments, categories, rules
  - Outlook calendar: calendars, events, invites/responses, scheduling, free/busy
"""
import logging

from src.oauth import OAuthConfig, OAuthHelper
from src.providers.base import BaseProviderClient
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.providers.graph")


class GraphClient(BaseProviderClient):
    def __init__(
        self,
        base_url: str,
        oauth_helper: OAuthHelper,
        oauth_config: OAuthConfig,
        token_store: TokenStore,
    ):
        super().__init__("microsoft", base_url)
        self._oauth_helper = oauth_helper
        self._oauth_config = oauth_config
        self._store = token_store

    async def _headers(self, alias: str) -> dict:
        access_token = await self._oauth_helper.get_valid_access_token(
            self._oauth_config, alias
        )
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _headers_binary(self, alias: str) -> dict:
        access_token = await self._oauth_helper.get_valid_access_token(
            self._oauth_config, alias
        )
        return {"Authorization": f"Bearer {access_token}"}

    # ════════════════════════════════════════
    # SharePoint
    # https://learn.microsoft.com/en-us/graph/api/resources/sharepoint
    # ════════════════════════════════════════

    async def list_sites(self, alias: str, limit: int = 50) -> dict:
        """List SharePoint sites.
        https://learn.microsoft.com/en-us/graph/api/site-list
        """
        return await self.request("GET", "/sites", headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def get_site(self, site_id: str, alias: str) -> dict:
        """Get a SharePoint site by ID or hostname:path.
        https://learn.microsoft.com/en-us/graph/api/site-get
        """
        return await self.request("GET", f"/sites/{site_id}", headers=await self._headers(alias))

    async def list_drives(self, site_id: str, alias: str, limit: int = 50) -> dict:
        """List document libraries (drives) in a site.
        https://learn.microsoft.com/en-us/graph/api/drive-list
        """
        return await self.request("GET", f"/sites/{site_id}/drives",
                                  headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def list_drive_items(self, drive_id: str, alias: str, item_id: str = None,
                               limit: int = 50) -> dict:
        """List children of a drive item (root if item_id is None).
        https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
        """
        path = f"/drives/{drive_id}/items/{item_id}/children" if item_id \
            else f"/drives/{drive_id}/root/children"
        return await self.request("GET", path, headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def upload_file(self, drive_id: str, parent_item_id: str, filename: str,
                          content: bytes, alias: str) -> dict:
        """Upload a file to a drive folder (small file, < 4MB).
        https://learn.microsoft.com/en-us/graph/api/driveitem-put-content
        """
        path = f"/drives/{drive_id}/items/{parent_item_id}:/{filename}:/content"
        resp = await self._http.put(
            f"{self.base_url}{path}",
            headers=await self._headers_binary(alias),
            content=content,
        )
        if resp.status_code >= 400:
            raise Exception(f"Upload failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()

    async def download_file(self, drive_id: str, item_id: str, alias: str) -> bytes:
        """Download a file's content.
        https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
        """
        path = f"/drives/{drive_id}/items/{item_id}/content"
        resp = await self._http.get(
            f"{self.base_url}{path}", headers=await self._headers(alias), follow_redirects=True,
        )
        if resp.status_code >= 400:
            raise Exception(f"Download failed: {resp.status_code} {resp.text[:200]}")
        return resp.content

    async def list_lists(self, site_id: str, alias: str, limit: int = 50) -> dict:
        """List SharePoint lists.
        https://learn.microsoft.com/en-us/graph/api/list-list
        """
        return await self.request("GET", f"/sites/{site_id}/lists",
                                  headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def list_list_items(self, site_id: str, list_id: str, alias: str, limit: int = 50) -> dict:
        """List items in a SharePoint list.
        https://learn.microsoft.com/en-us/graph/api/listitem-list
        """
        return await self.request("GET", f"/sites/{site_id}/lists/{list_id}/items",
                                  headers=await self._headers(alias),
                                  params={"$top": min(limit, 100), "$expand": "fields"})

    async def search_site(self, site_id: str, query: str, alias: str, limit: int = 25) -> dict:
        """Search within a SharePoint site.
        https://learn.microsoft.com/en-us/graph/api/site-search
        """
        return await self.request("GET", f"/sites/{site_id}",
                                  headers=await self._headers(alias),
                                  params={"$search": query, "$top": min(limit, 100)})

    # ════════════════════════════════════════
    # Outlook Mail
    # https://learn.microsoft.com/en-us/graph/api/resources/message
    # ════════════════════════════════════════

    async def list_messages(self, alias: str, folder_id: str = None, limit: int = 25,
                            select: list[str] | None = None) -> dict:
        """List messages in a mail folder (default: inbox).
        https://learn.microsoft.com/en-us/graph/api/user-list-messages
        """
        path = f"/me/mailFolders/{folder_id}/messages" if folder_id else "/me/messages"
        params: dict = {"$top": min(limit, 50)}
        if select:
            params["$select"] = ",".join(select)
        else:
            params["$select"] = "id,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead"
        return await self.request("GET", path, headers=await self._headers(alias), params=params)

    async def get_message(self, message_id: str, alias: str) -> dict:
        """Get a single message by ID.
        https://learn.microsoft.com/en-us/graph/api/message-get
        """
        return await self.request("GET", f"/me/messages/{message_id}",
                                  headers=await self._headers(alias))

    async def send_mail(self, message: dict, alias: str, save_to_sent_items: bool = True) -> dict:
        """Send an email immediately.
        https://learn.microsoft.com/en-us/graph/api/user-sendmail
        """
        body = {"message": message, "saveToSentItems": save_to_sent_items}
        return await self.request("POST", "/me/sendMail",
                                  headers=await self._headers(alias), json_body=body)

    async def create_draft(self, message: dict, alias: str) -> dict:
        """Create a draft message.
        https://learn.microsoft.com/en-us/graph/api/user-post-messages
        """
        return await self.request("POST", "/me/messages",
                                  headers=await self._headers(alias), json_body=message)

    async def reply_to_message(self, message_id: str, comment: str, alias: str) -> dict:
        """Reply to a message.
        https://learn.microsoft.com/en-us/graph/api/message-reply
        """
        return await self.request("POST", f"/me/messages/{message_id}/reply",
                                  headers=await self._headers(alias),
                                  json_body={"comment": comment})

    async def forward_message(self, message_id: str, to_recipients: list[str],
                              comment: str, alias: str) -> dict:
        """Forward a message.
        https://learn.microsoft.com/en-us/graph/api/message-forward
        """
        body = {
            "comment": comment,
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to_recipients],
        }
        return await self.request("POST", f"/me/messages/{message_id}/forward",
                                  headers=await self._headers(alias), json_body=body)

    async def list_mail_folders(self, alias: str, limit: int = 50) -> dict:
        """List mail folders.
        https://learn.microsoft.com/en-us/graph/api/user-list-mailfolders
        """
        return await self.request("GET", "/me/mailFolders",
                                  headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def list_message_categories(self, alias: str) -> dict:
        """List Outlook categories.
        https://learn.microsoft.com/en-us/graph/api/user-list-outlookcategories
        """
        return await self.request("GET", "/me/outlook/masterCategories",
                                  headers=await self._headers(alias))

    async def list_message_rules(self, alias: str) -> dict:
        """List message rules.
        https://learn.microsoft.com/en-us/graph/api/mailfolder-list-messagerules
        """
        return await self.request("GET", "/me/mailFolders/inbox/messageRules",
                                  headers=await self._headers(alias))

    # ════════════════════════════════════════
    # Outlook Calendar
    # https://learn.microsoft.com/en-us/graph/api/resources/calendar
    # ════════════════════════════════════════

    async def list_calendars(self, alias: str, limit: int = 50) -> dict:
        """List the user's calendars.
        https://learn.microsoft.com/en-us/graph/api/user-list-calendars
        """
        return await self.request("GET", "/me/calendars",
                                  headers=await self._headers(alias),
                                  params={"$top": min(limit, 100)})

    async def list_events(self, alias: str, calendar_id: str = None, limit: int = 25,
                          start: str = None, end: str = None) -> dict:
        """List calendar events (default calendar if calendar_id is None).
        https://learn.microsoft.com/en-us/graph/api/calendar-list-events
        """
        path = f"/me/calendars/{calendar_id}/events" if calendar_id else "/me/events"
        params: dict = {"$top": min(limit, 50)}
        if start and end:
            params["$filter"] = f"start/dateTime ge '{start}' and end/dateTime le '{end}'"
        params["$orderby"] = "start/dateTime"
        return await self.request("GET", path, headers=await self._headers(alias), params=params)

    async def get_event(self, event_id: str, alias: str) -> dict:
        """Get a calendar event.
        https://learn.microsoft.com/en-us/graph/api/event-get
        """
        return await self.request("GET", f"/me/events/{event_id}",
                                  headers=await self._headers(alias))

    async def create_event(self, event: dict, alias: str, calendar_id: str = None) -> dict:
        """Create a calendar event.
        https://learn.microsoft.com/en-us/graph/api/user-post-events
        """
        path = f"/me/calendars/{calendar_id}/events" if calendar_id else "/me/events"
        return await self.request("POST", path, headers=await self._headers(alias), json_body=event)

    async def update_event(self, event_id: str, event: dict, alias: str) -> dict:
        """Update a calendar event.
        https://learn.microsoft.com/en-us/graph/api/event-update
        """
        return await self.request("PATCH", f"/me/events/{event_id}",
                                  headers=await self._headers(alias), json_body=event)

    async def delete_event(self, event_id: str, alias: str) -> dict:
        """Delete a calendar event.
        https://learn.microsoft.com/en-us/graph/api/event-delete
        """
        return await self.request("DELETE", f"/me/events/{event_id}",
                                  headers=await self._headers(alias))

    async def get_free_busy(self, schedules: list[str], start: str, end: str,
                            alias: str, timezone: str = "UTC") -> dict:
        """Get free/busy information for users.
        https://learn.microsoft.com/en-us/graph/api/calendar-getschedule
        """
        body = {
            "schedules": schedules,
            "startTime": {"dateTime": start, "timeZone": timezone},
            "endTime": {"dateTime": end, "timeZone": timezone},
            "availabilityViewInterval": 30,
        }
        return await self.request("POST", "/me/calendar/getSchedule",
                                  headers=await self._headers(alias), json_body=body)

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str, alias: str,
        query: dict | None = None, body: dict | None = None,
    ) -> dict | list | str:
        """Call ANY Microsoft Graph endpoint. path should start with / (relative to /v1.0)."""
        return await self.request(
            method, path,
            headers=await self._headers(alias),
            params=query,
            json_body=body,
        )