"""
Initialized provider client instances. Populated at startup by init_clients().
Tool functions access clients via get_client() — avoids global state at import time.
"""
import logging

from src.config import Settings
from src.oauth import OAuthConfig, OAuthHelper
from src.registry import AccountRegistry
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.clients")

_clients: dict[str, object] = {}
_oauth_helper: OAuthHelper | None = None
_token_store: TokenStore | None = None
_registry: AccountRegistry | None = None
_oauth_configs: dict[str, OAuthConfig] = {}


def get_client(provider: str):
    """Get the initialized client for a provider."""
    client = _clients.get(provider)
    if client is None:
        raise RuntimeError(
            f"Provider client '{provider}' is not initialized. "
            f"Available: {list(_clients.keys())}"
        )
    return client


def get_token_store() -> TokenStore:
    if _token_store is None:
        raise RuntimeError("Token store not initialized. Call init_clients() first.")
    return _token_store


def get_oauth_helper() -> OAuthHelper:
    if _oauth_helper is None:
        raise RuntimeError("OAuth helper not initialized. Call init_clients() first.")
    return _oauth_helper


def get_oauth_config(provider: str) -> OAuthConfig | None:
    """Get the OAuth config for a provider (qbo, microsoft, google)."""
    return _oauth_configs.get(provider)


def resolve_account(provider: str, account: str | None) -> str:
    """Resolve an optional account argument to a concrete alias string."""
    global _registry
    if _registry is None:
        _registry = AccountRegistry(_token_store)
    return _registry.resolve_alias_simple(provider, account)


def init_clients(settings: Settings):
    """Initialize all provider clients. Called once at startup."""
    global _token_store, _oauth_helper, _registry

    _token_store = TokenStore(settings)
    _oauth_helper = OAuthHelper(_token_store)

    # Import here to avoid circular imports
    from src.providers.connecteam import ConnecteamClient
    from src.providers.qbo import QboClient
    from src.providers.hubspot import HubSpotClient
    from src.providers.graph import GraphClient
    from src.providers.google import GoogleClient

    # Connecteam — API key auth
    # https://developer.connecteam.com/docs/authentication-1
    _clients["connecteam"] = ConnecteamClient(
        api_key=settings.CONNECTEAM_KEY,
        base_url=settings.connecteam_base_url,
    )

    # HubSpot — private-app access token (bearer)
    # https://developers.hubspot.com/docs/api/private-apps
    _clients["hubspot"] = HubSpotClient(
        access_token=settings.HUBSPOT_MAIN,
        base_url=settings.hubspot_base_url,
    )

    # QuickBooks Online — OAuth 2.0
    # https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
    _clients["qbo"] = QboClient(
        base_url=settings.qbo_base_url,
        token_url=settings.qbo_token_url,
        oauth_helper=_oauth_helper,
        oauth_config=OAuthConfig(
            provider="qbo",
            token_url=settings.qbo_token_url,
            client_id=settings.QBO_CLIENT_ID,
            client_secret=settings.QBO_CLIENT_SECRET,
        ),
        token_store=_token_store,
    )

    # Microsoft Graph — delegated user OAuth (Entra app registration)
    # Acts as owner, NOT app-only. Separate from the managed identity.
    # https://learn.microsoft.com/en-us/graph/permissions-reference
    _clients["microsoft"] = GraphClient(
        base_url=settings.graph_base_url,
        oauth_helper=_oauth_helper,
        oauth_config=OAuthConfig(
            provider="microsoft",
            token_url=settings.graph_token_url,
            client_id=settings.GRAPH_CLIENT_ID,
            client_secret=settings.GRAPH_CLIENT_SECRET,
            # Delegated scopes: offline_access, User.Read, Sites.ReadWrite.All,
            # Files.ReadWrite.All, Mail.ReadWrite, Mail.Send, Calendars.ReadWrite
            scope="offline_access User.Read Sites.ReadWrite.All Files.ReadWrite.All "
                  "Mail.ReadWrite Mail.Send Calendars.ReadWrite",
        ),
        token_store=_token_store,
    )

    # Google — delegated OAuth (Gmail + Google Calendar)
    # https://developers.google.com/identity/protocols/oauth2/web-server
    _clients["google"] = GoogleClient(
        gmail_base_url=settings.gmail_base_url,
        gcal_base_url=settings.gcal_base_url,
        token_url=settings.google_token_url,
        oauth_helper=_oauth_helper,
        oauth_config=OAuthConfig(
            provider="google",
            token_url=settings.google_token_url,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            # Gmail: https://mail.google.com/ (RESTRICTED scope)
            # Calendar: https://www.googleapis.com/auth/calendar
            scope="https://mail.google.com/ https://www.googleapis.com/auth/calendar",
        ),
        token_store=_token_store,
    )

    # Expose OAuth configs for the /status endpoint (scope checks, token info)
    for _p in ("qbo", "microsoft", "google"):
        _oauth_configs[_p] = _clients[_p]._oauth_config

    _registry = AccountRegistry(_token_store)

    logger.info(
        "Initialized provider clients: %s",
        ", ".join(_clients.keys()),
    )