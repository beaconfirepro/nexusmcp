"""
Main server module — ties everything together.

Creates the FastMCP ASGI app, wraps it with Starlette to add:
  - GET /health: lightweight, UNAUTHENTICATED health check (no outbound calls)
  - GET /status: live provider status, protected by STATUS_TOKEN (separate read-only token)
  - BearerAuthMiddleware: validates tokens per route

The MCP endpoint is at /mcp. The inbound bearer-token middleware protects it.
GET /status is protected by STATUS_TOKEN — it can never invoke MCP tools.

Identity separation (critical):
  - Managed identity (AZURE_CLIENT_ID) → Azure Table Storage ONLY
  - Inbound token → who may call this MCP server
  - Status token → read-only provider status (cannot invoke MCP tools)
  - Outbound OAuth → how the server talks to providers (separate from all above)
"""
import logging

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from src.auth import BearerAuthMiddleware
from src.clients import init_clients
from src.config import VERSION, load_settings
from src.mcp_instance import mcp
from src.status import get_all_provider_status

logger = logging.getLogger("mcp_server")

# ── Load config + init clients at startup (fail fast if env vars missing) ──
settings = load_settings()
init_clients(settings)
logger.info("Settings loaded and provider clients initialized.")

# ── Import tool modules to register their @mcp.tool() decorators ──
# Each module imports mcp from src.mcp_instance and registers tools at import time.
import tools.connecteam  # noqa: F401, E402
import tools.qbo  # noqa: F401, E402
import tools.hubspot  # noqa: F401, E402
import tools.graph  # noqa: F401, E402
import tools.google  # noqa: F401, E402
import tools.diagnostics  # noqa: F401, E402

# ── Get the FastMCP streamable HTTP ASGI app ──
# stateless_http=True is set in mcp_instance.py — no session state between requests.
# http_app() is the newer method; streamable_http_app() is the older name (deprecated in later v1.x).
# https://py.sdk.modelcontextprotocol.io/server/
try:
    mcp_app = mcp.http_app()
except AttributeError:
    mcp_app = mcp.streamable_http_app()

# ── CORS headers for /status (the status page is a different origin) ──
_STATUS_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization",
}


# ── Health check endpoint (UNAUTHENTICATED, no outbound calls) ──
async def health(request):
    """Lightweight liveness probe — returns 200 as soon as process is up + config loaded.
    Does NOT make any outbound provider calls (that would be slow, burn rate limits,
    trigger token refreshes, and misbehave under scale-to-zero).
    https://learn.microsoft.com/en-us/azure/container-apps/health-probes
    """
    return JSONResponse({"status": "ok", "version": VERSION})


# ── Provider status endpoint (requires STATUS_TOKEN, checked by middleware) ──
async def status(request):
    """Live provider status — configuration, seeding, reachability, scopes, expiry.
    Protected by STATUS_TOKEN (separate from INBOUND_TOKEN). Never leaks secrets.
    """
    if request.method == "OPTIONS":
        return JSONResponse({}, status_code=204, headers=_STATUS_CORS)
    result = await get_all_provider_status(settings)
    return JSONResponse(result, headers=_STATUS_CORS)


# ── Build the outer Starlette app with auth middleware ──
# MCP app is mounted at / — it handles its own routing at /mcp internally.
# /health and /status are defined before the mount so they're matched first.
app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/status", status, methods=["GET", "OPTIONS"]),
        Mount("/", app=mcp_app),
    ],
    middleware=[
        Middleware(
            BearerAuthMiddleware,
            inbound_token=settings.INBOUND_TOKEN,
            status_token=settings.STATUS_TOKEN,
        ),
    ],
)

logger.info("MCP server ready. MCP: /mcp | Health: /health | Status: /status")