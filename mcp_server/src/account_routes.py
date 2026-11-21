"""
QuickBooks Online account connection — lets the owner add and NAME QBO
companies from the Nexus web app instead of running scripts/seed_oauth.py.

Endpoints:
  - GET  /connect/qbo           — form (name, alias, access); the web app's
                                  "Add an account" sends all three as query params
  - POST /connect/qbo           — same, then the owner signs in on the Nexus web app
  - GET  /connect/qbo/callback  — exchange the code, store refresh token + realmId
  - GET  /accounts/remove       — owner-approved removal of one account

Gated by the owner's sign-in on the Nexus web app (see src/bridge.py): the server
is stateless, so what was asked travels in a short-lived signed cookie.

Requires this redirect URI on the Intuit app registration:
  <MCP_BASE_URL>/connect/qbo/callback
"""
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
from src.clients import get_token_store
from src.connect_routes import _base, _page
from src.token_store import ACCESS_READ_ONLY, ACCESS_READ_WRITE, ACCESS_MODES

logger = logging.getLogger("mcp_server.account_routes")

_QBO_SCOPE = "com.intuit.quickbooks.accounting"
_COOKIE = "qbo_connect"
_COOKIE_TTL = 600
_ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_REMOVABLE = ("qbo", "microsoft", "google")

_FORM = """<h1>🔗 Connect QuickBooks account</h1>
<p class="sub">Name this company, then sign in with the QuickBooks login that owns it.
The agent picks the account by this name and never sees the credentials.</p>
<form method="POST" action="{action}">
  <label for="name">Account name</label>
  <input type="text" id="name" name="name" value="{name}" placeholder="Acme Books" maxlength="60" required />
  <label for="alias">Alias</label>
  <input type="text" id="alias" name="alias" value="{alias}" placeholder="acme-books" pattern="[a-z0-9][a-z0-9_-]{{0,31}}" required />
  <label>Access</label>
  <label style="display:flex;gap:.5rem;align-items:center;font-weight:400;margin:.35rem 0">
    <input type="radio" name="mode" value="read_only" {ro} /> Read only
  </label>
  <label style="display:flex;gap:.5rem;align-items:center;font-weight:400;margin:.35rem 0">
    <input type="radio" name="mode" value="read_write" {rw} /> Read and write
  </label>
  <button type="submit">Sign in to Nexus, then QuickBooks</button>
</form>
{error}"""


def _redirect_uri(request: Request) -> str:
    return f"{_base(request)}/connect/qbo/callback"


