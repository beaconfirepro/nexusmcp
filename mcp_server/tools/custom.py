"""
Custom API MCP tools — every API an admin adds with "Add an API" in the Nexus
web app. One generic tool covers them all, so a new API is callable on the
next call with no redeploy. Keys never leave the server: api_list_connections
returns no secrets.
"""
from pydantic import Field

from src.clients import get_client
from src.mcp_instance import RO, WRITE, mcp
from src.models import BaseToolInput


# ── List connections ──

class ApiListConnectionsInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO,
          description="List the APIs added in the Nexus web app (slug, name, base URL, auth type, description).")
async def api_list_connections(input: ApiListConnectionsInput) -> str:
    client = get_client("custom")
    connections = await client.list_connections()
    safe = [
        {k: c.get(k) for k in ("slug", "name", "base_url", "auth_type", "description")}
        for c in connections
    ]
    return client.format(safe, input.response_format)


# ── Request ──

class ApiRequestInput(BaseToolInput):
    api: str = Field(
        pattern=r"^[a-z][a-z0-9_]{1,30}$",
        description="The API's slug, from api_list_connections.",
        examples=["helm_dev"],
    )
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PATCH", "PUT", "DELETE"])
    path: str = Field(
        pattern=r"^/([^/].*)?$",
        description="Path appended to the API's base URL (starts with a single /).",
        examples=["/v1/customers"],
    )
    query: dict | None = Field(default=None, description="Query parameters.")
    body: dict | list | None = Field(default=None, description="Request body (JSON).")


@mcp.tool(annotations=WRITE,
          description="Call an API added in the Nexus web app, with its stored key. "
                      "Use api_list_connections to see which APIs exist.")
async def api_request(input: ApiRequestInput) -> str:
    client = get_client("custom")
    result = await client.call(input.api, input.method, input.path, query=input.query, body=input.body)
    return client.format(result, input.response_format)
