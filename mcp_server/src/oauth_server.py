"""
OAuth 2.1 Authorization Server — JWT and PKCE utilities.

  - JWT access token signing/verification (HS256)
  - PKCE S256 challenge verification

Spec references:
  - OAuth 2.1: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1
  - PKCE (RFC 7636): https://datatracker.ietf.org/doc/html/rfc7636
  - Auth Server Metadata (RFC 8414): https://datatracker.ietf.org/doc/html/rfc8414
  - Protected Resource Metadata (RFC 9728): https://datatracker.ietf.org/doc/html/rfc9728
  - MCP Authorization: https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
"""
import time
import hashlib
import base64
import secrets
import logging

import jwt

logger = logging.getLogger("mcp_server.oauth")

ACCESS_TOKEN_TTL = 3600  # 1 hour


def issue_access_token(issuer: str, subject: str, audience: str, signing_key: str) -> str:
    """Create a signed JWT access token (HS256)."""
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, signing_key, algorithm="HS256")


def verify_access_token(token: str, issuer: str, audience: str, signing_key: str) -> dict | None:
    """Verify a JWT access token. Returns claims dict or None."""
    try:
        return jwt.decode(
            token, signing_key, algorithms=["HS256"],
            issuer=issuer, audience=audience,
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT verification failed: %s", e)
        return None


def verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verify PKCE code_verifier against stored code_challenge (S256 only)."""
    if method != "S256":
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, code_challenge)