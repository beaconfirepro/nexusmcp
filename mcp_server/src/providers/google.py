"""
Google client — delegated OAuth (Gmail + Google Calendar).
Acts AS THE OWNER via delegated user OAuth with offline access.
https://developers.google.com/identity/protocols/oauth2/web-server

IMPORTANT: https://mail.google.com/ is a RESTRICTED scope. An unverified
("testing") OAuth app issues refresh tokens that expire ~7 days.
Move the OAuth app to "Production" or complete verification to avoid
periodic re-auth. See README for details.

Gmail base: https://gmail.googleapis.com/gmail/v1
  https://developers.google.com/gmail/api/reference/rest
Calendar base: https://www.googleapis.com/calendar/v3
  https://developers.google.com/calendar/api/v3/reference
"""
import base64
import logging

from src.oauth import OAuthConfig, OAuthHelper
from src.providers.base import BaseProviderClient
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.providers.google")


class GoogleClient(BaseProviderClient):
    def __init__(
        self,
        gmail_base_url: str,
        gcal_base_url: str,
        token_url: str,
        oauth_helper: OAuthHelper,
        oauth_config: OAuthConfig,
        token_store: TokenStore,
    ):
        # Use a neutral base_url; we override per-call with full URLs
        super().__init__("google", gmail_base_url)
        self._gmail_base = gmail_base_url
        self._gcal_base = gcal_base_url
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

    # ════════════════════════════════════════
    # Gmail API
    # https://developers.google.com/gmail/api/reference/rest
    # ════════════════════════════════════════

    async def list_messages(self, alias: str, q: str = "", max_results: int = 20,
                            label_ids: list[str] | None = None) -> dict:
        """List messages (metadata only; use get_message for full content).
        https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list
        """
        params: dict = {"maxResults": min(max_results, 100)}
        if q:
            params["q"] = q
        if label_ids:
            params["labelIds"] = label_ids
        return await self.request(
            "GET", "/users/me/messages",
            headers=await self._headers(alias), params=params,
            full_url=f"{self._gmail_base}/users/me/messages",
        )

    async def get_message(self, message_id: str, alias: str, format: str = "full") -> dict:
        """Get a message by ID.
        https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get
        format: full | metadata | minimal | raw
        """
        return await self.request(
            "GET", f"/users/me/messages/{message_id}",
            headers=await self._headers(alias),
            params={"format": format},
            full_url=f"{self._gmail_base}/users/me/messages/{message_id}",
        )

    async def send_message(self, raw_rfc822: str, alias: str) -> dict:
        """Send a message. raw_rfc822 is base64url-encoded RFC 822 message.
        https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send
        """
        encoded = base64.urlsafe_b64encode(raw_rfc822.encode()).decode().rstrip("=")
        return await self.request(
            "POST", "/users/me/messages/send",
            headers=await self._headers(alias),
            json_body={"raw": encoded},
            full_url=f"{self._gmail_base}/users/me/messages/send",
        )

    async def list_threads(self, alias: str, q: str = "", max_results: int = 20) -> dict:
        """List threads.
        https://developers.google.com/gmail/api/reference/rest/v1/users.threads/list
        """
        params: dict = {"maxResults": min(max_results, 100)}
        if q:
            params["q"] = q
        return await self.request(
            "GET", "/users/me/threads",
            headers=await self._headers(alias), params=params,
            full_url=f"{self._gmail_base}/users/me/threads",
        )

    async def get_thread(self, thread_id: str, alias: str) -> dict:
        """Get a thread by ID.
        https://developers.google.com/gmail/api/reference/rest/v1/users.threads/get
        """
        return await self.request(
            "GET", f"/users/me/threads/{thread_id}",
            headers=await self._headers(alias),
            full_url=f"{self._gmail_base}/users/me/threads/{thread_id}",
        )

    async def list_labels(self, alias: str) -> dict:
        """List labels.
        https://developers.google.com/gmail/api/reference/rest/v1/users.labels/list
        """
        return await self.request(
            "GET", "/users/me/labels",
            headers=await self._headers(alias),
            full_url=f"{self._gmail_base}/users/me/labels",
        )

    async def create_label(self, label: dict, alias: str) -> dict:
        """Create a label.
        https://developers.google.com/gmail/api/reference/rest/v1/users.labels/create
        """
        return await self.request(
            "POST", "/users/me/labels",
            headers=await self._headers(alias), json_body=label,
            full_url=f"{self._gmail_base}/users/me/labels",
        )

    async def create_draft(self, draft: dict, alias: str) -> dict:
        """Create a draft.
        https://developers.google.com/gmail/api/reference/rest/v1/users.drafts/create
        """
        return await self.request(
            "POST", "/users/me/drafts",
            headers=await self._headers(alias), json_body=draft,
            full_url=f"{self._gmail_base}/users/me/drafts",
        )

    async def list_filters(self, alias: str) -> dict:
        """List message filters.
        https://developers.google.com/gmail/api/reference/rest/v1/users.settings.filters/list
        """
        return await self.request(
            "GET", "/users/me/settings/filters",
            headers=await self._headers(alias),
            full_url=f"{self._gmail_base}/users/me/settings/filters",
        )

    async def get_vacation_settings(self, alias: str) -> dict:
        """Get vacation responder settings.
        https://developers.google.com/gmail/api/reference/rest/v1/users.settings/getVacation
        """
        return await self.request(
            "GET", "/users/me/settings/vacation",
            headers=await self._headers(alias),
            full_url=f"{self._gmail_base}/users/me/settings/vacation",
        )

    # ════════════════════════════════════════
    # Google Calendar API
    # https://developers.google.com/calendar/api/v3/reference
    # ════════════════════════════════════════

    async def list_calendars(self, alias: str) -> dict:
        """List calendar list (user's calendars).
        https://developers.google.com/calendar/api/v3/reference/calendarlist/list
        """
        return await self.request(
            "GET", "/users/me/calendarList",
            headers=await self._headers(alias),
            full_url=f"{self._gcal_base}/users/me/calendarList",
        )

    async def list_events(self, calendar_id: str, alias: str, max_results: int = 25,
                          time_min: str = None, time_max: str = None,
                          q: str = None, page_token: str = None) -> dict:
        """List events on a calendar.
        https://developers.google.com/calendar/api/v3/reference/events/list
        """
        params: dict = {"maxResults": min(max_results, 250)}
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        if q:
            params["q"] = q
        if page_token:
            params["pageToken"] = page_token
        return await self.request(
            "GET", f"/calendars/{calendar_id}/events",
            headers=await self._headers(alias), params=params,
            full_url=f"{self._gcal_base}/calendars/{calendar_id}/events",
        )

    async def get_event(self, calendar_id: str, event_id: str, alias: str) -> dict:
        """Get an event.
        https://developers.google.com/calendar/api/v3/reference/events/get
        """
        return await self.request(
            "GET", f"/calendars/{calendar_id}/events/{event_id}",
            headers=await self._headers(alias),
            full_url=f"{self._gcal_base}/calendars/{calendar_id}/events/{event_id}",
        )

    async def create_event(self, calendar_id: str, event: dict, alias: str) -> dict:
        """Create an event.
        https://developers.google.com/calendar/api/v3/reference/events/insert
        """
        return await self.request(
            "POST", f"/calendars/{calendar_id}/events",
            headers=await self._headers(alias), json_body=event,
            full_url=f"{self._gcal_base}/calendars/{calendar_id}/events",
        )

    async def update_event(self, calendar_id: str, event_id: str, event: dict, alias: str) -> dict:
        """Update an event.
        https://developers.google.com/calendar/api/v3/reference/events/patch
        """
        return await self.request(
            "PATCH", f"/calendars/{calendar_id}/events/{event_id}",
            headers=await self._headers(alias), json_body=event,
            full_url=f"{self._gcal_base}/calendars/{calendar_id}/events/{event_id}",
        )

    async def delete_event(self, calendar_id: str, event_id: str, alias: str) -> dict:
        """Delete an event.
        https://developers.google.com/calendar/api/v3/reference/events/delete
        """
        return await self.request(
            "DELETE", f"/calendars/{calendar_id}/events/{event_id}",
            headers=await self._headers(alias),
            full_url=f"{self._gcal_base}/calendars/{calendar_id}/events/{event_id}",
        )

    async def get_free_busy(self, time_min: str, time_max: str, alias: str,
                            calendar_ids: list[str] | None = None) -> dict:
        """Query free/busy information.
        https://developers.google.com/calendar/api/v3/reference/freebusy/query
        """
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": cid} for cid in (calendar_ids or ["primary"])] or [{"id": "primary"}],
        }
        return await self.request(
            "POST", "/freeBusy",
            headers=await self._headers(alias), json_body=body,
            full_url=f"{self._gcal_base}/freeBusy",
        )

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str, alias: str,
        query: dict | None = None, body: dict | None = None,
        service: str = "gmail",
    ) -> dict | list | str:
        """Call ANY Google API endpoint. path starts after the base URL.
        service: 'gmail' or 'calendar' (selects base URL).
        """
        base = self._gmail_base if service == "gmail" else self._gcal_base
        return await self.request(
            method, path,
            headers=await self._headers(alias),
            params=query,
            json_body=body,
            full_url=f"{base}/{path.lstrip('/')}",
        )