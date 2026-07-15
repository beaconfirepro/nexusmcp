"""
Account registry: maps ACCOUNT ALIAS -> { provider }.
Every data tool takes an optional `account` argument. With one login per
provider, it defaults to that provider's single registered alias.
Unknown alias -> actionable error listing valid aliases.

Providers and their starting single login:
  connecteam:main   qbo:main   hubspot:main
  microsoft:main    (Graph: SharePoint + Outlook mail + Outlook calendar)
  google:main       (Gmail + Google Calendar)

Microsoft tools (sharepoint_*, outlook_*) resolve to a microsoft:* login.
Google tools (gmail_*, gcal_*) resolve to a google:* login.
"""
import logging

from src.errors import UnknownAliasError
from src.token_store import TokenStore

logger = logging.getLogger("mcp_server.registry")

# Provider -> default alias (the starting single login per provider)
DEFAULT_ALIASES: dict[str, str] = {
    "connecteam": "connecteam:main",
    "qbo": "qbo:main",
    "hubspot": "hubspot:main",
    "microsoft": "microsoft:main",
    "google": "google:main",
}

# Tool prefix -> provider
TOOL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "connecteam": "connecteam",
    "qbo": "qbo",
    "hubspot": "hubspot",
    "sharepoint": "microsoft",
    "outlook": "microsoft",
    "gmail": "google",
    "gcal": "google",
}


class AccountRegistry:
    """Resolves account aliases to provider + credentials."""

    def __init__(self, token_store: TokenStore):
        self._store = token_store

    def resolve_alias(self, provider: str, account: str | None) -> str:
        """
        Resolve an optional account argument to a concrete alias.
        If account is None, returns the provider's default alias.
        If account is given, validates it exists in the token store
        (for OAuth providers) or in the defaults (for static-key providers).
        """
        if account is None:
            alias = DEFAULT_ALIASES.get(provider)
            if not alias:
                raise UnknownAliasError("(none)", provider, list(DEFAULT_ALIASES.values()))
            return alias

        # Validate: for OAuth providers, check token store has a record
        if provider in ("qbo", "microsoft", "google"):
            record = self._store.get_token_record(provider, account.split(":")[-1] if ":" in account else account)
            # Also try the account as-is (might be just "main")
            if not record:
                # Try splitting "provider:alias" if user passed full alias
                parts = account.split(":", 1)
                alias_part = parts[-1] if len(parts) == 2 else account
                record = self._store.get_token_record(provider, alias_part)
            if not record:
                valid = self._store.list_aliases(provider)
                if not valid:
                    valid = [DEFAULT_ALIASES.get(provider, "")]
                raise UnknownAliasError(account, provider, valid)
            # Return the normalized alias (just the alias part, not "provider:alias")
            return account if ":" in account else f"{provider}:{account}"

        # For static-key providers (connecteam, hubspot), validate against defaults
        if account in DEFAULT_ALIASES.values() or account == DEFAULT_ALIASES.get(provider, "").split(":")[-1]:
            return account if ":" in account else f"{provider}:{account}"

        raise UnknownAliasError(account, provider, [DEFAULT_ALIASES.get(provider, "")])

    def resolve_alias_simple(self, provider: str, account: str | None) -> str:
        """
        Simplified resolver: returns the alias string (e.g. 'main')
        used as RowKey in Table Storage. Falls back to default.
        """
        if account is None:
            alias = DEFAULT_ALIASES.get(provider)
            if not alias:
                raise UnknownAliasError("(none)", provider, list(DEFAULT_ALIASES.values()))
            return alias.split(":")[-1]

        # Normalize: if "provider:main", take "main"; if "main", keep "main"
        parts = account.split(":", 1)
        alias = parts[-1] if len(parts) == 2 else account

        # Validate exists
        if provider in ("qbo", "microsoft", "google"):
            record = self._store.get_token_record(provider, alias)
            if not record:
                valid = self._store.list_aliases(provider)
                if not valid:
                    valid = [DEFAULT_ALIASES.get(provider, "").split(":")[-1]]
                raise UnknownAliasError(account, provider, valid)

        return alias