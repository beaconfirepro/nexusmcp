"""
Provider status checker — aggregates configuration, OAuth seeding, live
connectivity, granted scopes, and token expiry for each provider.
Used by GET /status.

Reuses existing clients, token_store, and oauth helpers — no new HTTP
infrastructure beyond lightweight tokeninfo calls. Never leaks secrets or
token values. All logging goes to stderr.
"""
import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

import httpx

from src.clients import get_client, get_oauth_config, get_oauth_helper, get_token_store
from src.config import Settings

logger = logging.getLogger("mcp_server.status")

PROVIDERS = ["connecteam", "qbo", "hubspot", "helm", "microsoft", "google"]


def _is_configured(provider: str, settings: Settings) -> bool:
    """Check if required credentials are present in the environment."""
    checks = {
        "connecteam": bool(settings.CONNECTEAM_KEY),
        "hubspot": bool(settings.HUBSPOT_MAIN),
        "helm": bool(settings.HELM_API_KEY and settings.HELM_BASE_URL),
        "qbo": bool(settings.QBO_CLIENT_ID and settings.QBO_CLIENT_SECRET),
        "microsoft": bool(settings.GRAPH_CLIENT_ID and settings.GRAPH_CLIENT_SECRET),
        "google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
    return checks.get(provider, False)


OAUTH_PROVIDERS = ("qbo", "microsoft", "google")
DEFAULT_ALIAS = "main"


def list_account_aliases(provider: str) -> list[str]:
    """All account aliases for a provider (bare aliases, e.g. 'main', 'work2').
    OAuth providers: every row in the token store, always including the default
    alias so an unseeded 'main' still reports as 'Not seeded'. Static-key
    providers have a single login."""
    if provider not in OAUTH_PROVIDERS:
        return [DEFAULT_ALIAS]
    try:
        found = sorted(get_token_store().list_aliases(provider))
    except Exception:
        found = []
    if DEFAULT_ALIAS in found:
        found.remove(DEFAULT_ALIAS)
    return [DEFAULT_ALIAS, *found]


def _get_record(provider: str, alias: str) -> dict | None:
    if provider not in OAUTH_PROVIDERS:
        return None
    try:
        return get_token_store().get_token_record(provider, alias)
    except Exception:
        return None


async def _check_reachable(provider: str, alias: str) -> tuple[bool, str | None]:
    """Lightweight live auth ping — reuses existing client methods."""
    try:
        if provider == "connecteam":
            await get_client("connecteam").get_me()
        elif provider == "qbo":
            await get_client("qbo").query_entity("Customer", alias, limit=1)
        elif provider == "hubspot":
            await get_client("hubspot").list_objects("contacts", limit=1)
        elif provider == "helm":
            await get_client("helm").ping()
        elif provider == "microsoft":
            await get_client("microsoft").list_calendars(alias, limit=1)
        elif provider == "google":
            await get_client("google").list_calendars(alias)
        return True, None
    except Exception as e:
        return False, str(e)[:200]


async def _get_scopes(provider: str, alias: str) -> list[str]:
    """Fetch granted scopes per provider/account."""
    if provider == "connecteam":
        return ["api_key"]

    if provider == "qbo":
        return ["com.intuit.quickbooks.accounting"]

    if provider == "hubspot":
        # Private-app token — try the access-token-info endpoint
        # https://developers.hubspot.com/docs/api/private-apps
        try:
            token = get_client("hubspot")._access_token
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.get(f"https://api.hubapi.com/oauth/v1/access-tokens/{token}")
                if resp.status_code == 200:
                    return resp.json().get("scopes", [])
        except Exception:
            pass
        return []

    if provider == "helm":
        # The key's scopes, from GET /api/v1/ping
        return (await get_client("helm").ping())["scopes"]

    if provider == "microsoft":
        # Decode the access token JWT's scp claim
        # https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens
        try:
            oauth_helper = get_oauth_helper()
            oauth_config = get_oauth_config("microsoft")
            access_token = await oauth_helper.get_valid_access_token(oauth_config, alias)
            parts = access_token.split(".")
            if len(parts) >= 2:
                payload = parts[1] + "=" * (-len(parts[1]) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload))
                scp = claims.get("scp", "")
                if isinstance(scp, str):
                    return scp.split() if scp else []
                if isinstance(scp, list):
                    return scp
        except Exception:
            pass
        return []

    if provider == "google":
        # Google tokeninfo endpoint
        # https://developers.google.com/identity/protocols/oauth2/web-server#tokeninfo
        try:
            oauth_helper = get_oauth_helper()
            oauth_config = get_oauth_config("google")
            access_token = await oauth_helper.get_valid_access_token(oauth_config, alias)
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"access_token": access_token},
                )
                if resp.status_code == 200:
                    scope_str = resp.json().get("scope", "")
                    return scope_str.split() if scope_str else []
        except Exception:
            pass
        return []

    return []


async def _check_account(provider: str, alias: str, settings: Settings) -> dict:
    """Gather all status data for one account (alias) of a provider."""
    configured = _is_configured(provider, settings)
    record = _get_record(provider, alias)
    seeded = True if provider not in OAUTH_PROVIDERS else bool(record and record.get("refresh_token"))
    expires_at = record.get("expires_at") if record else None

    reachable = False
    error: str | None = None
    scopes: list[str] = []

    if not configured:
        error = "Not configured — required env vars are missing."
    elif not seeded:
        error = "Not seeded — no refresh token in token store. Run scripts/seed_oauth.py"
        error += " or open /connect/microsoft." if provider == "microsoft" else "."
    else:
        reachable, error = await _check_reachable(provider, alias)
        if reachable:
            scopes = await _get_scopes(provider, alias)

    return {
        "configured": configured,
        "seeded": seeded,
        "reachable": reachable,
        "scopes": scopes,
        "expires_at": expires_at,
        "error": error,
    }


async def _check_provider(provider: str, settings: Settings) -> dict:
    """Status for a provider. Top-level fields describe the default ('main')
    account (backwards compatible); `accounts` maps every alias to its own status."""
    aliases = list_account_aliases(provider)
    results = await asyncio.gather(*[_check_account(provider, a, settings) for a in aliases])
    accounts = dict(zip(aliases, results))
    return {**accounts[DEFAULT_ALIAS], "accounts": accounts}


async def get_all_provider_status(settings: Settings) -> dict:
    """Check all providers concurrently. Returns the full /status response."""
    async def safe_check(p):
        try:
            return p, await _check_provider(p, settings)
        except Exception as e:
            logger.error("Status check failed for %s: %s", p, e)
            return p, {
                "configured": False,
                "seeded": False,
                "reachable": False,
                "scopes": [],
                "expires_at": None,
                "error": f"Status check failed: {str(e)[:200]}",
                "accounts": {},
            }

    results = await asyncio.gather(*[safe_check(p) for p in PROVIDERS])
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "providers": dict(results),
    }