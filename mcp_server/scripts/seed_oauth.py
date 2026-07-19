#!/usr/bin/env python3
"""
Standalone OAuth seeding script — run LOCALLY (not on the deployed server).
Opens browser sign-in for QBO / Microsoft Graph / Google, exchanges the
authorization code for tokens, and writes the refresh token (and QBO realmId)
to Azure Table Storage using the OPERATOR'S OWN Azure credentials (az login /
DefaultAzureCredential).

Usage:
  python scripts/seed_oauth.py qbo
  python scripts/seed_oauth.py microsoft
  python scripts/seed_oauth.py google

Prerequisites:
  - az login (for the operator's own Azure credentials to write to Table Storage)
  - Environment variables set (see .env.example)
  - For QBO: redirect URI registered as http://localhost:8765/callback
  - For Microsoft: redirect URI registered as http://localhost:8765/callback
  - For Google: redirect URI registered as http://localhost:8765/callback

References:
  QBO: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
  Microsoft: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
  Google: https://developers.google.com/identity/protocols/oauth2/web-server
"""
import asyncio
import base64
import hashlib
import logging
import os
import secrets
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_oauth")

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


def get_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        logger.error(f"Environment variable {name} is not set. See .env.example.")
        sys.exit(1)
    return val


def get_table_client() -> TableClient:
    """Connect to Azure Table Storage using the operator's own credentials (az login)."""
    account = get_env("TOKEN_STORE_ACCOUNT")
    table = os.environ.get("TOKEN_STORE_TABLE", "oauthtokens")
    endpoint = f"https://{account}.table.core.windows.net"
    credential = DefaultAzureCredential()
    client = TableClient(endpoint=endpoint, table_name=table, credential=credential)
    try:
        client.create_table()
        logger.info(f"Created table '{table}'")
    except Exception:
        pass
    return client


def save_token(provider: str, alias: str, refresh_token: str,
               access_token: str = "", expires_in: int = 0,
               realm_id: str = None):
    """Write a token record to Table Storage."""
    from datetime import datetime, timedelta, timezone
    client = get_table_client()
    entity = {
        "PartitionKey": provider,
        "RowKey": alias,
        "refresh_token": refresh_token,
        "access_token": access_token,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if expires_in:
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).isoformat()
        entity["expires_at"] = expiry
    if realm_id:
        entity["realm_id"] = realm_id
    client.upsert_entity(entity)
    logger.info(f"Saved refresh token for {provider}:{alias}")


async def wait_for_callback(port: int) -> dict:
    """Start a local HTTP server and wait for the OAuth callback redirect."""
    import socketserver
    from http.server import BaseHTTPRequestHandler

    result: dict = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            result.update({k: v[0] for k, v in params.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this window.</p></body></html>"
            )

        def log_message(self, *args):
            pass  # Suppress default logging

    server = socketserver.TCPServer(("localhost", port), CallbackHandler)
    server.timeout = 300  # 5 minute timeout
    logger.info(f"Waiting for OAuth callback on http://localhost:{port}/callback ...")
    server.handle_request()
    server.server_close()
    return result


# ──────────────────────────────────────────────────────────────
# QuickBooks Online
# ──────────────────────────────────────────────────────────────

async def seed_qbo(alias: str = "main"):
    """Seed QuickBooks Online OAuth tokens.
    Captures realmId TOGETHER with the refresh token.
    """
    client_id = get_env("QBO_CLIENT_ID")
    client_secret = get_env("QBO_CLIENT_SECRET")
    env = get_env("QBO_ENV")

    # https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
    auth_base = "https://appcenter.intuit.com/connect/oauth2"
    scope = "com.intuit.quickbooks.accounting app-foundations.custom-field-definitions"

    params = urlencode({
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": secrets.token_urlsafe(16),
    })
    auth_url = f"{auth_base}?{params}"
    logger.info(f"Opening browser for QuickBooks Online sign-in...")
    webbrowser.open(auth_url)

    callback = await wait_for_callback(REDIRECT_PORT)
    code = callback.get("code")
    realm_id = callback.get("realmId")

    if not code:
        logger.error(f"No authorization code received. Callback params: {callback}")
        sys.exit(1)

    if not realm_id:
        logger.error("No realmId received in callback. The QBO record needs realmId.")
        sys.exit(1)

    logger.info(f"Received auth code and realmId: {realm_id}")

    # Exchange code for tokens
    # https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0
    token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            auth=(client_id, client_secret),
        )

    if resp.status_code != 200:
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    token_data = resp.json()
    refresh_token = token_data["refresh_token"]
    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 3600)

    save_token("qbo", alias, refresh_token, access_token, expires_in, realm_id=realm_id)
    logger.info(f"QBO seed complete. realmId={realm_id}")
    logger.info("NOTE: QBO refresh tokens ROTATE on every use. The server persists "
                "rotated tokens automatically.")


