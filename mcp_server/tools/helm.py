"""
Helm MCP tools.
Helm Public API v1, tenant API key (bearer). The key decides the Helm tenant
and its scopes (`<group>:read`, `<group>:write`); a call outside them answers
403 ScopeMissing.
Every resource has the same shape, so the typed tools accept `resource` as a
parameter (jobs, companies, ...) instead of one tool per resource, and
helm_request covers writes, bulk and actions.
"""
from pydantic import Field

from src.clients import get_client
from src.mcp_instance import RO, WRITE, mcp
from src.models import BaseToolInput

# A resource is one lowercase path segment, so it can never climb out of /api/v1.
RESOURCE_PATTERN = r"^[a-z][a-z0-9-]*$"


# ── Ping ──

class HelmPingInput(BaseToolInput):
    pass


@mcp.tool(annotations=RO, description="Check the Helm API key: returns its tenant (orgId), name, kind and scopes.")
async def helm_ping(input: HelmPingInput) -> str:
    client = get_client("helm")
    result = await client.ping()
    return client.format(result, input.response_format)


# ── List records ──

class HelmListInput(BaseToolInput):
    resource: str = Field(
        pattern=RESOURCE_PATTERN,
        description="Helm resource (e.g. jobs, companies).",
        examples=["jobs"],
    )
    limit: int = Field(default=100, ge=1, le=500, description="Max records per page.")
    cursor: str | None = Field(default=None, description="Pagination cursor (nextCursor from the previous page).")
    filters: dict | None = Field(
        default=None,
        description="Resource filters as query parameters, e.g. updatedSince, ids, externalId, status.",
        examples=[{"updatedSince": "2026-10-01T00:00:00Z", "status": "active"}],
    )


@mcp.tool(annotations=RO, description="List Helm records of one resource, one cursor page at a time.")
async def helm_list(input: HelmListInput) -> str:
    client = get_client("helm")
    result = await client.list_records(input.resource, limit=input.limit,
                                       cursor=input.cursor, filters=input.filters)
    return client.format(result, input.response_format)


# ── Get record ──

class HelmGetInput(BaseToolInput):
    resource: str = Field(pattern=RESOURCE_PATTERN, description="Helm resource.", examples=["jobs"])
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", description="Record id.", examples=["cm3x9k2a10001"])


@mcp.tool(annotations=RO, description="Get a single Helm record by id.")
async def helm_get(input: HelmGetInput) -> str:
    client = get_client("helm")
    result = await client.get_record(input.resource, input.id)
    return client.format(result, input.response_format)


# ── Escape-hatch ──

class HelmRequestInput(BaseToolInput):
    method: str = Field(description="HTTP method.", examples=["GET", "POST", "PATCH", "DELETE"])
    path: str = Field(
        pattern=r"^/",
        description="Path relative to /api/v1 (starts with /).",
        examples=["/jobs", "/jobs/bulk", "/invoices/123/actions/issue"],
    )
    query: dict | None = Field(
        default=None,
        description="Query parameters. Writes take qbo=skip|push (default skip on bulk).",
        examples=[{"qbo": "skip"}],
    )
    body: dict | list | None = Field(default=None, description="Request body (JSON).")
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency-Key header. A repeat of the same write within 24h replays the first response.",
    )


@mcp.tool(annotations=WRITE,
          description="Call ANY Helm Public API v1 endpoint (create, update, delete, bulk, actions). "
                      "Escape-hatch for full API coverage.")
async def helm_request(input: HelmRequestInput) -> str:
    client = get_client("helm")
    result = await client.generic_request(input.method, input.path, query=input.query,
                                          body=input.body, idempotency_key=input.idempotency_key)
    return client.format(result, input.response_format)
