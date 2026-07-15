"""
Inbound auth middleware — token-based access control.

  - /health: OPEN (unauthenticated, for ACA liveness probes)
  - /status: requires STATUS_TOKEN (read-only, separate from INBOUND_TOKEN)
  - /mcp and all other paths: requires INBOUND_TOKEN

STATUS_TOKEN unlocks ONLY /status — never the MCP tools.

Layer separation (critical):
  - Managed identity (AZURE_CLIENT_ID) → Azure Table Storage ONLY
  - Inbound token → who may call this MCP server
  - Status token → read-only provider status (cannot invoke MCP tools)
  - Outbound OAuth → how the server talks to providers (separate from all above)
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("mcp_server.auth")


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Validates bearer tokens on every request except /health."""

    def __init__(self, app, inbound_token: str, status_token: str):
        super().__init__(app)
        self._inbound_expected = f"Bearer {inbound_token}"
        self._status_expected = f"Bearer {status_token}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # /health is EXEMPT — must be lightweight and unauthenticated
        # https://learn.microsoft.com/en-us/azure/container-apps/health-probes
        if path == "/health":
            return await call_next(request)

        # OPTIONS preflight for /status is EXEMPT (browser sends no Authorization)
        if path == "/status" and request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        # /status accepts ONLY STATUS_TOKEN (never INBOUND_TOKEN)
        if path == "/status":
            if auth_header != self._status_expected:
                logger.warning("Unauthorized /status request — invalid or missing status token")
                return JSONResponse(
                    {"error": "unauthorized", "message": "A valid status bearer token is required."},
                    status_code=401,
                )
            return await call_next(request)

        # Everything else (including /mcp) requires INBOUND_TOKEN
        if auth_header != self._inbound_expected:
            logger.warning("Unauthorized request to %s — invalid or missing bearer token", path)
            return JSONResponse(
                {"error": "unauthorized", "message": "A valid bearer token is required."},
                status_code=401,
            )

        return await call_next(request)