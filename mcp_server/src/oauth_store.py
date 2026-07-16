"""
In-memory store for OAuth 2.1 authorization server state.

Holds:
  - Registered clients (from Dynamic Client Registration)
  - Pending authorization codes (short-lived, single-use)
  - Active refresh tokens

In-memory: on container restart (e.g., ACA scale-to-zero), all state is lost.
The owner simply re-authenticates. Acceptable for a single-owner server.
"""
import time
import secrets
import logging

logger = logging.getLogger("mcp_server.oauth_store")

_clients: dict[str, dict] = {}
_auth_codes: dict[str, dict] = {}
_refresh_tokens: dict[str, dict] = {}

CODE_TTL = 600             # 10 minutes
REFRESH_TTL = 30 * 86400   # 30 days


def register_client(client_id, client_name, redirect_uris,
                     grant_types, response_types, token_endpoint_auth_method):
    _clients[client_id] = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "grant_types": grant_types,
        "response_types": response_types,
        "token_endpoint_auth_method": token_endpoint_auth_method,
    }
    logger.info("Registered OAuth client: %s (%s)", client_id, client_name)
    return _clients[client_id]


def get_client(client_id):
    return _clients.get(client_id)


def create_auth_code(client_id, redirect_uri, code_challenge, code_challenge_method):
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "expires_at": time.time() + CODE_TTL,
    }
    return code


def consume_auth_code(code):
    """Pop and return an auth code entry, or None if invalid/expired."""
    entry = _auth_codes.pop(code, None)
    if entry is None:
        return None
    if entry["expires_at"] < time.time():
        return None
    return entry


def create_refresh_token(client_id):
    token = secrets.token_urlsafe(48)
    _refresh_tokens[token] = {
        "client_id": client_id,
        "expires_at": time.time() + REFRESH_TTL,
    }
    return token


def validate_refresh_token(token, client_id):
    entry = _refresh_tokens.get(token)
    if entry is None:
        return False
    if entry["expires_at"] < time.time():
        _refresh_tokens.pop(token, None)
        return False
    return entry["client_id"] == client_id


def revoke_refresh_token(token):
    _refresh_tokens.pop(token, None)