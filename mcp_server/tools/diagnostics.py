"""
Diagnostic MCP tool — check_provider_connectivity.
Authenticated, on-demand deep health check (separate from GET /health).
Makes ONE lightweight read call per provider to verify auth + connectivity.
"""
import asyncio

from src.clients import get_client, resolve_account
from src.errors import format_response
from src.mcp_instance import RO, mcp
from src.models import BaseToolInput
from pydantic import Field


class CheckConnectivityInput(BaseToolInput):
    providers: list[str] | None = Field(
        default=None,
        description="Providers to check (default: all). Options: connecteam, qbo, hubspot, microsoft, google.",
        examples=[["qbo", "google"]],
    )


@mcp.tool(annotations=RO,
          description="Check connectivity to each provider with a lightweight read call. "
                      "This is the authenticated on-demand equivalent of a deep health check "
                      "(separate from GET /health which is unauthenticated and makes no outbound calls).")
async def check_provider_connectivity(input: CheckConnectivityInput) -> str:
    providers = input.providers or ["connecteam", "qbo", "hubspot", "microsoft", "google"]
    results = {}

    async def check_connecteam():
        try:
            client = get_client("connecteam")
            await client.get_me()
            results["connecteam"] = {"status": "ok"}
        except Exception as e:
            results["connecteam"] = {"status": "error", "message": str(e)[:200]}

    async def check_qbo():
        try:
            client = get_client("qbo")
            alias = resolve_account("qbo", None)
            await client.query_entity("Customer", alias, limit=1)
            results["qbo"] = {"status": "ok"}
        except Exception as e:
            results["qbo"] = {"status": "error", "message": str(e)[:200]}

    async def check_hubspot():
        try:
            client = get_client("hubspot")
            await client.list_objects("contacts", limit=1)
            results["hubspot"] = {"status": "ok"}
        except Exception as e:
            results["hubspot"] = {"status": "error", "message": str(e)[:200]}

    async def check_microsoft():
        try:
            client = get_client("microsoft")
            alias = resolve_account("microsoft", None)
            await client.list_calendars(alias, limit=1)
            results["microsoft"] = {"status": "ok"}
        except Exception as e:
            results["microsoft"] = {"status": "error", "message": str(e)[:200]}

    async def check_google():
        try:
            client = get_client("google")
            alias = resolve_account("google", None)
            await client.list_calendars(alias)
            results["google"] = {"status": "ok"}
        except Exception as e:
            results["google"] = {"status": "error", "message": str(e)[:200]}

    checker_map = {
        "connecteam": check_connecteam,
        "qbo": check_qbo,
        "hubspot": check_hubspot,
        "microsoft": check_microsoft,
        "google": check_google,
    }

    tasks = [checker_map[p]() for p in providers if p in checker_map]
    await asyncio.gather(*tasks)

    return format_response(results, input.response_format)