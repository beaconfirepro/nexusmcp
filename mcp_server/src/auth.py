"""
Inbound auth middleware — validates a single bearer token on every MCP request.
EXEMPTS /health (must be unauthenticated and lightweight for ACA probes).
The token model is structured so per-user tokens could be added later,
but this ships the single-token version.

Layer separation (critical):
  - Managed identity (AZURE_CLIENT_ID) → Azure Table Storage ONLY
  - This inbound token → who may call the MCP server
  - Outbound OAuth → how the server talks to providers (separate from both above)
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("mcp_server.auth")


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Validates INBOUND_TOKEN bearer token on every request except /health."""

    def __init__(self, app, inbound_token: str):
        super().__init__(app)
        self._expected = f"Bearer {inbound_token}"

    async def dispatch(self, request: Request, call_next):
        # /health is EXEMPT — must be lightweight and unauthenticated
        # https://learn.microsoft.com/en-us/azure/container-apps/health-probes
        if request.url.path == "/health":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        if auth_header != self._expected:
            logger.warning("Unauthorized request to %s — invalid or missing bearer token", request.url.path)
            return JSONResponse(
                {"error": "unauthorized", "message": "A valid bearer token is required."},
                status_code=401,
            )

        return await call_next(request)