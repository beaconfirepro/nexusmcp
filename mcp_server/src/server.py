"""
Main server module — ties everything together.

Creates the FastMCP ASGI app, wraps it with Starlette to add:
  - GET /health: lightweight, UNAUTHENTICATED health check (no outbound calls)
  - BearerAuthMiddleware: validates INBOUND_TOKEN on every request except /health

The MCP endpoint is at /mcp. The bearer-token middleware protects it.

Identity separation (critical):
  - Managed identity (AZURE_CLIENT_ID) → Azure Table Storage ONLY
  - Inbound token → who may call this server
  - Outbound OAuth → how the server talks to providers (separate from both)
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

# ── Health check endpoint (UNAUTHENTICATED, no outbound calls) ──
async def health(request):
    """Lightweight liveness probe — returns 200 as soon as process is up + config loaded.
    Does NOT make any outbound provider calls (that would be slow, burn rate limits,
    trigger token refreshes, and misbehave under scale-to-zero).
    https://learn.microsoft.com/en-us/azure/container-apps/health-probes
    """
    return JSONResponse({"status": "ok", "version": VERSION})


# ── Build the outer Starlette app with auth middleware ──
# MCP app is mounted at / — it handles its own routing at /mcp internally.
# /health is defined first so it's matched before the mount catches everything.
app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_app),
    ],
    middleware=[
        Middleware(BearerAuthMiddleware, inbound_token=settings.INBOUND_TOKEN),
    ],
)

logger.info("MCP server ready. MCP endpoint: /mcp | Health check: /health")