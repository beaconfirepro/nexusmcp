"""
Shared OAuth refresh helper — reused across QuickBooks Online,
Microsoft Graph, and Google. Each provider supplies its token endpoint,
client_id, client_secret, and scope. The helper:
  1. Checks for a cached (still-valid) access token in Table Storage.
  2. If none, reads the refresh token from Table Storage.
  3. Calls the provider's token endpoint to get a new access + refresh token.
  4. Persists the rotated refresh token (and cached access token) to Table Storage.
  5. Returns the valid access token.

Critical for QBO: refresh tokens ROTATE on every use — the rotated token
must be persisted immediately or subsequent calls fail.
https://help.developer.intuit.com/s/question/0D54R000070vrMwSAI/how-to-get-new-refresh-token-without-user-consent

References:
  QBO: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
  Microsoft: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
  Google: https://developers.google.com/identity/protocols/oauth2/web-server#httprest_7
"""
import logging

import httpx

from src.errors import AuthExpiredError, ProviderError
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.oauth")


class OAuthConfig:
    """Per-provider OAuth configuration."""
    def __init__(
        self,
        provider: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "",
    ):
        self.provider = provider
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope


class OAuthHelper:
    """Shared token-refresh logic for all OAuth providers."""

    def __init__(self, token_store: TokenStore):
        self._store = token_store
        self._http = httpx.AsyncClient(timeout=30.0)

    async def get_valid_access_token(
        self, oauth_config: OAuthConfig, alias: str
    ) -> str:
        """Return a valid access token, refreshing if necessary."""
        # 1. Check cache
        cached = self._store.get_cached_access_token(oauth_config.provider, alias)
        if cached:
            logger.debug("Using cached access token for %s:%s", oauth_config.provider, alias)
            return cached

        # 2. Read refresh token
        refresh_token = self._store.get_refresh_token(oauth_config.provider, alias)
        if not refresh_token:
            raise AuthExpiredError(oauth_config.provider, alias)

        # 3. Exchange refresh token for new access + refresh token
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": oauth_config.client_id,
            "client_secret": oauth_config.client_secret,
        }
        if oauth_config.scope:
            data["scope"] = oauth_config.scope

        try:
            resp = await self._http.post(oauth_config.token_url, data=data)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Network error refreshing {oauth_config.provider} token: {exc}",
                provider=oauth_config.provider,
            )

        if resp.status_code != 200:
            body = resp.text
            # NEVER log token values — log only status and error type
            if "invalid_grant" in body or resp.status_code == 400:
                raise AuthExpiredError(
                    oauth_config.provider, alias,
                    detail="Refresh token is invalid or expired.",
                )
            raise ProviderError(
                f"Token refresh failed for {oauth_config.provider}:{alias} (HTTP {resp.status_code}).",
                provider=oauth_config.provider,
                status_code=resp.status_code,
                hint="Check client credentials and refresh token. Re-run scripts/seed_oauth.py if needed.",
            )

        token_data = resp.json()
        new_access_token = token_data.get("access_token")
        new_refresh_token = token_data.get("refresh_token", refresh_token)
        expires_in = token_data.get("expires_in")

        # 4. Persist rotated refresh token + cached access token
        # For QBO, refresh tokens ROTATE — the new one must be saved or the next call fails.
        realm_id = self._store.get_realm_id(oauth_config.provider, alias)
        self._store.save_token(
            provider=oauth_config.provider,
            alias=alias,
            refresh_token=new_refresh_token,
            access_token=new_access_token,
            expires_in=expires_in,
            realm_id=realm_id,
        )
        logger.info("Refreshed access token for %s:%s", oauth_config.provider, alias)

        return new_access_token

    async def close(self):
        await self._http.aclose()