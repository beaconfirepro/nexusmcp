"""
GET /authorize/bridge — where the Nexus web app sends the owner back after
Approve or Deny (see src/bridge.py for the contract).
"""
import html
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse

from src.bridge import BridgeError, verify_assertion, verify_request
from src.connect_routes import start_microsoft_sign_in
from src.oauth_routes import deny_authorize, finish_authorize

logger = logging.getLogger("mcp_server.bridge_routes")


def _refused(message: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        f"<!DOCTYPE html><meta charset='utf-8'><title>Nexus</title>"
        f"<p style='font-family:sans-serif;padding:2rem'>{html.escape(message)}</p>",
        status_code=status_code,
    )


async def authorize_bridge(request: Request):
    s = request.app.state.settings
    q = request.query_params

    try:
        if q.get("error") == "access_denied":
            claims = verify_request(q.get("request", ""), s.JWT_SIGNING_KEY)
            if claims["kind"] == "authorize":
                return deny_authorize(claims["params"])
            return _refused("Cancelled. Nothing was connected.", 200)

        approval = verify_assertion(q.get("assertion", ""), s.NEXUS_BRIDGE_SECRET)
        claims = verify_request(approval["req"], s.JWT_SIGNING_KEY)
    except BridgeError as e:
        logger.warning("Refused bridge sign-in: %s", e)
        return _refused("This sign-in link is invalid or has expired. Please start again.", 400)

    logger.info("Bridge sign-in approved by %s for %s", approval["sub"], claims["kind"])
    if claims["kind"] == "authorize":
        return finish_authorize(claims["params"], owner=approval["sub"])
    if claims["kind"] == "connect_microsoft":
        return start_microsoft_sign_in(request, claims["alias"])
    raise BridgeError(f"unknown request kind {claims['kind']!r}")
