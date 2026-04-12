"""Web routes for Google OAuth login flow."""
import html
import os
import logging
import requests as http_requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from .firestore_tokens import save_token

_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'none'",
}


def _html(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status_code, headers=_SECURITY_HEADERS)

logger = logging.getLogger(__name__)
router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "")
if not ALLOWED_DOMAIN:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "ALLOWED_DOMAIN is not set — any Google account can authenticate. "
        "Set ALLOWED_DOMAIN=yourcompany.com to restrict access."
    )
CLIENT_CONFIG_PATH = os.environ.get("OAUTH_CONFIG_PATH", "./client_secret.json")
BASE_URL = os.environ.get("BASE_URL", "")


def _make_flow(state=None):
    return Flow.from_client_secrets_file(
        CLIENT_CONFIG_PATH,
        scopes=SCOPES,
        redirect_uri=f"{BASE_URL}/auth/callback",
        state=state,
    )


@router.get("/login")
async def login(request: Request):
    flow = _make_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    request.session["oauth_state"] = state
    request.session["code_verifier"] = flow.code_verifier
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        return _html(f"<h2>Login cancelled: {html.escape(error)}</h2><a href='/auth/login'>Try again</a>")
    saved_state = request.session.get("oauth_state")
    if not state or state != saved_state:
        return _html("<h2>Security error: invalid state.</h2>", status_code=400)
    code_verifier = request.session.get("code_verifier")
    flow = _make_flow(state=state)
    flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    user_info = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    ).json()
    email = user_info.get("email", "")
    domain_part = email.split("@")[-1].lower() if "@" in email else ""
    if ALLOWED_DOMAIN and domain_part != ALLOWED_DOMAIN.lower():
        return _html(
            f"<h2>Access denied.</h2><p>Only @{html.escape(ALLOWED_DOMAIN)} accounts allowed.</p>"
            f"<p>Logged in as: {html.escape(email)}</p>",
            status_code=403,
        )
    save_token(email, creds)
    request.session["user_email"] = email
    logger.info(f"User logged in: {email}")
    return RedirectResponse("/auth/status")


@router.get("/status")
async def status(request: Request):
    email = request.session.get("user_email")
    if not email:
        return _html("<h2>Not logged in</h2><a href='/auth/login'><button>Login with Google</button></a>")
    return _html(
        f"<h2>Logged in as {html.escape(email)}</h2>"
        f"<p>Connect Claude to this MCP server.</p>"
        f"<p><a href='/auth/logout'>Logout</a></p>"
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return _html("<h2>Logged out.</h2><a href='/auth/login'>Login again</a>")
