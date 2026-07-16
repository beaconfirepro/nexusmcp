"""
Central configuration. Reads ALL static secrets from environment
variables (12-factor). The app NEVER calls Key Vault SDK — Azure
Container Apps injects Key Vault secret values as env vars via
Key Vault-reference secrets resolved with the attached managed identity.

Env var contract (see .env.example for descriptions):
  MCP_BASE_URL, OWNER_LOGIN_PASSWORD, JWT_SIGNING_KEY,
  CONNECTEAM_KEY, HUBSPOT_MAIN,
  QBO_CLIENT_ID, QBO_CLIENT_SECRET, QBO_ENV,
  GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, TENANT_ID,
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  AZURE_CLIENT_ID, TOKEN_STORE_ACCOUNT, TOKEN_STORE_TABLE
"""
import os
from dataclasses import dataclass

VERSION = "1.0.0"

REQUIRED_ENV_VARS = [
    "MCP_BASE_URL",
    "OWNER_LOGIN_PASSWORD",
    "JWT_SIGNING_KEY",
    "CONNECTEAM_KEY",
    "HUBSPOT_MAIN",
    "QBO_CLIENT_ID",
    "QBO_CLIENT_SECRET",
    "QBO_ENV",
    "GRAPH_CLIENT_ID",
    "GRAPH_CLIENT_SECRET",
    "TENANT_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "AZURE_CLIENT_ID",
    "TOKEN_STORE_ACCOUNT",
]


@dataclass(frozen=True)
class Settings:
    # Inbound auth — OAuth 2.1 authorization server
    MCP_BASE_URL: str            # Public base URL, e.g. https://multi-mcp.xxx.eastus.azurecontainerapps.io
    OWNER_LOGIN_PASSWORD: str    # Single-owner password for /authorize login screen
    JWT_SIGNING_KEY: str         # HS256 signing key for JWT access tokens
    # Connecteam — https://developer.connecteam.com/docs/authentication-1
    CONNECTEAM_KEY: str
    # HubSpot — https://developers.hubspot.com/docs/api/private-apps
    HUBSPOT_MAIN: str
    # QuickBooks Online — https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
    QBO_CLIENT_ID: str
    QBO_CLIENT_SECRET: str
    QBO_ENV: str  # "sandbox" | "production"
    # Microsoft Graph (delegated user OAuth)
    GRAPH_CLIENT_ID: str
    GRAPH_CLIENT_SECRET: str
    TENANT_ID: str
    # Google (delegated OAuth)
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    # Azure Table Storage — managed identity (for token store ONLY)
    AZURE_CLIENT_ID: str
    TOKEN_STORE_ACCOUNT: str
    TOKEN_STORE_TABLE: str

    @property
    def qbo_base_url(self) -> str:
        if self.QBO_ENV == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    @property
    def qbo_token_url(self) -> str:
        return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    @property
    def graph_base_url(self) -> str:
        return "https://graph.microsoft.com/v1.0"

    @property
    def graph_token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.TENANT_ID}/oauth2/v2.0/token"

    @property
    def graph_auth_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.TENANT_ID}/oauth2/v2.0/authorize"

    @property
    def google_token_url(self) -> str:
        return "https://oauth2.googleapis.com/token"

    @property
    def google_auth_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"

    @property
    def gmail_base_url(self) -> str:
        return "https://gmail.googleapis.com/gmail/v1"

    @property
    def gcal_base_url(self) -> str:
        return "https://www.googleapis.com/calendar/v3"

    @property
    def connecteam_base_url(self) -> str:
        return "https://api.connecteam.com"

    @property
    def hubspot_base_url(self) -> str:
        return "https://api.hubapi.com"


def load_settings() -> Settings:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"See .env.example for the full list and descriptions."
        )
    qbo_env = os.environ["QBO_ENV"]
    if qbo_env not in ("sandbox", "production"):
        raise RuntimeError(
            f"QBO_ENV must be 'sandbox' or 'production', got: {qbo_env!r}"
        )
    return Settings(
        MCP_BASE_URL=os.environ["MCP_BASE_URL"],
        OWNER_LOGIN_PASSWORD=os.environ["OWNER_LOGIN_PASSWORD"],
        JWT_SIGNING_KEY=os.environ["JWT_SIGNING_KEY"],
        CONNECTEAM_KEY=os.environ["CONNECTEAM_KEY"],
        HUBSPOT_MAIN=os.environ["HUBSPOT_MAIN"],
        QBO_CLIENT_ID=os.environ["QBO_CLIENT_ID"],
        QBO_CLIENT_SECRET=os.environ["QBO_CLIENT_SECRET"],
        QBO_ENV=qbo_env,
        GRAPH_CLIENT_ID=os.environ["GRAPH_CLIENT_ID"],
        GRAPH_CLIENT_SECRET=os.environ["GRAPH_CLIENT_SECRET"],
        TENANT_ID=os.environ["TENANT_ID"],
        GOOGLE_CLIENT_ID=os.environ["GOOGLE_CLIENT_ID"],
        GOOGLE_CLIENT_SECRET=os.environ["GOOGLE_CLIENT_SECRET"],
        AZURE_CLIENT_ID=os.environ["AZURE_CLIENT_ID"],
        TOKEN_STORE_ACCOUNT=os.environ["TOKEN_STORE_ACCOUNT"],
        TOKEN_STORE_TABLE=os.environ.get("TOKEN_STORE_TABLE", "oauthtokens"),
    )