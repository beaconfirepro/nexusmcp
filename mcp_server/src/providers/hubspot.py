"""
HubSpot client — private-app access token (bearer).
Classic API keys are sunset; use private-app tokens.
https://developers.hubspot.com/docs/api/private-apps
Base URL: https://api.hubapi.com
CRM v3: /crm/v3/objects/{objectType}
Search: POST /crm/v3/objects/{objectType}/search
"""
import logging

from src.providers.base import BaseProviderClient

logger = logging.getLogger("mcp_server.providers.hubspot")


class HubSpotClient(BaseProviderClient):
    def __init__(self, access_token: str, base_url: str):
        super().__init__("hubspot", base_url)
        self._access_token = access_token

    def _headers(self) -> dict:
        # https://developers.hubspot.com/docs/api/private-apps
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _list_params(self, limit: int, after: str | None, extra: dict | None = None) -> dict:
        params = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if extra:
            params.update(extra)
        return params

    # ── CRM objects ──

    async def list_objects(self, object_type: str, limit: int = 50, after: str | None = None,
                           properties: list[str] | None = None) -> dict:
        """List CRM objects (contacts, companies, deals, tickets, products, line_items, etc.).
        https://developers.hubspot.com/docs/api/crm/objects
        """
        params = self._list_params(limit, after)
        if properties:
            params["properties"] = ",".join(properties)
        return await self.request(
            "GET", f"/crm/v3/objects/{object_type}",
            headers=self._headers(), params=params,
        )

    async def get_object(self, object_type: str, object_id: str,
                         properties: list[str] | None = None) -> dict:
        params = {}
        if properties:
            params["properties"] = ",".join(properties)
        return await self.request(
            "GET", f"/crm/v3/objects/{object_type}/{object_id}",
            headers=self._headers(), params=params or None,
        )

    async def create_object(self, object_type: str, properties: dict,
                            associations: list[dict] | None = None) -> dict:
        body = {"properties": properties}
        if associations:
            body["associations"] = associations
        return await self.request(
            "POST", f"/crm/v3/objects/{object_type}",
            headers=self._headers(), json_body=body,
        )

    async def update_object(self, object_type: str, object_id: str, properties: dict) -> dict:
        return await self.request(
            "PATCH", f"/crm/v3/objects/{object_type}/{object_id}",
            headers=self._headers(), json_body={"properties": properties},
        )

    async def archive_object(self, object_type: str, object_id: str) -> dict:
        """Archive (soft delete) a CRM object."""
        return await self.request(
            "DELETE", f"/crm/v3/objects/{object_type}/{object_id}",
            headers=self._headers(),
        )

    async def search_objects(self, object_type: str, filter_properties: list[dict] | None = None,
                             sorts: list[dict] | None = None, query: str | None = None,
                             limit: int = 50, after: str | None = None,
                             properties: list[str] | None = None) -> dict:
        """Search CRM objects with filters.
        https://developers.hubspot.com/docs/api/crm/search
        """
        body: dict = {"limit": min(limit, 100)}
        if filter_properties:
            body["filters"] = filter_properties
        if sorts:
            body["sorts"] = sorts
        if query:
            body["query"] = query
        if after:
            body["after"] = after
        if properties:
            body["properties"] = properties
        return await self.request(
            "POST", f"/crm/v3/objects/{object_type}/search",
            headers=self._headers(), json_body=body,
        )

    # ── Associations ──

    async def list_associations(self, object_type: str, object_id: str,
                                to_object_type: str, limit: int = 50) -> dict:
        """List associations between objects.
        https://developers.hubspot.com/docs/api/crm/associations
        """
        return await self.request(
            "GET", f"/crm/v4/objects/{object_type}/{object_id}/associations/{to_object_type}",
            headers=self._headers(), params={"limit": min(limit, 500)},
        )

    async def create_association(self, object_type: str, object_id: str,
                                 to_object_type: str, to_object_id: str,
                                 association_type: str) -> dict:
        return await self.request(
            "PUT",
            f"/crm/v4/objects/{object_type}/{object_id}/associations/{to_object_type}/{to_object_id}",
            headers=self._headers(),
            json_body=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type}],
        )

    # ── Engagements (notes, calls, emails) ──

    async def create_note(self, engagement: dict, metadata: dict,
                          associations: list[dict] | None = None) -> dict:
        """Create a note engagement.
        https://developers.hubspot.com/docs/api/crm/notes
        """
        body = {"engagement": engagement, "metadata": metadata}
        if associations:
            body["associations"] = associations
        return await self.request(
            "POST", "/engagements/v1/engagements",
            headers=self._headers(), json_body=body,
        )

    # ── Properties ──

    async def list_properties(self, object_type: str) -> dict:
        """List all properties for an object type.
        https://developers.hubspot.com/docs/api/crm/properties
        """
        return await self.request(
            "GET", f"/crm/v3/properties/{object_type}",
            headers=self._headers(),
        )

    # ── Pipelines ──

    async def list_pipelines(self, object_type: str) -> dict:
        """List pipelines for an object type (e.g. deals, tickets).
        https://developers.hubspot.com/docs/api/crm/pipelines
        """
        return await self.request(
            "GET", f"/crm/v3/pipelines/{object_type}",
            headers=self._headers(),
        )

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str,
        query: dict | None = None, body: dict | None = None,
    ) -> dict | list | str:
        """Call ANY HubSpot endpoint. path should start with /."""
        return await self.request(
            method, path,
            headers=self._headers(),
            params=query,
            json_body=body,
        )