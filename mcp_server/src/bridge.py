"""
Sign-in through the Nexus web app (Base44) — replaces the owner password.

Flow (contract shared with the Base44 app's /mcp-authorize page and its
mcpAuthorize function):
  1. A server page that needs the owner (/authorize, /connect/microsoft) packs
     what it was asked to do into a short-lived JWT signed with JWT_SIGNING_KEY
     (the "request") and redirects to
     {NEXUS_APP_URL}/mcp-authorize?request=<request>&purpose=<text>.
  2. The Base44 app signs the user in (invite-only, admin role), shows
     Approve / Deny, and on Approve its mcpAuthorize function returns an
     assertion: base64url(payload_json) + "." + base64url(HMAC-SHA256), keyed
     with NEXUS_BRIDGE_SECRET, payload {sub, name, req, iat, exp}.
  3. The browser lands on GET /authorize/bridge?assertion=..., which checks the
     signature, the expiry, and that `req` is a request this server issued,
     then carries on with what the request says.
"""
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse

import jwt
from starlette.responses import RedirectResponse

logger = logging.getLogger("mcp_server.bridge")

REQUEST_TTL = 600  # seconds the owner has to sign in and approve
_REQUEST_AUDIENCE = "nexus-bridge-request"


class BridgeError(Exception):
    """An assertion or request that must not be honoured."""


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def sign_request(claims: dict, signing_key: str) -> str:
    """Pack what the server was asked to do; only this server can mint one."""
    now = int(time.time())
    return jwt.encode(
        {**claims, "aud": _REQUEST_AUDIENCE, "iat": now, "exp": now + REQUEST_TTL},
        signing_key, algorithm="HS256",
    )


def verify_request(token: str, signing_key: str) -> dict:
    try:
        return jwt.decode(token, signing_key, algorithms=["HS256"], audience=_REQUEST_AUDIENCE)
    except jwt.PyJWTError as e:
        raise BridgeError(f"request: {e}") from e


def verify_assertion(assertion: str, bridge_secret: str) -> dict:
    """The Base44 app's signed statement that an admin approved `req`."""
    try:
        payload_part, sig_part = assertion.split(".")
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(sig_part)
    except ValueError as e:
        raise BridgeError("assertion is malformed") from e
    expected = hmac.new(bridge_secret.encode(), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise BridgeError("assertion signature does not match")
    payload = json.loads(payload_bytes)
    if payload["exp"] < time.time():
        raise BridgeError("assertion has expired")
    return payload


def redirect_to_sign_in(settings, claims: dict, purpose: str) -> RedirectResponse:
    """Send the browser to the Nexus web app to sign in and approve."""
    request_token = sign_request(claims, settings.JWT_SIGNING_KEY)
    query = urllib.parse.urlencode({"request": request_token, "purpose": purpose})
    return RedirectResponse(f"{settings.NEXUS_APP_URL.rstrip('/')}/mcp-authorize?{query}", status_code=302)
