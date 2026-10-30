"""
Custom APIs — the ones an admin adds with "Add an API" in the Nexus web app.

The connections (base URL, auth, key) live in the Base44 app's ApiConnection
entity. This server reads them, per call, from the app's backend function
nexusApiConnections, authenticating with NEXUS_BRIDGE_SECRET:
  GET {NEXUS_APP_URL}/api/functions/nexusApiConnections
  -> { connections: [{ slug, name, base_url, auth_type, header_name, secret, description }] }
Reading per call means a connection added, changed or disabled in the web app
takes effect on the next tool call, with no redeploy.
"""
import logging

from src.errors import ProviderError
from src.providers.base import BaseProviderClient

logger = logging.getLogger("mcp_server.providers.custom")


class CustomApiClient(BaseProviderClient):
    AUTH_HINT = ("The API rejected the key stored for this connection. Replace it on the APIs page of the "
                 "Nexus web app.")

    def __init__(self, app_url: str, bridge_secret: str):
        super().__init__("custom", f"{app_url.rstrip('/')}/api/functions")
        self._bridge_secret = bridge_secret

    async def list_connections(self) -> list[dict]:
        result = await self.request(
            "GET", "/nexusApiConnections",
            headers={"Authorization": f"Bearer {self._bridge_secret}"},
        )
        return result["connections"]

    async def get_connection(self, slug: str) -> dict:
        connections = await self.list_connections()
        for conn in connections:
            if conn["slug"] == slug:
                return conn
        raise ProviderError(
            f"No enabled API connection '{slug}'. "
            f"Available: {', '.join(c['slug'] for c in connections) or '(none)'}.",
            provider="custom",
            hint="Add or enable it on the APIs page of the Nexus web app.",
        )

    @staticmethod
    def _auth_headers(conn: dict) -> dict:
        if conn["auth_type"] == "bearer":
            return {"Authorization": f"Bearer {conn['secret']}"}
        if conn["auth_type"] == "header":
            return {conn["header_name"]: conn["secret"]}
        return {}

    async def call(self, slug: str, method: str, path: str,
                   query: dict | None = None, body: dict | list | None = None) -> dict | list | str:
        """Call `path` on the connection's base URL with its stored auth."""
        conn = await self.get_connection(slug)
        return await self.request(
            method, path,
            full_url=f"{conn['base_url'].rstrip('/')}{path}",
            headers={"Content-Type": "application/json", **self._auth_headers(conn)},
            params=query,
            json_body=body,
        )
