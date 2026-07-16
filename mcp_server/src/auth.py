"""
Inbound auth middleware — OAuth 2.1 JWT validation for /mcp.

  - /health: OPEN (unauthenticated, for ACA liveness probes)
  - /status: requires STATUS_TOKEN (read-only, separate from OAuth)
  - OAuth endpoints (/authorize, /token, /register, /.well-known/*): OPEN
  - /mcp: requires a valid OAuth 2.1 JWT access token
  - Everything else: pass through (MCP app returns 404 for unknown paths)

When /mcp is requested without a valid token, returns 401 with
WWW-Authenticate: Bearer resource_metadata="<base>/.well-known/oauth-protected-resource"
per the MCP authorization spec.

Identity layers (critical):
  - Managed identity (AZURE_CLIENT_ID) → Azure Table Storage ONLY
  - OAuth JWT access token → who may call /mcp
  - Status token → read-only provider status (cannot invoke MCP tools)
  - Outbound OAuth → how the server talks to providers (separate from all above)
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.oauth_server import verify_access_token

logger = logging.getLogger("mcp_server.auth")

_OPEN_PATHS = frozenset({
    "/health",
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/register",
    "/authorize",
    "/token",
})


def _unauthorized_response(issuer: str) -> JSONResponse:
    resource_metadata = f"{issuer.rstrip('/')}/.well-known/oauth-protected-resource"
    return JSONResponse(
        {
            "error": "invalid_token",
            "error_description": "The access token is missing or invalid.",
        },
        status_code=401,
        headers={
            "WWW-Authenticate": f'Bearer resource_metadata="{resource_metadata}"',
        },
    )


class OAuthBearerAuthMiddleware(BaseHTTPMiddleware):
    """Validates OAuth 2.1 JWT access tokens on /mcp; open routes for /health and OAuth."""

    def __init__(self, app, status_token: str, jwt_signing_key: str, issuer: str, audience: str):
        super().__init__(app)
        self._status_expected = f"Bearer {status_token}"
        self._jwt_signing_key = jwt_signing_key
        self._issuer = issuer
        self._audience = audience

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Open paths: /health, OAuth endpoints
        if path in _OPEN_PATHS:
            return await call_next(request)

        # /status OPTIONS preflight (browser sends no Authorization)
        if path == "/status" and request.method == "OPTIONS":
            return await call_next(request)

        # /status: STATUS_TOKEN (never accepts OAuth tokens)
        if path == "/status":
            if request.headers.get("Authorization", "") != self._status_expected:
                logger.warning("Unauthorized /status request — invalid or missing status token")
                return JSONResponse(
                    {"error": "unauthorized", "message": "A valid status bearer token is required."},
                    status_code=401,
                )
            return await call_next(request)

        # /mcp: validate OAuth 2.1 JWT access token
        if path == "/mcp":
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning("Unauthorized /mcp request — missing Bearer token")
                return _unauthorized_response(self._issuer)
            token = auth_header[7:]
            claims = verify_access_token(token, self._issuer, self._audience, self._jwt_signing_key)
            if claims is None:
                logger.warning("Unauthorized /mcp request — invalid or expired JWT")
                return _unauthorized_response(self._issuer)
            return await call_next(request)

        # Everything else: pass through
        return await call_next(request)