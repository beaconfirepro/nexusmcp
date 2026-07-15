"""
QuickBooks Online client — OAuth 2.0.
Refresh tokens ROTATE on every use — persisted to Table Storage immediately.
https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
Base URL: sandbox → https://sandbox-quickbooks.api.intuit.com
           production → https://quickbooks.api.intuit.com
API path: /v3/company/{realmId}/{entity}
Query: /v3/company/{realmId}/query?query=SELECT * FROM Invoice
Reports: /v3/company/{realmId}/reports/{ReportName}
Minor version: 75 (current as of docs)
"""
import logging

from src.errors import ProviderError
from src.oauth import OAuthConfig, OAuthHelper
from src.providers.base import BaseProviderClient
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.providers.qbo")

QBO_MINOR_VERSION = "75"  # https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/minor-versions


class QboClient(BaseProviderClient):
    def __init__(
        self,
        base_url: str,
        token_url: str,
        oauth_helper: OAuthHelper,
        oauth_config: OAuthConfig,
        token_store: TokenStore,
    ):
        super().__init__("qbo", base_url)
        self._oauth_helper = oauth_helper
        self._oauth_config = oauth_config
        self._store = token_store

    async def _headers(self, alias: str) -> dict:
        access_token = await self._oauth_helper.get_valid_access_token(
            self._oauth_config, alias
        )
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _realm_id(self, alias: str) -> str:
        realm_id = self._store.get_realm_id("qbo", alias)
        if not realm_id:
            raise ProviderError(
                f"No realmId found for qbo:{alias}. The realmId must be stored "
                f"alongside the refresh token. Re-run scripts/seed_oauth.py.",
                provider="qbo",
            )
        return realm_id

    def _path(self, alias: str, suffix: str) -> str:
        return f"/v3/company/{self._realm_id(alias)}/{suffix.lstrip('/')}"

    def _params(self, extra: dict | None = None) -> dict:
        params = {"minorversion": QBO_MINOR_VERSION}
        if extra:
            params.update(extra)
        return params

    # ── Entity CRUD ──

    async def query_entity(self, entity: str, alias: str, where: str = "",
                           limit: int = 50, offset: int = 1) -> dict:
        """Query entities using QBO SQL-like query language.
        https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/data-queries
        """
        query = f"SELECT * FROM {entity} STARTPOSITION {offset} MAXRESULTS {limit}"
        if where:
            query = f"SELECT * FROM {entity} WHERE {where} STARTPOSITION {offset} MAXRESULTS {limit}"
        return await self.request(
            "GET", self._path(alias, "query"),
            headers=await self._headers(alias),
            params=self._params({"query": query}),
        )

    async def get_entity(self, entity: str, entity_id: str, alias: str) -> dict:
        return await self.request(
            "GET", self._path(alias, f"{entity}/{entity_id}"),
            headers=await self._headers(alias),
            params=self._params(),
        )

    async def create_entity(self, entity: str, data: dict, alias: str) -> dict:
        return await self.request(
            "POST", self._path(alias, entity),
            headers=await self._headers(alias),
            params=self._params(),
            json_body=data,
        )

    async def update_entity(self, entity: str, entity_id: str, data: dict, alias: str) -> dict:
        # QBO updates require full entity with SyncToken — caller must provide it
        data.setdefault("Id", entity_id)
        return await self.request(
            "POST", self._path(alias, entity),
            headers=await self._headers(alias),
            params=self._params({"operation": "update"}),
            json_body=data,
        )

    async def delete_entity(self, entity: str, entity_id: str, alias: str) -> dict:
        # QBO delete is an operation on the entity endpoint
        return await self.request(
            "POST", self._path(alias, entity),
            headers=await self._headers(alias),
            params=self._params({"operation": "delete"}),
            json_body={"Id": entity_id},
        )

    async def get_report(self, report_name: str, alias: str, params: dict | None = None) -> dict:
        """Get a QBO report (e.g. ProfitAndLoss, BalanceSheet, CashFlow).
        https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/report
        """
        return await self.request(
            "GET", self._path(alias, f"reports/{report_name}"),
            headers=await self._headers(alias),
            params=self._params(params),
        )

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str, alias: str,
        query: dict | None = None, body: dict | None = None,
    ) -> dict | list | str:
        """Call ANY QBO endpoint. path should include /v3/company/{realmId}/... or start after base URL."""
        return await self.request(
            method, path,
            headers=await self._headers(alias),
            params=self._params(query),
            json_body=body,
        )