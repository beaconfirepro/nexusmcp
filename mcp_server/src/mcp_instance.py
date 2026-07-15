"""
FastMCP instance — created once, imported by all tool modules.
stateless_http=True: no in-memory session state between requests
(safe for ACA scale-to-zero cold starts).

Also exports annotation presets for tool registration:
  RO            — read-only, openWorld (safe GET calls)
  WRITE         — non-destructive write, openWorld
  DESTRUCTIVE   — destructive write, openWorld
  IDEMPOTENT    — idempotent write (safe to retry), openWorld
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "multi-account-mcp",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Annotation presets — https://modelcontextprotocol.io/docs/concepts/tools#annotations
try:
    from mcp.types import ToolAnnotations

    RO = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
    WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)
    IDEMPOTENT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
except ImportError:
    RO = WRITE = DESTRUCTIVE = IDEMPOTENT = None