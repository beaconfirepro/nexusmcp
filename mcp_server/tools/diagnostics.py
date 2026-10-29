"""
Diagnostic MCP tool — check_provider_connectivity.
Authenticated, on-demand deep health check (separate from GET /health).
Makes ONE lightweight read call per provider account to verify auth + connectivity.
"""
import asyncio

from src.status import PROVIDERS, _check_reachable, list_account_aliases
from src.errors import format_response
from src.mcp_instance import RO, mcp
from src.models import BaseToolInput
from pydantic import Field


class CheckConnectivityInput(BaseToolInput):
    providers: list[str] | None = Field(
        default=None,
        description="Providers to check (default: all). Options: connecteam, qbo, hubspot, helm, microsoft, google.",
        examples=[["qbo", "google"]],
    )


@mcp.tool(annotations=RO,
          description="Check connectivity to each provider with a lightweight read call. "
                      "This is the authenticated on-demand equivalent of a deep health check "
                      "(separate from GET /health which is unauthenticated and makes no outbound calls).")
async def check_provider_connectivity(input: CheckConnectivityInput) -> str:
    providers = input.providers or list(PROVIDERS)
    results = {}

    async def check_provider(provider: str):
        # One lightweight read per account; OAuth providers may have several logins.
        aliases = list_account_aliases(provider)
        accounts = {}
        for alias in aliases:
            ok, err = await _check_reachable(provider, alias)
            accounts[alias] = {"status": "ok"} if ok else {"status": "error", "message": err}
        entry = {"status": "ok" if all(a["status"] == "ok" for a in accounts.values()) else "error"}
        if len(accounts) > 1:
            entry["accounts"] = accounts
        else:
            entry.update(next(iter(accounts.values())))
        results[provider] = entry

    tasks = [check_provider(p) for p in providers if p in PROVIDERS]
    await asyncio.gather(*tasks)

    return format_response(results, input.response_format)