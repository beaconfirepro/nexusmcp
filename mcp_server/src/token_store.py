"""
Azure Table Storage adapter for rotating OAuth refresh tokens.
This is the app's ONLY direct Azure-SDK access. Uses the user-assigned
managed identity (AZURE_CLIENT_ID) — NEVER used for Microsoft Graph calls.

Table schema:
  PartitionKey = provider  ("qbo" | "microsoft" | "google")
  RowKey        = alias     ("main", etc.)
  Fields:
    refresh_token     — current refresh token (rotated on every use for QBO)
    realm_id          — QuickBooks company realmId (QBO only)
    access_token      — cached access token (optional, in-memory TTL)
    expires_at        — ISO 8601 timestamp when access_token expires
    updated_at        — ISO 8601 timestamp of last refresh

References:
  https://learn.microsoft.com/en-us/azure/storage/tables/table-storage-overview
  https://learn.microsoft.com/en-us/python/api/overview/azure/data-tables-readme
"""
import logging
from datetime import datetime, timezone

from azure.data.tables import TableClient
from azure.identity import ManagedIdentityCredential

from src.config import Settings

logger = logging.getLogger("mcp_server.token_store")


class TokenStore:
    """Read+write rotating OAuth tokens from Azure Table Storage."""

    def __init__(self, settings: Settings):
        self._settings = settings
        # ManagedIdentityCredential with explicit client_id — the app's ONLY
        # use of the managed identity. NEVER used for Graph calls.
        # https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.ManagedIdentityCredential
        self._credential = ManagedIdentityCredential(
            client_id=settings.AZURE_CLIENT_ID
        )
        self._client: TableClient | None = None

    def _get_client(self) -> TableClient:
        if self._client is None:
            endpoint = f"https://{self._settings.TOKEN_STORE_ACCOUNT}.table.core.windows.net"
            self._client = TableClient(
                endpoint=endpoint,
                table_name=self._settings.TOKEN_STORE_TABLE,
                credential=self._credential,
            )
            try:
                self._client.create_table()
                logger.info("Created token store table '%s'", self._settings.TOKEN_STORE_TABLE)
            except Exception:
                # Table already exists — expected on warm starts
                pass
        return self._client

    def get_token_record(self, provider: str, alias: str) -> dict | None:
        """Read a token record. Returns dict with refresh_token, realm_id, etc., or None."""
        try:
            entity = self._get_client().get_entity(
                partition_key=provider, row_key=alias
            )
            return dict(entity)
        except Exception:
            logger.warning("No token record found for %s:%s", provider, alias)
            return None

    def get_refresh_token(self, provider: str, alias: str) -> str | None:
        record = self.get_token_record(provider, alias)
        return record.get("refresh_token") if record else None

    def get_realm_id(self, provider: str, alias: str) -> str | None:
        record = self.get_token_record(provider, alias)
        return record.get("realm_id") if record else None

    def save_token(
        self,
        provider: str,
        alias: str,
        refresh_token: str,
        access_token: str | None = None,
        expires_in: int | None = None,
        realm_id: str | None = None,
    ):
        """Persist a (possibly rotated) refresh token + cached access token."""
        now = datetime.now(timezone.utc).isoformat()
        entity = {
            "PartitionKey": provider,
            "RowKey": alias,
            "refresh_token": refresh_token,
            "updated_at": now,
        }
        if access_token:
            entity["access_token"] = access_token
        if expires_in:
            from datetime import timedelta
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).isoformat()
            entity["expires_at"] = expiry
        if realm_id:
            entity["realm_id"] = realm_id

        self._get_client().upsert_entity(entity)
        logger.info("Persisted token for %s:%s", provider, alias)

    def get_cached_access_token(self, provider: str, alias: str) -> str | None:
        """Return a cached access token if still valid, else None."""
        record = self.get_token_record(provider, alias)
        if not record:
            return None
        access_token = record.get("access_token")
        expires_at_str = record.get("expires_at")
        if not access_token or not expires_at_str:
            return None
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now(timezone.utc) < expires_at:
                return access_token
        except (ValueError, TypeError):
            pass
        return None

    def list_aliases(self, provider: str) -> list[str]:
        """List all registered aliases for a provider."""
        try:
            entities = self._get_client().query_entities(
                query_filter=f"PartitionKey eq '{provider}'",
                select=["RowKey"],
            )
            return [e["RowKey"] for e in entities]
        except Exception:
            return []