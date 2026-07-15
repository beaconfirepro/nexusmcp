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

from src.clients import get_client, get_oauth_config, get_oauth_helper, get_token_store, resolve_account
from src.config import Settings

logger = logging.getLogger("mcp_server.status")

PROVIDERS = ["connecteam", "qbo", "hubspot", "microsoft", "google"]


def _is_configured(provider: str, settings: Settings) -> bool:
    """Check if required credentials are present in the environment."""
    checks = {
        "connecteam": bool(settings.CONNECTEAM_KEY),
        "hubspot": bool(settings.HUBSPOT_MAIN),
        "qbo": bool(settings.QBO_CLIENT_ID and settings.QBO_CLIENT_SECRET),
        "microsoft": bool(settings.GRAPH_CLIENT_ID and settings.GRAPH_CLIENT_SECRET),
        "google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
    return checks.get(provider, False)


def _is_seeded(provider: str) -> bool:
    """For OAuth providers, check if a refresh token exists in Table Storage."""
    if provider not in ("qbo", "microsoft", "google"):
        return True  # Static-key providers are always 'seeded'
    try:
        store = get_token_store()
        alias = resolve_account(provider, None)
        record = store.get_token_record(provider, alias)
        return record is not None and bool(record.get("refresh_token"))
    except Exception:
        return False


def _get_expires_at(provider: str) -> str | None:
    """Get token expiry from the token store if applicable."""
    if provider not in ("qbo", "microsoft", "google"):
        return None
    try:
        store = get_token_store()
        alias = resolve_account(provider, None)
        record = store.get_token_record(provider, alias)
        if record:
            return record.get("expires_at")
    except Exception:
        pass
    return None


async def _check_reachable(provider: str) -> tuple[bool, str | None]:
    """Lightweight live auth ping — reuses existing client methods."""
    try:
        if provider == "connecteam":
            await get_client("connecteam").get_me()
        elif provider == "qbo":
            client = get_client("qbo")
            alias = resolve_account("qbo", None)
            await client.query_entity("Customer", alias, limit=1)
        elif provider == "hubspot":
            await get_client("hubspot").list_objects("contacts", limit=1)
        elif provider == "microsoft":
            client = get_client("microsoft")
            alias = resolve_account("microsoft", None)
            await client.list_calendars(alias, limit=1)
        elif provider == "google":
            client = get_client("google")
            alias = resolve_account("google", None)
            await client.list_calendars(alias)
        return True, None
    except Exception as e:
        return False, str(e)[:200]


async def _get_scopes(provider: str) -> list[str]:
    """Fetch granted scopes per provider."""
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

    if provider == "microsoft":
        # Decode the access token JWT's scp claim
        # https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens
        try:
            oauth_helper = get_oauth_helper()
            oauth_config = get_oauth_config("microsoft")
            alias = resolve_account("microsoft", None)
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
            alias = resolve_account("google", None)
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


async def _check_provider(provider: str, settings: Settings) -> dict:
    """Gather all status data for one provider."""
    configured = _is_configured(provider, settings)
    seeded = _is_seeded(provider)
    expires_at = _get_expires_at(provider)

    reachable = False
    error: str | None = None
    scopes: list[str] = []

    if not configured:
        error = "Not configured — required env vars are missing."
    elif not seeded:
        error = "Not seeded — no refresh token in token store. Run scripts/seed_oauth.py."
    else:
        reachable, error = await _check_reachable(provider)
        if reachable:
            scopes = await _get_scopes(provider)

    return {
        "configured": configured,
        "seeded": seeded,
        "reachable": reachable,
        "scopes": scopes,
        "expires_at": expires_at,
        "error": error,
    }


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
            }

    results = await asyncio.gather(*[safe_check(p) for p in PROVIDERS])
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "providers": dict(results),
    }