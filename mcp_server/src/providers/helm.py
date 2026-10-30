"""
Helm client — Helm Public API v1, tenant API key (bearer).
The key decides the Helm tenant; no call names an org.
Contract: packages/api-spec/public-v1.yaml in Beacon-Fire-Protection/helm.
Base URL: {HELM_BASE_URL}/api/v1
Every resource has one shape:
  GET    /{resource}            list, cursor pages (limit 1..500, cursor, filters)
  GET    /{resource}/{id}       one record
  POST   /{resource}            create
  PATCH  /{resource}/{id}       update
  DELETE /{resource}/{id}       delete (or void, per the record's rule)
  POST   /{resource}/bulk       up to 500 ops, mode validate | commit
  POST   /{resource}/{id}/actions/{action}
Writes take `qbo=skip|push` in the query and an optional `Idempotency-Key` header.
Errors: { error: { code, message, field?, requestId } }.
"""
import logging

from src.providers.base import BaseProviderClient

logger = logging.getLogger("mcp_server.providers.helm")


class HelmClient(BaseProviderClient):
    AUTH_HINT = ("The Helm API key is missing, unknown or revoked (see error.code). Make a new key in "
                 "Helm Tenant Admin > API keys and update the helm-api-key secret (MAINTENANCE.md).")

    def __init__(self, api_key: str, base_url: str):
        super().__init__("helm", base_url)
        self._api_key = api_key

    def _headers(self, idempotency_key: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def ping(self) -> dict:
        """The calling key's tenant, kind and scopes. Needs no scope."""
        return await self.request("GET", "/ping", headers=self._headers())

    async def list_records(self, resource: str, limit: int = 100, cursor: str | None = None,
                           filters: dict | None = None) -> dict:
        """One page of a resource: { data: [...], nextCursor }."""
        params = dict(filters or {})
        params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        return await self.request("GET", f"/{resource}", headers=self._headers(), params=params)

    async def get_record(self, resource: str, record_id: str) -> dict:
        return await self.request("GET", f"/{resource}/{record_id}", headers=self._headers())

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str,
        query: dict | None = None, body: dict | list | None = None,
        idempotency_key: str | None = None,
    ) -> dict | list | str:
        """Call ANY Helm Public API endpoint. path is relative to /api/v1 and starts with /."""
        return await self.request(
            method, path,
            headers=self._headers(idempotency_key),
            params=query,
            json_body=body,
        )