# ──────────────────────────────────────────────────────────────
# Microsoft Graph
# ──────────────────────────────────────────────────────────────

async def seed_microsoft(alias: str = "main"):
    """Seed Microsoft Graph delegated OAuth tokens (SharePoint + Outlook)."""
    client_id = get_env("GRAPH_CLIENT_ID")
    client_secret = get_env("GRAPH_CLIENT_SECRET")
    tenant_id = get_env("TENANT_ID")

    # https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
    auth_url_base = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
    scope = "offline_access User.Read Sites.ReadWrite.All Files.ReadWrite.All Mail.ReadWrite Mail.Send Calendars.ReadWrite"

    # Use PKCE for security
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    params = urlencode({
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "response_mode": "query",
        "state": secrets.token_urlsafe(16),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{auth_url_base}?{params}"
    logger.info(f"Opening browser for Microsoft Graph sign-in...")
    webbrowser.open(auth_url)

    callback = await wait_for_callback(REDIRECT_PORT)
    code = callback.get("code")

    if not code:
        logger.error(f"No authorization code received. Callback: {callback}")
        sys.exit(1)

    logger.info("Received auth code, exchanging for tokens...")

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "scope": scope,
                "code_verifier": code_verifier,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    token_data = resp.json()
    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 3600)

    if not refresh_token:
        logger.error("No refresh token received. Ensure offline_access scope is granted.")
        sys.exit(1)

    save_token("microsoft", alias, refresh_token, access_token, expires_in)
    logger.info("Microsoft Graph seed complete. Covers SharePoint + Outlook mail + Outlook calendar.")


# ──────────────────────────────────────────────────────────────
# Google (Gmail + Calendar)
# ──────────────────────────────────────────────────────────────

async def seed_google(alias: str = "main"):
    """Seed Google OAuth tokens (Gmail + Calendar).

    IMPORTANT: https://mail.google.com/ is a RESTRICTED scope. An unverified
    ("testing") OAuth app issues refresh tokens that expire ~7 days.
    Move the OAuth app to "Production" in Google Cloud Console to avoid
    periodic re-auth. See README for details.
    """
    client_id = get_env("GOOGLE_CLIENT_ID")
    client_secret = get_env("GOOGLE_CLIENT_SECRET")

    # https://developers.google.com/identity/protocols/oauth2/web-server
    auth_url_base = "https://accounts.google.com/o/oauth2/v2/auth"
    scope = "https://mail.google.com/ https://www.googleapis.com/auth/calendar"

    # Use PKCE
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    params = urlencode({
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "access_type": "offline",  # Required for refresh token
        "prompt": "consent",  # Force consent to get a new refresh token
        "state": secrets.token_urlsafe(16),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{auth_url_base}?{params}"
    logger.info("Opening browser for Google sign-in...")
    logger.info("NOTE: Gmail scope is RESTRICTED. If the OAuth app is in 'Testing' mode, "
                "refresh tokens expire in ~7 days. Move to 'Production' to avoid this.")
    webbrowser.open(auth_url)

    callback = await wait_for_callback(REDIRECT_PORT)
    code = callback.get("code")

    if not code:
        logger.error(f"No authorization code received. Callback: {callback}")
        sys.exit(1)

    logger.info("Received auth code, exchanging for tokens...")

    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    token_data = resp.json()
    refresh_token = token_data.get("refresh_token")
    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 3600)

    if not refresh_token:
        logger.error("No refresh token received. Ensure access_type=offline and prompt=consent.")
        sys.exit(1)

    save_token("google", alias, refresh_token, access_token, expires_in)
    logger.info("Google seed complete. Covers Gmail + Google Calendar.")


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

PROVIDERS = {
    "qbo": seed_qbo,
    "microsoft": seed_microsoft,
    "google": seed_google,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROVIDERS:
        logger.error(f"Usage: python scripts/seed_oauth.py <provider>")
        logger.error(f"Providers: {', '.join(PROVIDERS.keys())}")
        logger.error(f"Optional: --alias <name> to use a non-default alias")
        sys.exit(1)

    provider = sys.argv[1]
    alias = "main"

    # Parse --alias
    if "--alias" in sys.argv:
        idx = sys.argv.index("--alias")
        if idx + 1 < len(sys.argv):
            alias = sys.argv[idx + 1]

    logger.info(f"Seeding {provider}:{alias} ...")
    asyncio.run(PROVIDERS[provider](alias))
    logger.info("Done.")


if __name__ == "__main__":
    main()