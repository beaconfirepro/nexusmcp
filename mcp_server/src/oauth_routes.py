"""
OAuth 2.1 Authorization Server — Starlette route handlers.

Endpoints:
  - GET  /.well-known/oauth-authorization-server  — AS metadata (RFC 8414)
  - GET  /.well-known/oauth-protected-resource     — PR metadata (RFC 9728)
  - POST /register                                  — Dynamic Client Registration (RFC 7591)
  - GET  /authorize                                 — Authorization endpoint (sends the owner to
                                                      the Nexus web app to sign in; see src/bridge.py)
  - POST /token                                     — Token endpoint (code + refresh grants)
"""
import secrets
import logging
import urllib.parse

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from src.bridge import redirect_to_sign_in
from src.oauth_server import issue_access_token, verify_pkce, ACCESS_TOKEN_TTL
from src.oauth_store import (
    register_client,
    create_auth_code, consume_auth_code,
    create_refresh_token, validate_refresh_token, revoke_refresh_token,
)

logger = logging.getLogger("mcp_server.oauth_routes")


def _base_url(settings) -> str:
    return settings.MCP_BASE_URL.rstrip("/")


def _audience(settings) -> str:
    return f"{_base_url(settings)}/mcp"


# ── Authorization Server Metadata (RFC 8414) ──
async def authorization_server_metadata(request: Request):
    s = request.app.state.settings
    base = _base_url(s)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "revocation_endpoint": f"{base}/token",
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "scopes_supported": [],
    })


# ── Protected Resource Metadata (RFC 9728) ──
async def protected_resource_metadata(request: Request):
    s = request.app.state.settings
    base = _base_url(s)
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    })


# ── Dynamic Client Registration (RFC 7591) ──
async def register(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "invalid_client_metadata", "error_description": "Malformed JSON"},
            status_code=400,
        )

    client_id = secrets.token_urlsafe(16)
    redirect_uris = body.get("redirect_uris", [])
    client_name = body.get("client_name", "unnamed")
    grant_types = body.get("grant_types", ["authorization_code", "refresh_token"])
    response_types = body.get("response_types", ["code"])
    token_endpoint_auth_method = body.get("token_endpoint_auth_method", "none")

    register_client(
        client_id, client_name, redirect_uris,
        grant_types, response_types, token_endpoint_auth_method,
    )

    return JSONResponse({
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "grant_types": grant_types,
        "response_types": response_types,
        "token_endpoint_auth_method": token_endpoint_auth_method,
    }, status_code=201)


# ── Authorization Endpoint ──
# The owner signs in on the Nexus web app (Base44), not here: see src/bridge.py.
async def authorize(request: Request):
    s = request.app.state.settings
    params = dict(request.query_params)
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    response_type = params.get("response_type")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method", "S256")

    if not all([client_id, redirect_uri, response_type, code_challenge]):
        return JSONResponse(
            {"error": "invalid_request",
             "error_description": "Missing required parameters (client_id, redirect_uri, response_type, code_challenge)"},
            status_code=400,
        )
    if response_type != "code":
        return JSONResponse(
            {"error": "unsupported_response_type", "error_description": "Only 'code' is supported"},
            status_code=400,
        )
    if code_challenge_method != "S256":
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Only S256 code_challenge_method is supported"},
            status_code=400,
        )

    return redirect_to_sign_in(
        s, {"kind": "authorize", "params": params},
        purpose=f"Connect an AI client to Nexus ({params.get('client_id')})",
    )


def _redirect_with(redirect_uri: str, query: dict) -> RedirectResponse:
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urllib.parse.urlencode(query)}", status_code=302)


def finish_authorize(params: dict, owner: str) -> RedirectResponse:
    """The owner approved: issue the code and send it to the client."""
    code = create_auth_code(
        params.get("client_id"),
        params.get("redirect_uri"),
        params.get("code_challenge"),
        params.get("code_challenge_method", "S256"),
    )
    logger.info("Authorized client %s for %s", params.get("client_id"), owner)
    query = {"code": code}
    if params.get("state"):
        query["state"] = params["state"]
    return _redirect_with(params["redirect_uri"], query)


def deny_authorize(params: dict) -> RedirectResponse:
    query = {"error": "access_denied"}
    if params.get("state"):
        query["state"] = params["state"]
    return _redirect_with(params["redirect_uri"], query)


# ── Token Endpoint ──
async def token(request: Request):
    s = request.app.state.settings
    base = _base_url(s)
    aud = _audience(s)

    form = await request.form()
    grant_type = form.get("grant_type", "")

    # ── authorization_code grant ──
    if grant_type == "authorization_code":
        code = form.get("code", "")
        code_verifier = form.get("code_verifier", "")
        client_id = form.get("client_id", "")
        redirect_uri = form.get("redirect_uri", "")

        entry = consume_auth_code(code)
        if entry is None:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
                status_code=400,
            )
        if entry["client_id"] != client_id:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Client ID mismatch"},
                status_code=400,
            )
        if entry["redirect_uri"] != redirect_uri:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Redirect URI mismatch"},
                status_code=400,
            )
        if not verify_pkce(code_verifier, entry["code_challenge"], entry["code_challenge_method"]):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                status_code=400,
            )

        access_token = issue_access_token(
            issuer=base, subject="owner", audience=aud, signing_key=s.JWT_SIGNING_KEY,
        )
        refresh_token = create_refresh_token(client_id)

        logger.info("Issued access token for client %s", client_id)
        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL,
            "refresh_token": refresh_token,
        })

    # ── refresh_token grant ──
    if grant_type == "refresh_token":
        refresh_token = form.get("refresh_token", "")
        client_id = form.get("client_id", "")

        if not validate_refresh_token(refresh_token, client_id):
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid refresh token"},
                status_code=400,
            )

        # Rotate: revoke old, issue new
        revoke_refresh_token(refresh_token)
        new_access = issue_access_token(
            issuer=base, subject="owner", audience=aud, signing_key=s.JWT_SIGNING_KEY,
        )
        new_refresh = create_refresh_token(client_id)

        return JSONResponse({
            "access_token": new_access,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL,
            "refresh_token": new_refresh,
        })

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)