def _form(
    request: Request,
    name: str = "",
    alias: str = "",
    mode: str = ACCESS_READ_ONLY,
    error: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return _page(
        _FORM.format(
            action=f"{_base(request)}/connect/qbo",
            name=html.escape(name),
            alias=html.escape(alias),
            ro="checked" if mode == ACCESS_READ_ONLY else "",
            rw="checked" if mode == ACCESS_READ_WRITE else "",
            error=err,
        ),
        status_code,
    )


def _account_list() -> str:
    accounts = get_token_store().list_accounts("qbo")
    if not accounts:
        return "<p class='sub'>No QuickBooks accounts are connected yet.</p>"
    rows = "".join(
        f"<li><strong>{html.escape(a['name'])}</strong> — "
        f"<code>qbo:{html.escape(a['alias'])}</code> "
        f"({'read only' if a['access_mode'] == ACCESS_READ_ONLY else 'read and write'})</li>"
        for a in accounts
    )
    return f"<ul style='margin:.5rem 0 0 1.1rem;font-size:.9rem'>{rows}</ul>"


async def connect_qbo(request: Request):
    s = request.app.state.settings

    if request.method == "GET":
        q = request.query_params
        name = q.get("name", "").strip()
        alias = q.get("alias", "").strip().lower()
        mode = q.get("mode", "").strip()
    else:
        form = await request.form()
        name = str(form.get("name", "")).strip()
        alias = str(form.get("alias", "")).strip().lower()
        mode = str(form.get("mode", "")).strip()

    if not (name and alias and mode):
        return _form(request, name, alias, mode or ACCESS_READ_ONLY)
    if not _ALIAS_RE.match(alias):
        return _form(request, name, alias, mode, "Alias must be 1-32 chars: lowercase letters, digits, '-' or '_'.", 400)
    if mode not in ACCESS_MODES:
        return _form(request, name, alias, mode, "Choose read only or read and write.", 400)
    if len(name) > 60:
        return _form(request, name, alias, mode, "Account name must be 60 characters or fewer.", 400)

    access = "read only" if mode == ACCESS_READ_ONLY else "read and write"
    return redirect_to_sign_in(
        s, {"kind": "connect_qbo", "alias": alias, "name": name, "mode": mode},
        purpose=f"Connect the QuickBooks account '{name}' to Nexus as qbo:{alias} ({access})",
    )


def start_qbo_sign_in(request: Request, alias: str, name: str, mode: str) -> RedirectResponse:
    """The owner approved on the Nexus web app: go on to QuickBooks sign-in."""
    s = request.app.state.settings
    state = secrets.token_urlsafe(16)

    params = urllib.parse.urlencode({
        "client_id": s.QBO_CLIENT_ID,
        "scope": _QBO_SCOPE,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "state": state,
    })
    cookie = jwt.encode(
        {"alias": alias, "name": name, "mode": mode, "state": state,
         "exp": int(time.time()) + _COOKIE_TTL},
        s.JWT_SIGNING_KEY, algorithm="HS256",
    )
    resp = RedirectResponse(f"{s.qbo_auth_url}?{params}", status_code=302)
    resp.set_cookie(
        _COOKIE, cookie, max_age=_COOKIE_TTL, httponly=True, samesite="lax",
        secure=_base(request).startswith("https://"), path="/connect/qbo",
    )
    return resp


async def connect_qbo_callback(request: Request):
    s = request.app.state.settings
    q = request.query_params

    if q.get("error"):
        msg = f"{q.get('error')}: {q.get('error_description', '')}"
        return _form(request, error=f"QuickBooks sign-in failed — {msg[:300]}", status_code=400)

    try:
        ctx = jwt.decode(request.cookies.get(_COOKIE, ""), s.JWT_SIGNING_KEY, algorithms=["HS256"])
    except Exception:
        return _form(request, error="Your session expired. Please start again.", status_code=400)

    if not q.get("code") or not secrets.compare_digest(q.get("state", ""), ctx["state"]):
        return _form(request, error="Invalid sign-in response (state mismatch). Please start again.", status_code=400)

    realm_id = q.get("realmId", "")
    if not realm_id:
        return _form(request, error="QuickBooks did not return a company id. Please start again.", status_code=502)

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            s.qbo_token_url,
            data={
                "grant_type": "authorization_code",
                "code": q["code"],
                "redirect_uri": _redirect_uri(request),
            },
            auth=(s.QBO_CLIENT_ID, s.QBO_CLIENT_SECRET),
        )
        if resp.status_code != 200:
            logger.error("QBO token exchange failed: %s", resp.status_code)
            return _form(request, error=f"Token exchange failed ({resp.status_code}). Check the Intuit redirect URI and client secret.", status_code=502)
        tok = resp.json()

    if not tok.get("refresh_token"):
        return _form(request, error="No refresh token returned. Please start again.", status_code=502)

    store = get_token_store()
    store.save_token(
        "qbo", ctx["alias"], tok["refresh_token"],
        tok.get("access_token"), tok.get("expires_in"),
        realm_id=realm_id, name=ctx["name"], access_mode=ctx["mode"],
    )
    logger.info("Connected qbo:%s (%s) realm %s", ctx["alias"], ctx["mode"], realm_id)

    access = "read only" if ctx["mode"] == ACCESS_READ_ONLY else "read and write"
    page = _page(
        f'<h1>✅ Connected</h1><p class="ok"><strong>{html.escape(ctx["name"])}</strong> is now '
        f'<code>qbo:{html.escape(ctx["alias"])}</code> ({access}).</p>'
        f'<p class="sub">QuickBooks accounts:</p>{_account_list()}'
        f'<p style="margin-top:1rem"><a href="{_base(request)}/connect/qbo">Connect another account</a>'
        f' &nbsp;·&nbsp; <a href="{s.NEXUS_APP_URL.rstrip("/")}/accounts">Back to Nexus Accounts</a></p>'
    )
    page.delete_cookie(_COOKIE, path="/connect/qbo")
    return page


async def remove_account(request: Request):
    """Owner-approved disconnect: deletes the account's stored credentials."""
    s = request.app.state.settings
    provider = request.query_params.get("provider", "").strip().lower()
    alias = request.query_params.get("alias", "").strip().lower()

    if provider not in _REMOVABLE or not alias:
        return _page("<h1>Remove an account</h1><p class='error'>Missing or unknown account.</p>", 400)

    return redirect_to_sign_in(
        s, {"kind": "remove_account", "provider": provider, "alias": alias},
        purpose=f"Disconnect {provider}:{alias} from Nexus — its stored credentials are deleted",
    )


def finish_remove_account(request: Request, provider: str, alias: str) -> HTMLResponse:
    s = request.app.state.settings
    if provider not in _REMOVABLE:
        return _page("<h1>Remove an account</h1><p class='error'>Unknown provider.</p>", 400)

    removed = get_token_store().delete_token(provider, alias)
    label = f"{html.escape(provider)}:{html.escape(alias)}"
    if removed:
        body = (
            f"<h1>🗑️ Disconnected</h1><p class='ok'>{label} was removed and its stored "
            f"credentials deleted.</p>"
        )
    else:
        body = f"<h1>Not found</h1><p class='sub'>No stored credentials for {label}.</p>"

    body += f'<p style="margin-top:1rem"><a href="{s.NEXUS_APP_URL.rstrip("/")}/accounts">Back to Nexus Accounts</a></p>'
    return _page(body, 200 if removed else 404)