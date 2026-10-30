"""
Browser-based Microsoft account connection — lets the owner add Outlook /
SharePoint logins (aliases) without running scripts/seed_oauth.py locally.

Endpoints:
  - GET  /connect/microsoft            — form: alias
  - POST /connect/microsoft            — check alias, send the owner to sign in on the Nexus web app
  - (via /authorize/bridge)            — approved: redirect to Microsoft sign-in
  - GET  /connect/microsoft/callback   — exchange code, store refresh token under the alias

Gated by the owner's sign-in on the Nexus web app (same as /authorize, see
src/bridge.py). The server is stateless, so
the PKCE verifier and state travel in a short-lived signed, HttpOnly cookie.

Requires this redirect URI on the Entra app registration:
  <MCP_BASE_URL>/connect/microsoft/callback
"""
import base64
import hashlib
import html
import logging
import re
import secrets
import time
import urllib.parse

import httpx
import jwt
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from src.bridge import redirect_to_sign_in
from src.clients import get_oauth_config, get_token_store

logger = logging.getLogger("mcp_server.connect_routes")

_COOKIE = "ms_connect"
_COOKIE_TTL = 600
_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NexusMCP — Connect Microsoft Account</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
.card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 2.5rem; width: 100%; max-width: 420px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }}
h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: #f8fafc; }}
p.sub {{ font-size: 0.875rem; color: #94a3b8; margin-bottom: 1.5rem; }}
label {{ display: block; font-size: 0.8rem; font-weight: 500; color: #cbd5e1; margin: 1rem 0 0.5rem; }}
input[type=text] {{ width: 100%; padding: 0.75rem 1rem; border: 1px solid #475569; border-radius: 8px; background: #0f172a; color: #f1f5f9; font-size: 1rem; }}
input:focus {{ outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }}
button {{ width: 100%; padding: 0.75rem; border: none; border-radius: 8px; background: #3b82f6; color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer; margin-top: 1.5rem; }}
button:hover {{ background: #2563eb; }}
.error {{ color: #f87171; font-size: 0.85rem; margin-top: 1rem; }}
.ok {{ color: #4ade80; font-size: 0.95rem; margin-bottom: 1rem; }}
a {{ color: #60a5fa; }}
code {{ background: #0f172a; padding: 0.1rem 0.4rem; border-radius: 4px; }}
</style>
</head>
<body><div class="card">{body}</div></body>
</html>"""

_FORM = """<h1>🔗 Connect Microsoft account</h1>
<p class="sub">Adds an Outlook / SharePoint login. Pick the alias you will pass as
<code>account</code> (e.g. <code>microsoft:work2</code>), then sign in with that account.</p>
<form method="POST" action="{action}">
  <label for="alias">Alias</label>
  <input type="text" id="alias" name="alias" value="{alias}" placeholder="work2" pattern="[a-z0-9][a-z0-9_-]{{0,31}}" required />
  <button type="submit">Sign in to Nexus, then Microsoft</button>
</form>
{error}"""


def _base(request: Request) -> str:
    return request.app.state.settings.MCP_BASE_URL.rstrip("/")


def _redirect_uri(request: Request) -> str:
    return f"{_base(request)}/connect/microsoft/callback"


def _page(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(body=body), status_code=status_code)


def _form(request: Request, alias: str = "", error: str = "", status_code: int = 200) -> HTMLResponse:
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return _page(
        _FORM.format(action=f"{_base(request)}/connect/microsoft", alias=html.escape(alias), error=err),
        status_code,
    )


async def connect_microsoft(request: Request):
    s = request.app.state.settings

    if request.method == "GET":
        return _form(request)

    form = await request.form()
    alias = str(form.get("alias", "")).strip().lower()
    if not _ALIAS_RE.match(alias):
        return _form(request, alias, "Alias must be 1-32 chars: lowercase letters, digits, '-' or '_'.", 400)

    return redirect_to_sign_in(
        s, {"kind": "connect_microsoft", "alias": alias},
        purpose=f"Connect a Microsoft account to Nexus as microsoft:{alias}",
    )


def start_microsoft_sign_in(request: Request, alias: str) -> RedirectResponse:
    """The owner approved on the Nexus web app: go on to Microsoft sign-in."""
    s = request.app.state.settings
    code_verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(16)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    cfg = get_oauth_config("microsoft")
    params = urllib.parse.urlencode({
        "client_id": s.GRAPH_CLIENT_ID,
        "scope": cfg.scope,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "response_mode": "query",
        "prompt": "select_account",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })

    cookie = jwt.encode(
        {"alias": alias, "v": code_verifier, "state": state, "exp": int(time.time()) + _COOKIE_TTL},
        s.JWT_SIGNING_KEY, algorithm="HS256",
    )
    resp = RedirectResponse(f"{s.graph_auth_url}?{params}", status_code=302)
    resp.set_cookie(
        _COOKIE, cookie, max_age=_COOKIE_TTL, httponly=True, samesite="lax",
        secure=_base(request).startswith("https://"), path="/connect/microsoft",
    )
    return resp


async def connect_microsoft_callback(request: Request):
    s = request.app.state.settings
    q = request.query_params

    if q.get("error"):
        msg = f"{q.get('error')}: {q.get('error_description', '')}"
        return _form(request, error=f"Microsoft sign-in failed — {msg[:300]}", status_code=400)

    try:
        ctx = jwt.decode(request.cookies.get(_COOKIE, ""), s.JWT_SIGNING_KEY, algorithms=["HS256"])
    except Exception:
        return _form(request, error="Your session expired. Please start again.", status_code=400)

    if not q.get("code") or not secrets.compare_digest(q.get("state", ""), ctx["state"]):
        return _form(request, error="Invalid sign-in response (state mismatch). Please start again.", status_code=400)

    cfg = get_oauth_config("microsoft")
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(s.graph_token_url, data={
            "client_id": s.GRAPH_CLIENT_ID,
            "client_secret": s.GRAPH_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": q["code"],
            "redirect_uri": _redirect_uri(request),
            "scope": cfg.scope,
            "code_verifier": ctx["v"],
        })
        if resp.status_code != 200:
            logger.error("Microsoft token exchange failed: %s", resp.status_code)
            return _form(request, error=f"Token exchange failed ({resp.status_code}). Check the Entra redirect URI and app secret.", status_code=502)
        tok = resp.json()
        if not tok.get("refresh_token"):
            return _form(request, error="No refresh token returned. Ensure offline_access is granted.", status_code=502)

        who = ""
        me = await http.get(f"{s.graph_base_url}/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
        if me.status_code == 200:
            j = me.json()
            who = j.get("userPrincipalName") or j.get("mail") or ""

    alias = ctx["alias"]
    store = get_token_store()
    store.save_token("microsoft", alias, tok["refresh_token"], tok.get("access_token"), tok.get("expires_in"))
    logger.info("Connected microsoft:%s via browser (%s)", alias, who or "unknown user")

    aliases = ", ".join(f"<code>microsoft:{html.escape(a)}</code>" for a in sorted(store.list_aliases("microsoft")))
    resp = _page(
        f'<h1>✅ Connected</h1><p class="ok">{html.escape(who or "Account")} is now '
        f'<code>microsoft:{html.escape(alias)}</code>.</p>'
        f'<p class="sub">All Microsoft accounts: {aliases}</p>'
        f'<a href="{_base(request)}/connect/microsoft">Connect another account</a>'
    )
    resp.delete_cookie(_COOKIE, path="/connect/microsoft")
    return resp
