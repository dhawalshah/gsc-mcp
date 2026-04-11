# Google Search Console MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted GSC MCP server deployable to Google Cloud Run with SSE transport, matching the team's GA4/Ads MCP pattern, with 24+ tools covering search analytics, URL inspection, sitemaps, sites, and composite analysis.

**Architecture:** FastMCP + FastAPI wrapper with SSE transport; per-user OAuth 2.0 tokens stored in Firestore; domain-restricted login via `/auth/login`; audit logging via Cloud Logging; in-memory rate limiting (10 req/min/user).

**Tech Stack:** Python 3.11, fastmcp>=2.0.0, FastAPI, uvicorn, google-auth, google-auth-oauthlib, google-cloud-firestore, google-cloud-logging, python-dotenv, requests

---

## File Map

| File | Responsibility |
|------|---------------|
| `server.py` | FastMCP instance; imports and registers all tools from `gsc/` |
| `main.py` | FastAPI app, session middleware, auth routes, MCP mount, login guard |
| `oauth/google_auth.py` | ContextVar, token load (Firestore or local file), auto-refresh |
| `oauth/auth_routes.py` | `/auth/login`, `/auth/callback`, `/auth/status`, `/auth/logout` |
| `oauth/firestore_tokens.py` | Firestore CRUD for per-user OAuth tokens |
| `gsc/client.py` | `gsc_get()` / `gsc_post()` helpers, `format_response()`, rate limiter, audit log |
| `gsc/sites.py` | `list_properties`, `get_site_details` |
| `gsc/search_analytics.py` | `get_search_analytics`, `get_performance_overview`, `compare_periods`, `batch_search_analytics`, `get_position_band_report`, `get_ctr_optimization_report`, `get_keyword_cannibalization` |
| `gsc/url_inspection.py` | `inspect_url`, `batch_url_inspection` |
| `gsc/sitemaps.py` | `list_sitemaps`, `get_sitemap`, `submit_sitemap`, `delete_sitemap` |
| `gsc/composite.py` | `analyze_site_health`, `identify_quick_wins`, `export_full_dataset`, `crawl_error_summary`, `property_migration_checklist` |
| `setup_local_auth.py` | One-shot local OAuth token saver (STDIO dev mode) |
| `manifest.json` | MCP registry metadata |
| `Dockerfile` | Cloud Run container |
| `tests/test_auth.py` | Auth module unit tests |
| `tests/test_sites.py` | Sites tools unit tests |
| `tests/test_search_analytics.py` | Search analytics unit tests |
| `tests/test_url_inspection.py` | URL inspection unit tests |
| `tests/test_sitemaps.py` | Sitemaps unit tests |
| `tests/test_composite.py` | Composite tools unit tests |

---

## Task 1: Scaffold + Clone Reference Repo

**> This is when to clone the AminForou/mcp-gsc repo. See step below.**

**Files:**
- Create: `gsc/__init__.py`, `oauth/__init__.py`, `tests/__init__.py`
- Create: `requirements.txt`, `.env.example`, `client_secret.json.example`

- [ ] **Step 1: Clone the reference repo for API pattern reference**

```bash
# In a SEPARATE directory — this is reference only, not our project
git clone https://github.com/AminForou/mcp-gsc /tmp/mcp-gsc-reference
```

Keep this open in a second terminal window. We reference its API call patterns (request bodies, URL encoding, field names) but do NOT copy its architecture — it uses STDIO transport and a different structure.

- [ ] **Step 2: Create directory structure in the project**

```bash
mkdir -p gsc oauth tests
touch gsc/__init__.py oauth/__init__.py tests/__init__.py
```

- [ ] **Step 3: Create requirements.txt**

```
# Core MCP framework
fastmcp>=2.0.0

# Web server
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
starlette>=0.36.0
itsdangerous>=2.1.0

# Google Auth
google-auth>=2.28.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
requests>=2.31.0

# Firestore (token storage)
google-cloud-firestore>=2.14.0

# Environment variables
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 4: Create .env.example**

```bash
# .env.example — copy to .env for local development
GCP_PROJECT_ID=your-project-id
OAUTH_CONFIG_PATH=./client_secret.json
ALLOWED_DOMAIN=yourcompany.com
BASE_URL=http://localhost:8080
SESSION_SECRET_KEY=dev-secret-change-me
# MCP_USER_EMAIL=you@yourcompany.com  # STDIO local mode only
```

- [ ] **Step 5: Create client_secret.json.example**

```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["https://gsc-mcp-YOURPROJECT.asia-southeast1.run.app/auth/callback"],
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 7: Commit scaffold**

```bash
git init
git add .
git commit -m "feat: scaffold GSC MCP project structure"
```

---

## Task 2: OAuth Module

**Files:**
- Create: `oauth/firestore_tokens.py`
- Create: `oauth/google_auth.py`
- Create: `oauth/auth_routes.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing auth tests**

```python
# tests/test_auth.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_get_headers_uses_firestore_when_context_var_set():
    from oauth.google_auth import current_user_email, get_headers_with_auto_token
    mock_creds = MagicMock()
    mock_creds.token = "firestore-token"
    with patch("oauth.google_auth.load_token", return_value=mock_creds):
        token = current_user_email.set("user@example.com")
        try:
            headers = get_headers_with_auto_token()
        finally:
            current_user_email.reset(token)
    assert headers["Authorization"] == "Bearer firestore-token"


def test_get_headers_uses_local_token_when_env_var_set():
    from oauth.google_auth import get_headers_with_auto_token
    mock_creds = MagicMock()
    mock_creds.token = "local-token"
    with patch.dict(os.environ, {"MCP_USER_EMAIL": "user@example.com"}):
        with patch("oauth.google_auth.load_local_token", return_value=mock_creds):
            headers = get_headers_with_auto_token()
    assert headers["Authorization"] == "Bearer local-token"


def test_get_headers_raises_when_no_auth():
    from oauth.google_auth import get_headers_with_auto_token
    env = {k: v for k, v in os.environ.items() if k != "MCP_USER_EMAIL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="No authenticated user"):
            get_headers_with_auto_token()


def test_load_local_token_returns_none_when_file_missing(tmp_path):
    from oauth import google_auth
    with patch.object(google_auth, "LOCAL_TOKEN_PATH", tmp_path / "nonexistent.json"):
        result = google_auth.load_local_token(["https://www.googleapis.com/auth/webmasters.readonly"])
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: `ModuleNotFoundError: No module named 'oauth.google_auth'`

- [ ] **Step 3: Create oauth/firestore_tokens.py**

```python
"""Per-user OAuth token storage in Firestore."""
import json
import os
import logging
from google.cloud import firestore
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

logger = logging.getLogger(__name__)
COLLECTION = "user_tokens_gsc"


def _db():
    return firestore.Client(project=os.environ["GCP_PROJECT_ID"])


def save_token(user_email: str, creds: Credentials):
    _db().collection(COLLECTION).document(user_email).set({
        "token_json": creds.to_json(),
        "updated_at": firestore.SERVER_TIMESTAMP,
    })
    logger.info(f"Saved token for {user_email}")


def load_token(user_email: str, scopes: list):
    doc = _db().collection(COLLECTION).document(user_email).get()
    if not doc.exists:
        logger.warning(f"No token found for {user_email}")
        return None
    token_json = doc.to_dict().get("token_json")
    creds = Credentials.from_authorized_user_info(json.loads(token_json), scopes)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            logger.info(f"Refreshing token for {user_email}")
            creds.refresh(Request())
            save_token(user_email, creds)
            return creds
        except RefreshError:
            logger.warning(f"Token refresh failed for {user_email} — re-login required")
            return None
    return None
```

- [ ] **Step 4: Create oauth/google_auth.py**

```python
"""GSC OAuth authentication — HTTP server mode (Firestore) and STDIO local mode."""
import json
import os
import contextvars
import logging
from pathlib import Path
from typing import Dict, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from .firestore_tokens import load_token

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

LOCAL_TOKEN_PATH = Path.home() / ".config" / "google-search-console-mcp" / "token.json"

current_user_email: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_user_email", default=None
)


def load_local_token(scopes: list) -> Optional[Credentials]:
    if not LOCAL_TOKEN_PATH.exists():
        logger.warning(f"Local token file not found: {LOCAL_TOKEN_PATH}")
        return None
    try:
        token_data = json.loads(LOCAL_TOKEN_PATH.read_text())
        creds = Credentials.from_authorized_user_info(token_data, scopes)
    except Exception as e:
        logger.warning(f"Failed to load local token: {e}")
        return None
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            LOCAL_TOKEN_PATH.write_text(creds.to_json())
            return creds
        except RefreshError:
            logger.warning("Local token refresh failed — re-run setup_local_auth.py")
            return None
    return None


def get_headers_with_auto_token() -> Dict[str, str]:
    email = current_user_email.get()
    if email:
        creds = load_token(email, SCOPES)
        if not creds:
            raise ValueError(f"No valid token for {email}. Visit /auth/login first.")
        return {"Authorization": f"Bearer {creds.token}"}

    local_email = os.environ.get("MCP_USER_EMAIL")
    if local_email:
        creds = load_local_token(SCOPES)
        if not creds:
            raise ValueError("Local token invalid. Run: python setup_local_auth.py")
        return {"Authorization": f"Bearer {creds.token}"}

    raise ValueError(
        "No authenticated user. "
        "HTTP mode: visit /auth/login. "
        "STDIO mode: set MCP_USER_EMAIL env var and run setup_local_auth.py."
    )
```

- [ ] **Step 5: Create oauth/auth_routes.py**

```python
"""Web routes for Google OAuth login flow."""
import os
import logging
import requests as http_requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from .firestore_tokens import save_token

logger = logging.getLogger(__name__)
router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "")
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
        return HTMLResponse(f"<h2>Login cancelled: {error}</h2><a href='/auth/login'>Try again</a>")
    saved_state = request.session.get("oauth_state")
    if not state or state != saved_state:
        return HTMLResponse("<h2>Security error: invalid state.</h2>", status_code=400)
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
    if ALLOWED_DOMAIN and not email.endswith(f"@{ALLOWED_DOMAIN}"):
        return HTMLResponse(
            f"<h2>Access denied.</h2><p>Only @{ALLOWED_DOMAIN} accounts allowed.</p>"
            f"<p>Logged in as: {email}</p>",
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
        return HTMLResponse("<h2>Not logged in</h2><a href='/auth/login'><button>Login with Google</button></a>")
    return HTMLResponse(
        f"<h2>Logged in as {email}</h2>"
        f"<p>Connect Claude to this MCP server.</p>"
        f"<p><a href='/auth/logout'>Logout</a></p>"
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return HTMLResponse("<h2>Logged out.</h2><a href='/auth/login'>Login again</a>")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add oauth/ tests/test_auth.py
git commit -m "feat: add OAuth module with Firestore token storage"
```

---

## Task 3: Shared GSC Client

**Files:**
- Create: `gsc/client.py`

- [ ] **Step 1: Create gsc/client.py**

```python
"""Shared GSC API client: request helpers, response formatter, rate limiter, audit log."""
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

from oauth.google_auth import get_headers_with_auto_token, current_user_email

logger = logging.getLogger("gsc_audit")

GSC_BASE = "https://www.googleapis.com/webmasters/v3"
INSPECT_BASE = "https://searchconsole.googleapis.com/v1"

# Rate limiting: 10 requests per minute per user
_rate_windows: dict = defaultdict(list)
RATE_LIMIT = 10
RATE_WINDOW = 60  # seconds


def _check_rate_limit(email: str):
    now = time.time()
    window = [t for t in _rate_windows[email] if now - t < RATE_WINDOW]
    if len(window) >= RATE_LIMIT:
        raise RuntimeError(
            f"Rate limit exceeded: {RATE_LIMIT} requests/minute. Please wait before retrying."
        )
    window.append(now)
    _rate_windows[email] = window


def _audit(tool: str, site_url: str = ""):
    email = current_user_email.get() or "local"
    logger.info(json.dumps({
        "tool": tool,
        "site_url": site_url,
        "user": email,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


def _encode_site(site_url: str) -> str:
    """URL-encode site URL for use in GSC API paths."""
    return quote(site_url, safe="")


def gsc_get(path: str, params: Optional[Dict] = None, site_url: str = "") -> Dict:
    """GET request to GSC webmasters API."""
    email = current_user_email.get() or ""
    _check_rate_limit(email)
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.get(url, headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def gsc_post(path: str, body: Dict, site_url: str = "") -> Dict:
    """POST request to GSC webmasters API."""
    email = current_user_email.get() or ""
    _check_rate_limit(email)
    headers = get_headers_with_auto_token()
    headers["Content-Type"] = "application/json"
    url = f"{GSC_BASE}/{path}"
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


def gsc_put(path: str, site_url: str = "") -> Dict:
    """PUT request to GSC webmasters API (for add site / submit sitemap)."""
    email = current_user_email.get() or ""
    _check_rate_limit(email)
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.put(url, headers=headers)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def gsc_delete(path: str, site_url: str = "") -> Dict:
    """DELETE request to GSC webmasters API."""
    email = current_user_email.get() or ""
    _check_rate_limit(email)
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.delete(url, headers=headers)
    resp.raise_for_status()
    return {}


def inspect_post(body: Dict) -> Dict:
    """POST request to URL Inspection API v1."""
    email = current_user_email.get() or ""
    _check_rate_limit(email)
    headers = get_headers_with_auto_token()
    headers["Content-Type"] = "application/json"
    url = f"{INSPECT_BASE}/urlInspection/index:inspect"
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


def format_response(
    data: Any,
    site_url: str = "",
    date_range: Optional[list] = None,
    rows_returned: Optional[int] = None,
    rows_available: Optional[int] = None,
) -> Dict:
    return {
        "success": True,
        "data": data,
        "metadata": {
            "property": site_url,
            "date_range": date_range,
            "rows_returned": rows_returned,
            "rows_available": rows_available,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "error": None,
    }


def format_error(message: str, error_code: str = "API_ERROR") -> Dict:
    return {
        "success": False,
        "data": None,
        "error": message,
        "error_code": error_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 2: Commit**

```bash
git add gsc/client.py
git commit -m "feat: add shared GSC API client with rate limiting and audit logging"
```

---

## Task 4: Sites Tools

**Files:**
- Create: `gsc/sites.py`
- Create: `tests/test_sites.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sites.py
import pytest
from unittest.mock import patch, MagicMock


def test_list_properties_returns_sites():
    from gsc.sites import list_properties
    mock_resp = {
        "siteEntry": [
            {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
            {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteFullUser"},
        ]
    }
    with patch("gsc.sites.gsc_get", return_value=mock_resp):
        result = list_properties()
    assert result["success"] is True
    assert len(result["data"]["sites"]) == 2
    assert result["data"]["sites"][0]["siteUrl"] == "https://example.com/"
    assert result["data"]["sites"][0]["permissionLevel"] == "siteOwner"


def test_list_properties_empty():
    from gsc.sites import list_properties
    with patch("gsc.sites.gsc_get", return_value={}):
        result = list_properties()
    assert result["success"] is True
    assert result["data"]["sites"] == []


def test_get_site_details_returns_details():
    from gsc.sites import get_site_details
    mock_resp = {
        "siteUrl": "https://example.com/",
        "permissionLevel": "siteOwner",
    }
    with patch("gsc.sites.gsc_get", return_value=mock_resp):
        result = get_site_details("https://example.com/")
    assert result["success"] is True
    assert result["data"]["siteUrl"] == "https://example.com/"


def test_get_site_details_api_error():
    from gsc.sites import get_site_details
    import requests
    with patch("gsc.sites.gsc_get", side_effect=requests.HTTPError("404")):
        result = get_site_details("https://notfound.com/")
    assert result["success"] is False
    assert "404" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sites.py -v
```

Expected: `ModuleNotFoundError: No module named 'gsc.sites'`

- [ ] **Step 3: Create gsc/sites.py**

```python
"""GSC Sites (property) tools."""
from typing import Any, Dict
from .client import gsc_get, gsc_delete, gsc_put, format_response, format_error, _encode_site, _audit


def list_properties() -> Dict:
    """List all GSC properties the authenticated user has access to, with permission levels."""
    _audit("list_properties")
    try:
        data = gsc_get("sites")
        sites = data.get("siteEntry", [])
        return format_response({
            "sites": [
                {
                    "siteUrl": s.get("siteUrl"),
                    "permissionLevel": s.get("permissionLevel"),
                }
                for s in sites
            ],
            "total": len(sites),
        })
    except Exception as e:
        return format_error(str(e))


def get_site_details(site_url: str) -> Dict:
    """Get details for a specific GSC property including permission level.

    Args:
        site_url: Property URL (e.g. 'https://example.com/' or 'sc-domain:example.com')
    """
    _audit("get_site_details", site_url)
    try:
        data = gsc_get(f"sites/{_encode_site(site_url)}")
        return format_response(data, site_url=site_url)
    except Exception as e:
        return format_error(str(e))


def add_site(site_url: str) -> Dict:
    """Add a new property to GSC. Requires site owner verification.

    Args:
        site_url: Property URL to add (e.g. 'https://example.com/')
    """
    _audit("add_site", site_url)
    try:
        gsc_put(f"sites/{_encode_site(site_url)}", site_url=site_url)
        return format_response({"added": site_url, "message": "Site added. Complete verification in GSC."})
    except Exception as e:
        return format_error(str(e))


def delete_site(site_url: str) -> Dict:
    """Remove a property from GSC. Irreversible — use with caution.

    Args:
        site_url: Property URL to remove
    """
    _audit("delete_site", site_url)
    try:
        gsc_delete(f"sites/{_encode_site(site_url)}", site_url=site_url)
        return format_response({"deleted": site_url})
    except Exception as e:
        return format_error(str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sites.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add gsc/sites.py tests/test_sites.py
git commit -m "feat: add sites tools (list, get, add, delete)"
```

---

## Task 5: Search Analytics — Core Tools

**Files:**
- Create: `gsc/search_analytics.py`
- Create: `tests/test_search_analytics.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_search_analytics.py
import pytest
from unittest.mock import patch


MOCK_ANALYTICS_RESP = {
    "rows": [
        {
            "keys": ["example query"],
            "clicks": 100.0,
            "impressions": 1000.0,
            "ctr": 0.1,
            "position": 5.2,
        }
    ],
    "responseAggregationType": "byPage",
}


def test_get_search_analytics_basic():
    from gsc.search_analytics import get_search_analytics
    with patch("gsc.search_analytics.gsc_post", return_value=MOCK_ANALYTICS_RESP):
        result = get_search_analytics(
            site_url="https://example.com/",
            start_date="2025-01-01",
            end_date="2025-01-07",
        )
    assert result["success"] is True
    assert len(result["data"]["rows"]) == 1
    assert result["data"]["rows"][0]["clicks"] == 100.0
    assert result["metadata"]["rows_returned"] == 1


def test_get_search_analytics_with_dimensions():
    from gsc.search_analytics import get_search_analytics
    with patch("gsc.search_analytics.gsc_post", return_value=MOCK_ANALYTICS_RESP) as mock_post:
        result = get_search_analytics(
            site_url="https://example.com/",
            start_date="2025-01-01",
            end_date="2025-01-07",
            dimensions=["query", "page"],
            search_type="web",
            data_state="final",
        )
    call_body = mock_post.call_args[0][1]
    assert call_body["dimensions"] == ["query", "page"]
    assert call_body["searchType"] == "web"
    assert call_body["dataState"] == "final"


def test_get_performance_overview():
    from gsc.search_analytics import get_performance_overview
    mock_resp = {
        "rows": [
            {"clicks": 500.0, "impressions": 10000.0, "ctr": 0.05, "position": 8.3}
        ]
    }
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = get_performance_overview("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    assert "summary" in result["data"]
    assert result["data"]["summary"]["total_clicks"] == 500.0


def test_compare_periods():
    from gsc.search_analytics import compare_periods
    mock_current = {"rows": [{"clicks": 200.0, "impressions": 2000.0, "ctr": 0.1, "position": 5.0}]}
    mock_previous = {"rows": [{"clicks": 100.0, "impressions": 1000.0, "ctr": 0.1, "position": 6.0}]}
    with patch("gsc.search_analytics.gsc_post", side_effect=[mock_current, mock_previous]):
        result = compare_periods(
            site_url="https://example.com/",
            current_start="2025-01-08",
            current_end="2025-01-14",
            previous_start="2025-01-01",
            previous_end="2025-01-07",
        )
    assert result["success"] is True
    assert result["data"]["current"]["total_clicks"] == 200.0
    assert result["data"]["previous"]["total_clicks"] == 100.0
    assert result["data"]["changes"]["clicks_change_pct"] == 100.0


def test_get_search_analytics_api_error():
    from gsc.search_analytics import get_search_analytics
    import requests
    with patch("gsc.search_analytics.gsc_post", side_effect=requests.HTTPError("403 Forbidden")):
        result = get_search_analytics("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is False
    assert "403" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_search_analytics.py -v
```

Expected: `ModuleNotFoundError: No module named 'gsc.search_analytics'`

- [ ] **Step 3: Create gsc/search_analytics.py**

```python
"""GSC Search Analytics tools."""
from typing import Any, Dict, List, Optional
from .client import gsc_post, format_response, format_error, _encode_site, _audit

VALID_DIMENSIONS = {"query", "page", "country", "device", "searchAppearance", "date"}
VALID_SEARCH_TYPES = {"web", "image", "video", "news", "discover", "googleNews"}
VALID_DATA_STATES = {"all", "final"}
MAX_ROW_LIMIT = 5000


def get_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Optional[List[str]] = None,
    search_type: str = "web",
    data_state: str = "all",
    row_limit: int = 1000,
    start_row: int = 0,
    filters: Optional[List[Dict]] = None,
) -> Dict:
    """Query GSC search analytics data.

    Args:
        site_url: Property URL (e.g. 'https://example.com/' or 'sc-domain:example.com')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        dimensions: List of dimensions. Options: query, page, country, device, searchAppearance, date
        search_type: One of: web, image, video, news, discover, googleNews (default: web)
        data_state: 'all' (includes partial data) or 'final' (2-3 day lag, more stable)
        row_limit: Max rows to return. Max 5000 (default: 1000)
        start_row: Pagination offset (default: 0)
        filters: List of filter dicts: [{"dimension": "query", "operator": "contains", "expression": "keyword"}]
    """
    _audit("get_search_analytics", site_url)
    if search_type not in VALID_SEARCH_TYPES:
        return format_error(f"Invalid search_type '{search_type}'. Valid: {VALID_SEARCH_TYPES}", "INVALID_PARAM")
    if data_state not in VALID_DATA_STATES:
        return format_error(f"Invalid data_state '{data_state}'. Valid: all, final", "INVALID_PARAM")
    row_limit = min(row_limit, MAX_ROW_LIMIT)

    body: Dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "searchType": search_type,
        "dataState": data_state,
        "rowLimit": row_limit,
        "startRow": start_row,
    }
    if dimensions:
        body["dimensions"] = dimensions
    if filters:
        body["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]

    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])
        return format_response(
            {"rows": rows, "aggregation_type": resp.get("responseAggregationType")},
            site_url=site_url,
            date_range=[start_date, end_date],
            rows_returned=len(rows),
        )
    except Exception as e:
        return format_error(str(e))


def get_performance_overview(site_url: str, start_date: str, end_date: str, search_type: str = "web") -> Dict:
    """Get a summary of clicks, impressions, CTR, and average position for a property.

    Args:
        site_url: Property URL
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        search_type: One of: web, image, video, news, discover, googleNews
    """
    _audit("get_performance_overview", site_url)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "searchType": search_type,
        "rowLimit": 1,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [{}])
        row = rows[0] if rows else {}
        summary = {
            "total_clicks": row.get("clicks", 0),
            "total_impressions": row.get("impressions", 0),
            "average_ctr": round(row.get("ctr", 0) * 100, 2),
            "average_position": round(row.get("position", 0), 1),
        }
        return format_response(
            {"summary": summary, "period": {"start": start_date, "end": end_date}},
            site_url=site_url,
            date_range=[start_date, end_date],
        )
    except Exception as e:
        return format_error(str(e))


def compare_periods(
    site_url: str,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    dimensions: Optional[List[str]] = None,
    search_type: str = "web",
) -> Dict:
    """Compare search performance between two date periods.

    Args:
        site_url: Property URL
        current_start / current_end: Current period (YYYY-MM-DD)
        previous_start / previous_end: Comparison period (YYYY-MM-DD)
        dimensions: Dimensions to group by (optional)
        search_type: One of: web, image, video, news, discover, googleNews
    """
    _audit("compare_periods", site_url)

    def _query(start, end):
        body: Dict[str, Any] = {
            "startDate": start, "endDate": end,
            "searchType": search_type, "rowLimit": 1,
        }
        if dimensions:
            body["dimensions"] = dimensions
        return gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)

    def _summarize(resp):
        rows = resp.get("rows", [{}])
        row = rows[0] if rows else {}
        return {
            "total_clicks": row.get("clicks", 0),
            "total_impressions": row.get("impressions", 0),
            "average_ctr": round(row.get("ctr", 0) * 100, 2),
            "average_position": round(row.get("position", 0), 1),
        }

    try:
        current_resp = _query(current_start, current_end)
        previous_resp = _query(previous_start, previous_end)
        current = _summarize(current_resp)
        previous = _summarize(previous_resp)

        def _pct(curr, prev):
            if prev == 0:
                return None
            return round((curr - prev) / prev * 100, 1)

        changes = {
            "clicks_change_pct": _pct(current["total_clicks"], previous["total_clicks"]),
            "impressions_change_pct": _pct(current["total_impressions"], previous["total_impressions"]),
            "ctr_change_pct": _pct(current["average_ctr"], previous["average_ctr"]),
            "position_change": round(current["average_position"] - previous["average_position"], 1),
        }
        return format_response(
            {
                "current": current,
                "previous": previous,
                "changes": changes,
                "periods": {
                    "current": {"start": current_start, "end": current_end},
                    "previous": {"start": previous_start, "end": previous_end},
                },
            },
            site_url=site_url,
        )
    except Exception as e:
        return format_error(str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_search_analytics.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add gsc/search_analytics.py tests/test_search_analytics.py
git commit -m "feat: add core search analytics tools (query, overview, compare)"
```

---

## Task 6: Search Analytics — Extended Tools

**Files:**
- Modify: `gsc/search_analytics.py`
- Modify: `tests/test_search_analytics.py`

- [ ] **Step 1: Add failing tests for extended tools**

Append to `tests/test_search_analytics.py`:

```python
def test_get_position_band_report():
    from gsc.search_analytics import get_position_band_report
    mock_resp = {
        "rows": [
            {"keys": ["/page-a"], "clicks": 50.0, "impressions": 200.0, "ctr": 0.25, "position": 2.1},
            {"keys": ["/page-b"], "clicks": 10.0, "impressions": 500.0, "ctr": 0.02, "position": 7.5},
        ]
    }
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = get_position_band_report("https://example.com/", "2025-01-01", "2025-01-07", band="4-10")
    assert result["success"] is True
    # Band 4-10 → only page-b (position 7.5) should appear
    pages = result["data"]["pages"]
    assert all(4 <= p["position"] <= 10 for p in pages)


def test_get_ctr_optimization_report():
    from gsc.search_analytics import get_ctr_optimization_report
    mock_resp = {
        "rows": [
            {"keys": ["/low-ctr"], "clicks": 5.0, "impressions": 1000.0, "ctr": 0.005, "position": 6.0},
            {"keys": ["/good-ctr"], "clicks": 50.0, "impressions": 500.0, "ctr": 0.1, "position": 4.0},
        ]
    }
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = get_ctr_optimization_report("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    # Only low-ctr page should appear (impressions>100, ctr<2%)
    opportunities = result["data"]["opportunities"]
    assert len(opportunities) == 1
    assert opportunities[0]["page"] == "/low-ctr"


def test_get_keyword_cannibalization():
    from gsc.search_analytics import get_keyword_cannibalization
    mock_resp = {
        "rows": [
            {"keys": ["seo tips", "/page-a"], "clicks": 50.0, "impressions": 500.0, "ctr": 0.1, "position": 3.0},
            {"keys": ["seo tips", "/page-b"], "clicks": 20.0, "impressions": 300.0, "ctr": 0.07, "position": 7.0},
            {"keys": ["unique query", "/page-c"], "clicks": 100.0, "impressions": 1000.0, "ctr": 0.1, "position": 2.0},
        ]
    }
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = get_keyword_cannibalization("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    conflicts = result["data"]["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["query"] == "seo tips"
    assert len(conflicts[0]["pages"]) == 2


def test_batch_search_analytics():
    from gsc.search_analytics import batch_search_analytics
    mock_resp = {"rows": [{"clicks": 10.0, "impressions": 100.0, "ctr": 0.1, "position": 5.0}]}
    queries = [
        {"site_url": "https://example.com/", "start_date": "2025-01-01", "end_date": "2025-01-07"},
        {"site_url": "https://example.com/", "start_date": "2025-01-08", "end_date": "2025-01-14"},
    ]
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = batch_search_analytics(queries)
    assert result["success"] is True
    assert len(result["data"]["results"]) == 2
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_search_analytics.py::test_get_position_band_report tests/test_search_analytics.py::test_get_ctr_optimization_report tests/test_search_analytics.py::test_get_keyword_cannibalization tests/test_search_analytics.py::test_batch_search_analytics -v
```

Expected: 4 failures — `ImportError` or `AttributeError`

- [ ] **Step 3: Add extended functions to gsc/search_analytics.py**

Append to `gsc/search_analytics.py`:

```python
def get_position_band_report(
    site_url: str,
    start_date: str,
    end_date: str,
    band: str = "4-10",
    search_type: str = "web",
) -> Dict:
    """Get pages filtered by position band (e.g. ranks 4-10, 11-20).

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        band: Position range. Options: '1-3', '4-10', '11-20', '21-50' (default: '4-10')
        search_type: Search type filter
    """
    _audit("get_position_band_report", site_url)
    bands = {"1-3": (1, 3), "4-10": (4, 10), "11-20": (11, 20), "21-50": (21, 50)}
    if band not in bands:
        return format_error(f"Invalid band '{band}'. Valid: {list(bands.keys())}", "INVALID_PARAM")
    low, high = bands[band]
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": search_type,
        "rowLimit": MAX_ROW_LIMIT,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])
        filtered = [
            {
                "page": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows
            if low <= r.get("position", 0) <= high
        ]
        filtered.sort(key=lambda x: x["position"])
        return format_response(
            {"pages": filtered, "band": band, "count": len(filtered)},
            site_url=site_url, date_range=[start_date, end_date], rows_returned=len(filtered),
        )
    except Exception as e:
        return format_error(str(e))


def get_ctr_optimization_report(
    site_url: str,
    start_date: str,
    end_date: str,
    min_impressions: int = 100,
    max_ctr_pct: float = 2.0,
    search_type: str = "web",
) -> Dict:
    """Find pages with high impressions but low CTR — quick-win optimization candidates.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        min_impressions: Minimum impressions threshold (default: 100)
        max_ctr_pct: Maximum CTR % to include (default: 2.0)
        search_type: Search type filter
    """
    _audit("get_ctr_optimization_report", site_url)
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": search_type,
        "rowLimit": MAX_ROW_LIMIT,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])
        opportunities = [
            {
                "page": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr_pct": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
                "suggestion": "Review title tag and meta description — high impressions suggest ranking, low CTR suggests poor snippet appeal",
            }
            for r in rows
            if r.get("impressions", 0) >= min_impressions
            and r.get("ctr", 0) * 100 < max_ctr_pct
        ]
        opportunities.sort(key=lambda x: -x["impressions"])
        return format_response(
            {
                "opportunities": opportunities,
                "count": len(opportunities),
                "filters": {"min_impressions": min_impressions, "max_ctr_pct": max_ctr_pct},
            },
            site_url=site_url, date_range=[start_date, end_date], rows_returned=len(opportunities),
        )
    except Exception as e:
        return format_error(str(e))


def get_keyword_cannibalization(
    site_url: str,
    start_date: str,
    end_date: str,
    min_impressions: int = 50,
    search_type: str = "web",
) -> Dict:
    """Identify queries where multiple pages are competing for the same keyword.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        min_impressions: Minimum impressions per row to consider (default: 50)
        search_type: Search type filter
    """
    _audit("get_keyword_cannibalization", site_url)
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["query", "page"], "searchType": search_type,
        "rowLimit": MAX_ROW_LIMIT,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])

        # Group by query
        from collections import defaultdict
        query_pages: Dict[str, list] = defaultdict(list)
        for r in rows:
            if r.get("impressions", 0) < min_impressions:
                continue
            query, page = r["keys"][0], r["keys"][1]
            query_pages[query].append({
                "page": page,
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "position": round(r.get("position", 0), 1),
            })

        conflicts = [
            {
                "query": q,
                "pages": sorted(pages, key=lambda x: x["position"]),
                "recommendation": f"Consolidate content or add canonical tag. Primary page should be position {min(p['position'] for p in pages):.1f}.",
            }
            for q, pages in query_pages.items()
            if len(pages) > 1
        ]
        conflicts.sort(key=lambda x: -sum(p["impressions"] for p in x["pages"]))

        return format_response(
            {"conflicts": conflicts, "count": len(conflicts)},
            site_url=site_url, date_range=[start_date, end_date], rows_returned=len(conflicts),
        )
    except Exception as e:
        return format_error(str(e))


def batch_search_analytics(queries: List[Dict]) -> Dict:
    """Run multiple search analytics queries in one call.

    Args:
        queries: List of query dicts. Each dict supports: site_url (required), start_date,
                 end_date, dimensions, search_type, data_state, row_limit, filters.

    Example:
        queries = [
            {"site_url": "https://example.com/", "start_date": "2025-01-01", "end_date": "2025-01-07"},
            {"site_url": "https://example.com/", "start_date": "2025-01-08", "end_date": "2025-01-14"},
        ]
    """
    _audit("batch_search_analytics")
    results = []
    for i, q in enumerate(queries):
        site_url = q.get("site_url", "")
        body: Dict[str, Any] = {
            "startDate": q.get("start_date", ""),
            "endDate": q.get("end_date", ""),
            "searchType": q.get("search_type", "web"),
            "dataState": q.get("data_state", "all"),
            "rowLimit": min(q.get("row_limit", 1000), MAX_ROW_LIMIT),
        }
        if q.get("dimensions"):
            body["dimensions"] = q["dimensions"]
        if q.get("filters"):
            body["dimensionFilterGroups"] = [{"groupType": "and", "filters": q["filters"]}]
        try:
            resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
            rows = resp.get("rows", [])
            results.append({"index": i, "success": True, "query": q, "rows": rows, "rows_returned": len(rows)})
        except Exception as e:
            results.append({"index": i, "success": False, "query": q, "error": str(e)})

    return format_response({"results": results, "total_queries": len(queries)})


def export_full_dataset(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Optional[List[str]] = None,
    search_type: str = "web",
    max_rows: int = 50000,
) -> Dict:
    """Export all rows bypassing the 5,000-row API limit using pagination.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        dimensions: Dimensions to include (default: ['query', 'page'])
        search_type: Search type filter
        max_rows: Maximum total rows to fetch (default: 50000)
    """
    _audit("export_full_dataset", site_url)
    dimensions = dimensions or ["query", "page"]
    all_rows = []
    start_row = 0
    page_size = MAX_ROW_LIMIT  # 5000 per request

    try:
        while len(all_rows) < max_rows:
            body = {
                "startDate": start_date, "endDate": end_date,
                "dimensions": dimensions, "searchType": search_type,
                "rowLimit": page_size, "startRow": start_row,
            }
            resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
            rows = resp.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            start_row += len(rows)
            if len(rows) < page_size:
                break  # Last page

        return format_response(
            {"rows": all_rows[:max_rows], "paginated": start_row > MAX_ROW_LIMIT},
            site_url=site_url, date_range=[start_date, end_date],
            rows_returned=len(all_rows), rows_available=start_row,
        )
    except Exception as e:
        return format_error(str(e))
```

- [ ] **Step 4: Run all search analytics tests**

```bash
pytest tests/test_search_analytics.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add gsc/search_analytics.py tests/test_search_analytics.py
git commit -m "feat: add extended search analytics tools (position bands, CTR, cannibalization, batch, export)"
```

---

## Task 7: URL Inspection Tools

**Files:**
- Create: `gsc/url_inspection.py`
- Create: `tests/test_url_inspection.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_url_inspection.py
import pytest
from unittest.mock import patch


MOCK_INSPECT_RESP = {
    "inspectionResult": {
        "inspectionResultLink": "https://search.google.com/search-console/inspect?...",
        "indexStatusResult": {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "robotsTxtState": "ALLOWED",
            "indexingState": "INDEXING_ALLOWED",
            "lastCrawlTime": "2025-01-10T08:00:00Z",
            "pageFetchState": "SUCCESSFUL",
            "googleCanonical": "https://example.com/page",
            "userCanonical": "https://example.com/page",
        },
        "mobileUsabilityResult": {"verdict": "PASS", "issues": []},
        "richResultsResult": {
            "verdict": "PASS",
            "detectedItems": [{"richResultType": "FAQ"}],
        },
        "ampResult": None,
    }
}


def test_inspect_url_returns_full_result():
    from gsc.url_inspection import inspect_url
    with patch("gsc.url_inspection.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = inspect_url("https://example.com/page", "https://example.com/")
    assert result["success"] is True
    data = result["data"]
    assert data["verdict"] == "PASS"
    assert data["last_crawl_time"] == "2025-01-10T08:00:00Z"
    assert data["mobile_usability"]["verdict"] == "PASS"
    assert data["rich_results"]["verdict"] == "PASS"


def test_inspect_url_api_error():
    from gsc.url_inspection import inspect_url
    import requests
    with patch("gsc.url_inspection.inspect_post", side_effect=requests.HTTPError("403")):
        result = inspect_url("https://example.com/page", "https://example.com/")
    assert result["success"] is False


def test_batch_url_inspection():
    from gsc.url_inspection import batch_url_inspection
    with patch("gsc.url_inspection.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = batch_url_inspection(
            ["https://example.com/page-1", "https://example.com/page-2"],
            "https://example.com/",
        )
    assert result["success"] is True
    assert len(result["data"]["results"]) == 2
    assert result["data"]["results"][0]["url"] == "https://example.com/page-1"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_url_inspection.py -v
```

Expected: `ModuleNotFoundError: No module named 'gsc.url_inspection'`

- [ ] **Step 3: Create gsc/url_inspection.py**

```python
"""GSC URL Inspection tools."""
from typing import Dict, List, Optional
from .client import inspect_post, format_response, format_error, _audit


def _parse_inspection_result(resp: Dict) -> Dict:
    """Extract all relevant fields from URL Inspection API response."""
    result = resp.get("inspectionResult", {})
    index = result.get("indexStatusResult", {})
    mobile = result.get("mobileUsabilityResult", {})
    rich = result.get("richResultsResult", {})
    amp = result.get("ampResult")

    return {
        "verdict": index.get("verdict"),
        "coverage_state": index.get("coverageState"),
        "robots_txt_state": index.get("robotsTxtState"),
        "indexing_state": index.get("indexingState"),
        "last_crawl_time": index.get("lastCrawlTime"),
        "page_fetch_state": index.get("pageFetchState"),
        "google_canonical": index.get("googleCanonical"),
        "user_canonical": index.get("userCanonical"),
        "mobile_usability": {
            "verdict": mobile.get("verdict"),
            "issues": mobile.get("issues", []),
        },
        "rich_results": {
            "verdict": rich.get("verdict"),
            "detected_items": rich.get("detectedItems", []),
        },
        "amp": {
            "verdict": amp.get("verdict") if amp else None,
            "issues": amp.get("issues", []) if amp else [],
        } if amp else None,
        "inspection_link": result.get("inspectionResultLink"),
    }


def inspect_url(url: str, site_url: str) -> Dict:
    """Inspect a single URL for indexing status, mobile usability, rich results, and AMP.

    Args:
        url: The page URL to inspect (must belong to the property)
        site_url: The GSC property URL (e.g. 'https://example.com/')
    """
    _audit("inspect_url", site_url)
    try:
        resp = inspect_post({"inspectionUrl": url, "siteUrl": site_url})
        return format_response(_parse_inspection_result(resp), site_url=site_url)
    except Exception as e:
        return format_error(str(e))


def batch_url_inspection(urls: List[str], site_url: str) -> Dict:
    """Inspect multiple URLs for indexing status, mobile usability, and rich results.

    Args:
        urls: List of page URLs to inspect (max 50 recommended per call)
        site_url: The GSC property URL
    """
    _audit("batch_url_inspection", site_url)
    results = []
    for url in urls:
        try:
            resp = inspect_post({"inspectionUrl": url, "siteUrl": site_url})
            results.append({"url": url, "success": True, **_parse_inspection_result(resp)})
        except Exception as e:
            results.append({"url": url, "success": False, "error": str(e)})

    passed = sum(1 for r in results if r.get("verdict") == "PASS")
    failed = len(results) - passed
    return format_response(
        {"results": results, "summary": {"total": len(results), "passed": passed, "failed": failed}},
        site_url=site_url, rows_returned=len(results),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_url_inspection.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add gsc/url_inspection.py tests/test_url_inspection.py
git commit -m "feat: add URL inspection tools with full field extraction"
```

---

## Task 8: Sitemaps Tools

**Files:**
- Create: `gsc/sitemaps.py`
- Create: `tests/test_sitemaps.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sitemaps.py
import pytest
from unittest.mock import patch


MOCK_SITEMAP = {
    "path": "https://example.com/sitemap.xml",
    "lastSubmitted": "2025-01-01T00:00:00Z",
    "isPending": False,
    "isSitemapsIndex": False,
    "type": "sitemap",
    "lastDownloaded": "2025-01-02T00:00:00Z",
    "warnings": 0,
    "errors": 2,
    "contents": [
        {"type": "web", "submitted": 100, "indexed": 95}
    ],
}


def test_list_sitemaps():
    from gsc.sitemaps import list_sitemaps
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [MOCK_SITEMAP]}):
        result = list_sitemaps("https://example.com/")
    assert result["success"] is True
    assert len(result["data"]["sitemaps"]) == 1
    assert result["data"]["sitemaps"][0]["path"] == "https://example.com/sitemap.xml"
    assert result["data"]["sitemaps"][0]["indexed"] == 95
    assert result["data"]["sitemaps"][0]["errors"] == 2


def test_list_sitemaps_flags_high_error_rate():
    from gsc.sitemaps import list_sitemaps
    bad_sitemap = {**MOCK_SITEMAP, "contents": [{"type": "web", "submitted": 100, "indexed": 10}], "errors": 90}
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [bad_sitemap]}):
        result = list_sitemaps("https://example.com/")
    assert result["data"]["sitemaps"][0]["health"] == "poor"


def test_get_sitemap():
    from gsc.sitemaps import get_sitemap
    with patch("gsc.sitemaps.gsc_get", return_value=MOCK_SITEMAP):
        result = get_sitemap("https://example.com/", "https://example.com/sitemap.xml")
    assert result["success"] is True
    assert result["data"]["path"] == "https://example.com/sitemap.xml"


def test_submit_sitemap():
    from gsc.sitemaps import submit_sitemap
    with patch("gsc.sitemaps.gsc_put", return_value={}):
        result = submit_sitemap("https://example.com/", "https://example.com/sitemap-new.xml")
    assert result["success"] is True
    assert "submitted" in result["data"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_sitemaps.py -v
```

Expected: `ModuleNotFoundError: No module named 'gsc.sitemaps'`

- [ ] **Step 3: Create gsc/sitemaps.py**

```python
"""GSC Sitemaps tools."""
from typing import Dict
from .client import gsc_get, gsc_put, gsc_delete, format_response, format_error, _encode_site, _audit


def _parse_sitemap(s: Dict) -> Dict:
    contents = s.get("contents", [])
    total_submitted = sum(c.get("submitted", 0) for c in contents)
    total_indexed = sum(c.get("indexed", 0) for c in contents)
    errors = s.get("errors", 0)

    # Health classification
    if total_submitted > 0:
        index_rate = total_indexed / total_submitted
        health = "good" if index_rate >= 0.9 and errors == 0 else \
                 "fair" if index_rate >= 0.7 else "poor"
    else:
        health = "unknown"

    return {
        "path": s.get("path"),
        "last_submitted": s.get("lastSubmitted"),
        "last_downloaded": s.get("lastDownloaded"),
        "type": s.get("type"),
        "is_index": s.get("isSitemapsIndex", False),
        "is_pending": s.get("isPending", False),
        "submitted": total_submitted,
        "indexed": total_indexed,
        "errors": errors,
        "warnings": s.get("warnings", 0),
        "health": health,
        "contents_breakdown": contents,
    }


def list_sitemaps(site_url: str) -> Dict:
    """List all sitemaps for a property with indexing stats and health classification.

    Args:
        site_url: Property URL (e.g. 'https://example.com/')
    """
    _audit("list_sitemaps", site_url)
    try:
        data = gsc_get(f"sites/{_encode_site(site_url)}/sitemaps")
        sitemaps = [_parse_sitemap(s) for s in data.get("sitemap", [])]
        poor_health = [s for s in sitemaps if s["health"] == "poor"]
        return format_response(
            {
                "sitemaps": sitemaps,
                "total": len(sitemaps),
                "health_summary": {
                    "good": sum(1 for s in sitemaps if s["health"] == "good"),
                    "fair": sum(1 for s in sitemaps if s["health"] == "fair"),
                    "poor": len(poor_health),
                },
                "alerts": [f"{s['path']} has high error rate ({s['errors']} errors)" for s in poor_health],
            },
            site_url=site_url, rows_returned=len(sitemaps),
        )
    except Exception as e:
        return format_error(str(e))


def get_sitemap(site_url: str, feed_path: str) -> Dict:
    """Get details for a specific sitemap.

    Args:
        site_url: Property URL
        feed_path: Full URL of the sitemap (e.g. 'https://example.com/sitemap.xml')
    """
    _audit("get_sitemap", site_url)
    try:
        data = gsc_get(f"sites/{_encode_site(site_url)}/sitemaps/{_encode_site(feed_path)}")
        return format_response(_parse_sitemap(data), site_url=site_url)
    except Exception as e:
        return format_error(str(e))


def submit_sitemap(site_url: str, feed_path: str) -> Dict:
    """Submit a sitemap to Google Search Console.

    Args:
        site_url: Property URL
        feed_path: Full URL of the sitemap to submit
    """
    _audit("submit_sitemap", site_url)
    try:
        gsc_put(f"sites/{_encode_site(site_url)}/sitemaps/{_encode_site(feed_path)}", site_url=site_url)
        return format_response({"submitted": feed_path, "message": "Sitemap submitted. Google will process it shortly."})
    except Exception as e:
        return format_error(str(e))


def delete_sitemap(site_url: str, feed_path: str) -> Dict:
    """Remove a sitemap from GSC. Does not delete the actual sitemap file.

    Args:
        site_url: Property URL
        feed_path: Full URL of the sitemap to remove
    """
    _audit("delete_sitemap", site_url)
    try:
        gsc_delete(f"sites/{_encode_site(site_url)}/sitemaps/{_encode_site(feed_path)}", site_url=site_url)
        return format_response({"deleted": feed_path})
    except Exception as e:
        return format_error(str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sitemaps.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add gsc/sitemaps.py tests/test_sitemaps.py
git commit -m "feat: add sitemap tools with health classification"
```

---

## Task 9: Composite Tools

**Files:**
- Create: `gsc/composite.py`
- Create: `tests/test_composite.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_composite.py
import pytest
from unittest.mock import patch, MagicMock, call


MOCK_SITES = {"siteEntry": [{"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"}]}
MOCK_ANALYTICS = {
    "rows": [
        {"keys": ["/top-page"], "clicks": 500.0, "impressions": 5000.0, "ctr": 0.1, "position": 3.2},
    ]
}
MOCK_INSPECT = {
    "inspectionResult": {
        "indexStatusResult": {
            "verdict": "PASS", "coverageState": "Submitted and indexed",
            "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED",
            "lastCrawlTime": "2025-01-10T08:00:00Z", "pageFetchState": "SUCCESSFUL",
            "googleCanonical": "https://example.com/top-page", "userCanonical": "https://example.com/top-page",
        },
        "mobileUsabilityResult": {"verdict": "PASS", "issues": []},
        "richResultsResult": {"verdict": "PASS", "detectedItems": []},
        "ampResult": None,
    }
}


def test_analyze_site_health():
    from gsc.composite import analyze_site_health
    with patch("gsc.composite.gsc_post", return_value=MOCK_ANALYTICS), \
         patch("gsc.composite.inspect_post", return_value=MOCK_INSPECT):
        result = analyze_site_health("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    pages = result["data"]["top_pages"]
    assert len(pages) == 1
    assert pages[0]["url"] == "/top-page"
    assert pages[0]["indexing"]["verdict"] == "PASS"


def test_identify_quick_wins():
    from gsc.composite import identify_quick_wins
    mock_resp = {
        "rows": [
            {"keys": ["/win-page"], "clicks": 5.0, "impressions": 500.0, "ctr": 0.01, "position": 6.5},
            {"keys": ["/good-page"], "clicks": 100.0, "impressions": 1000.0, "ctr": 0.1, "position": 2.0},
        ]
    }
    with patch("gsc.composite.gsc_post", return_value=mock_resp), \
         patch("gsc.composite.inspect_post", return_value=MOCK_INSPECT):
        result = identify_quick_wins("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    wins = result["data"]["quick_wins"]
    # Only /win-page qualifies: impressions>100, ctr<2%, position 4-10
    assert len(wins) == 1
    assert wins[0]["page"] == "/win-page"


def test_crawl_error_summary():
    from gsc.composite import crawl_error_summary
    mock_resp = {
        "rows": [
            {"keys": ["/broken"], "clicks": 0.0, "impressions": 100.0, "ctr": 0.0, "position": 30.0},
        ]
    }
    fail_inspect = {
        "inspectionResult": {
            "indexStatusResult": {
                "verdict": "FAIL", "coverageState": "Excluded", "robotsTxtState": "ALLOWED",
                "indexingState": "INDEXING_ALLOWED", "lastCrawlTime": None,
                "pageFetchState": "SOFT_404", "googleCanonical": None, "userCanonical": "/broken",
            },
            "mobileUsabilityResult": {"verdict": "FAIL", "issues": [{"type": "MOBILE_ISSUE"}]},
            "richResultsResult": {"verdict": "NEUTRAL", "detectedItems": []},
            "ampResult": None,
        }
    }
    with patch("gsc.composite.gsc_post", return_value=mock_resp), \
         patch("gsc.composite.inspect_post", return_value=fail_inspect):
        result = crawl_error_summary("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    assert result["data"]["total_errors"] >= 1
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_composite.py -v
```

Expected: `ModuleNotFoundError: No module named 'gsc.composite'`

- [ ] **Step 3: Create gsc/composite.py**

```python
"""Cross-service composite GSC analysis tools."""
from typing import Dict, List, Optional
from .client import gsc_get, gsc_post, format_response, format_error, _encode_site, _audit, inspect_post
from .url_inspection import _parse_inspection_result

MAX_PAGES_FOR_HEALTH = 10
MAX_ROW_LIMIT = 5000


def analyze_site_health(site_url: str, start_date: str, end_date: str) -> Dict:
    """One-call site health report: top pages with traffic, indexing status, mobile usability, and last crawl time.

    Args:
        site_url: Property URL
        start_date / end_date: Date range for traffic data (YYYY-MM-DD)
    """
    _audit("analyze_site_health", site_url)
    # Step 1: Get top pages by traffic
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": "web",
        "rowLimit": MAX_PAGES_FOR_HEALTH,
    }
    try:
        analytics_resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        top_rows = analytics_resp.get("rows", [])

        # Step 2: Inspect each page
        enriched = []
        for row in top_rows:
            page_url = row["keys"][0]
            traffic = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr_pct": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
            try:
                inspect_resp = inspect_post({"inspectionUrl": page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url, "siteUrl": site_url})
                indexing = _parse_inspection_result(inspect_resp)
            except Exception as e:
                indexing = {"error": str(e)}

            enriched.append({"url": page_url, "traffic": traffic, "indexing": indexing})

        issues = [p for p in enriched if isinstance(p.get("indexing"), dict) and p["indexing"].get("verdict") != "PASS"]
        return format_response(
            {
                "top_pages": enriched,
                "summary": {
                    "pages_analyzed": len(enriched),
                    "indexing_issues": len(issues),
                },
            },
            site_url=site_url, date_range=[start_date, end_date],
        )
    except Exception as e:
        return format_error(str(e))


def identify_quick_wins(
    site_url: str,
    start_date: str,
    end_date: str,
    min_impressions: int = 100,
    max_ctr_pct: float = 2.0,
    position_low: float = 4.0,
    position_high: float = 10.0,
) -> Dict:
    """Find pages worth quick optimization: high impressions, low CTR, ranked 4-10, no indexing issues.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        min_impressions: Minimum impressions threshold (default: 100)
        max_ctr_pct: Maximum CTR % (default: 2.0)
        position_low / position_high: Position band (default: 4.0 - 10.0)
    """
    _audit("identify_quick_wins", site_url)
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": "web",
        "rowLimit": MAX_ROW_LIMIT,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])
        candidates = [
            r for r in rows
            if r.get("impressions", 0) >= min_impressions
            and r.get("ctr", 0) * 100 < max_ctr_pct
            and position_low <= r.get("position", 0) <= position_high
        ]

        quick_wins = []
        for r in candidates[:20]:  # Inspect top 20 candidates only
            page_url = r["keys"][0]
            try:
                inspect_resp = inspect_post({"inspectionUrl": page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url, "siteUrl": site_url})
                parsed = _parse_inspection_result(inspect_resp)
                if parsed.get("verdict") != "PASS":
                    continue  # Skip pages with indexing issues
            except Exception:
                parsed = {}

            quick_wins.append({
                "page": page_url,
                "impressions": r.get("impressions", 0),
                "clicks": r.get("clicks", 0),
                "ctr_pct": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
                "suggestion": "Improve title tag and meta description to increase click-through rate",
                "indexing": parsed,
            })

        return format_response(
            {"quick_wins": quick_wins, "count": len(quick_wins)},
            site_url=site_url, date_range=[start_date, end_date],
        )
    except Exception as e:
        return format_error(str(e))


def crawl_error_summary(site_url: str, start_date: str, end_date: str, sample_size: int = 50) -> Dict:
    """Aggregate crawl and indexing errors across a property's low-performing pages.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        sample_size: Number of pages to inspect (default: 50)
    """
    _audit("crawl_error_summary", site_url)
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": "web",
        "rowLimit": sample_size,
    }
    try:
        resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        rows = resp.get("rows", [])

        errors = []
        mobile_issues = []
        for r in rows:
            page_url = r["keys"][0]
            try:
                inspect_resp = inspect_post({"inspectionUrl": page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url, "siteUrl": site_url})
                parsed = _parse_inspection_result(inspect_resp)
                if parsed.get("verdict") != "PASS":
                    errors.append({"page": page_url, "verdict": parsed.get("verdict"), "state": parsed.get("coverage_state"), "fetch_state": parsed.get("page_fetch_state")})
                if parsed.get("mobile_usability", {}).get("verdict") == "FAIL":
                    mobile_issues.append({"page": page_url, "issues": parsed["mobile_usability"]["issues"]})
            except Exception:
                pass

        return format_response(
            {
                "indexing_errors": errors,
                "mobile_issues": mobile_issues,
                "total_errors": len(errors),
                "total_mobile_issues": len(mobile_issues),
                "pages_sampled": len(rows),
            },
            site_url=site_url, date_range=[start_date, end_date],
        )
    except Exception as e:
        return format_error(str(e))


def property_migration_checklist(old_site_url: str, new_site_url: str, start_date: str, end_date: str) -> Dict:
    """Generate a migration checklist when moving a site: indexed pages, sitemap status, redirect verification.

    Args:
        old_site_url: Original property URL
        new_site_url: New/destination property URL
        start_date / end_date: Date range to assess current traffic (YYYY-MM-DD)
    """
    _audit("property_migration_checklist", old_site_url)
    checklist = []
    data = {}

    # Step 1: Get indexed pages on old site
    try:
        body = {
            "startDate": start_date, "endDate": end_date,
            "dimensions": ["page"], "searchType": "web", "rowLimit": MAX_ROW_LIMIT,
        }
        resp = gsc_post(f"sites/{_encode_site(old_site_url)}/searchAnalytics/query", body, old_site_url)
        old_pages = [r["keys"][0] for r in resp.get("rows", [])]
        data["old_site_indexed_pages"] = len(old_pages)
        data["sample_old_pages"] = old_pages[:20]
        checklist.append({"item": "Identify indexed pages on old site", "status": "done", "count": len(old_pages)})
    except Exception as e:
        checklist.append({"item": "Identify indexed pages on old site", "status": "error", "error": str(e)})

    # Step 2: List sitemaps on old site
    try:
        sitemaps_resp = gsc_get(f"sites/{_encode_site(old_site_url)}/sitemaps")
        sitemaps = sitemaps_resp.get("sitemap", [])
        data["old_sitemaps"] = [s.get("path") for s in sitemaps]
        checklist.append({"item": "List sitemaps on old site", "status": "done", "sitemaps": data["old_sitemaps"]})
    except Exception as e:
        checklist.append({"item": "List sitemaps on old site", "status": "error", "error": str(e)})

    # Step 3: Check if new site exists in GSC
    try:
        new_sites_resp = gsc_get("sites")
        new_site_exists = any(
            s.get("siteUrl") == new_site_url
            for s in new_sites_resp.get("siteEntry", [])
        )
        checklist.append({
            "item": "Verify new site is added to GSC",
            "status": "done" if new_site_exists else "action_required",
            "message": "New site found in GSC" if new_site_exists else f"Add {new_site_url} to GSC and complete verification",
        })
    except Exception as e:
        checklist.append({"item": "Verify new site is added to GSC", "status": "error", "error": str(e)})

    # Step 4: Recommended manual steps
    checklist.extend([
        {"item": "Verify 301 redirects are in place for all old URLs", "status": "manual", "action": "Check redirect rules on server or CDN"},
        {"item": "Submit updated sitemaps on new property", "status": "manual", "action": f"Use submit_sitemap tool on {new_site_url}"},
        {"item": "Monitor new site in GSC for 2-4 weeks post-migration", "status": "manual", "action": "Check coverage report weekly"},
        {"item": "Set preferred domain in new GSC property", "status": "manual", "action": "GSC → Settings → Preferred domain"},
    ])

    return format_response(
        {"checklist": checklist, "data": data, "old_site": old_site_url, "new_site": new_site_url},
        site_url=old_site_url, date_range=[start_date, end_date],
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_composite.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add gsc/composite.py tests/test_composite.py
git commit -m "feat: add composite analysis tools (site health, quick wins, crawl errors, migration)"
```

---

## Task 10: server.py + main.py

**Files:**
- Create: `server.py`
- Create: `main.py`

- [ ] **Step 1: Create server.py**

```python
"""Google Search Console MCP Server — tool registrations."""
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

mcp = FastMCP("Google Search Console Tools")

# --- Sites ---
from gsc.sites import list_properties, get_site_details, add_site, delete_site
mcp.tool(list_properties)
mcp.tool(get_site_details)
mcp.tool(add_site)
mcp.tool(delete_site)

# --- Search Analytics ---
from gsc.search_analytics import (
    get_search_analytics,
    get_performance_overview,
    compare_periods,
    get_position_band_report,
    get_ctr_optimization_report,
    get_keyword_cannibalization,
    batch_search_analytics,
    export_full_dataset,
)
mcp.tool(get_search_analytics)
mcp.tool(get_performance_overview)
mcp.tool(compare_periods)
mcp.tool(get_position_band_report)
mcp.tool(get_ctr_optimization_report)
mcp.tool(get_keyword_cannibalization)
mcp.tool(batch_search_analytics)
mcp.tool(export_full_dataset)

# --- URL Inspection ---
from gsc.url_inspection import inspect_url, batch_url_inspection
mcp.tool(inspect_url)
mcp.tool(batch_url_inspection)

# --- Sitemaps ---
from gsc.sitemaps import list_sitemaps, get_sitemap, submit_sitemap, delete_sitemap
mcp.tool(list_sitemaps)
mcp.tool(get_sitemap)
mcp.tool(submit_sitemap)
mcp.tool(delete_sitemap)

# --- Composite ---
from gsc.composite import (
    analyze_site_health,
    identify_quick_wins,
    crawl_error_summary,
    property_migration_checklist,
)
mcp.tool(analyze_site_health)
mcp.tool(identify_quick_wins)
mcp.tool(crawl_error_summary)
mcp.tool(property_migration_checklist)
```

- [ ] **Step 2: Create main.py**

```python
"""Google Search Console MCP Server — FastAPI wrapper with OAuth and SSE transport."""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from server import mcp
from oauth.auth_routes import router as auth_router
from oauth.google_auth import current_user_email

BASE_URL = os.environ.get("BASE_URL", "")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "dev-secret-change-me")

mcp_asgi_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_asgi_app.lifespan, redirect_slashes=False)

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.include_router(auth_router, prefix="/auth")


@app.middleware("http")
async def require_login_for_mcp(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        email = request.query_params.get("user")
        if not email:
            email = request.session.get("user_email")
        if not email:
            return Response("Unauthorized. Visit /auth/login first.", status_code=401)
        current_user_email.set(email)
    return await call_next(request)


app.mount("/mcp", mcp_asgi_app)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

- [ ] **Step 3: Run all tests to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all passed

- [ ] **Step 4: Commit**

```bash
git add server.py main.py
git commit -m "feat: wire server.py and main.py — all 22 tools registered"
```

---

## Task 11: Dockerfile + Deploy Script

**Files:**
- Create: `Dockerfile`
- Modify: `/Users/dhawal/src/team-mcp/deploy.sh`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["python", "main.py"]
```

- [ ] **Step 2: Add GSC MCP block to deploy.sh**

In `/Users/dhawal/src/team-mcp/deploy.sh`, compute the GSC URL alongside GA/Ads URLs:

```bash
GSC_URL="https://gsc-mcp-${PROJECT_NUMBER}.${REGION}.run.app"
GSC_SESSION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

And add the deploy block before the final summary echo:

```bash
echo ""
echo "========================================="
echo "Deploying Google Search Console MCP..."
echo "========================================="

gcloud run deploy gsc-mcp \
  --source ./google-search-console-mcp \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,OAUTH_CONFIG_PATH=/app/client_secret.json,ALLOWED_DOMAIN=$ALLOWED_DOMAIN,SESSION_SECRET_KEY=$GSC_SESSION_KEY,BASE_URL=$GSC_URL,OAUTHLIB_RELAX_TOKEN_SCOPE=1"

echo "GSC MCP deployed at: $GSC_URL"
```

And add to the summary section:
```bash
echo "Google Search Console MCP:"
echo "  Login page: $GSC_URL/auth/login"
echo "  MCP path:   $GSC_URL/mcp"
echo ""
echo "  Add to Google Cloud Console → Credentials:"
echo "  $GSC_URL/auth/callback"
```

- [ ] **Step 3: Test Docker build locally**

```bash
docker build -t gsc-mcp:local .
docker run --rm -p 8080:8080 \
  -e GCP_PROJECT_ID=test \
  -e OAUTH_CONFIG_PATH=/app/client_secret.json \
  -e ALLOWED_DOMAIN=example.com \
  -e SESSION_SECRET_KEY=test-secret \
  -e BASE_URL=http://localhost:8080 \
  gsc-mcp:local
```

Expected: Server starts, visit http://localhost:8080/auth/status shows "Not logged in" page

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile and Cloud Run deploy config"
```

---

## Task 12: Open Source Prep

**Files:**
- Create: `setup_local_auth.py`
- Create: `manifest.json`
- Create: `README.md`

- [ ] **Step 1: Create setup_local_auth.py**

```python
#!/usr/bin/env python3
"""
One-shot local authentication for Google Search Console MCP (STDIO mode).

Opens your browser for Google OAuth consent, saves token to
~/.config/google-search-console-mcp/token.json

Usage:
    python setup_local_auth.py

Requirements:
    OAUTH_CONFIG_PATH env var (or ./client_secret.json by default)
"""
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

REDIRECT_URI = "http://localhost:8080/auth/callback"
TOKEN_PATH = Path.home() / ".config" / "google-search-console-mcp" / "token.json"
CLIENT_CONFIG_PATH = os.environ.get("OAUTH_CONFIG_PATH", "./client_secret.json")

_auth_code = None
_auth_error = None
_server_done = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code, _auth_error
        parsed = urlparse(self.path)
        if parsed.path != "/auth/callback":
            self.send_response(404); self.end_headers(); return
        params = parse_qs(parsed.query)
        if "error" in params:
            _auth_error = params["error"][0]
            self._respond("<h2>Authentication cancelled.</h2>")
        elif "code" in params:
            _auth_code = params["code"][0]
            self._respond("<h2>Authentication successful! You can close this tab.</h2>")
        _server_done.set()

    def _respond(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format, *args): pass


def main():
    if not Path(CLIENT_CONFIG_PATH).exists():
        print(f"ERROR: OAuth credentials file not found: {CLIENT_CONFIG_PATH}")
        raise SystemExit(1)

    flow = Flow.from_client_secrets_file(CLIENT_CONFIG_PATH, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("Opening browser for Google authentication...")
    print(f"If browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    _server_done.wait(timeout=120)
    server.shutdown()

    if _auth_error:
        print(f"ERROR: {_auth_error}"); raise SystemExit(1)
    if not _auth_code:
        print("ERROR: No code received (timed out)."); raise SystemExit(1)

    flow.fetch_token(code=_auth_code)
    creds = flow.credentials
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"\nToken saved to: {TOKEN_PATH}")
    print("\nAdd to Claude Desktop MCP config:")
    print('  "env": { "MCP_USER_EMAIL": "you@company.com", "OAUTH_CONFIG_PATH": "/path/to/client_secret.json" }')


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create manifest.json**

```json
{
  "dxt_version": "0.1",
  "name": "google-search-console-mcp",
  "display_name": "Google Search Console MCP",
  "version": "1.0.0",
  "description": "A Python MCP server for Google Search Console API with OAuth 2.0 authentication",
  "long_description": "Connect Claude (or any MCP-compatible AI client) directly to your Google Search Console properties. Supports search analytics, URL inspection, sitemap management, and composite analysis tools for SEO teams. Runs locally via STDIO or as a shared team server on Google Cloud Run.",
  "author": {
    "name": "Dhawal Shah",
    "url": "https://github.com/dhawalshah"
  },
  "server": {
    "type": "python",
    "entry_point": "server.py",
    "mcp_config": {
      "command": "python",
      "args": ["${__dirname}/server.py"],
      "env": {
        "OAUTH_CONFIG_PATH": "${user_config.oauth_config_path}",
        "MCP_USER_EMAIL": "${user_config.mcp_user_email}",
        "PYTHONPATH": "${__dirname}/lib"
      },
      "cwd": "${__dirname}"
    }
  },
  "tools": [
    {"name": "list_properties", "description": "List all GSC properties with permission levels"},
    {"name": "get_site_details", "description": "Get details for a specific GSC property"},
    {"name": "get_search_analytics", "description": "Query search analytics with dimensions and filters"},
    {"name": "get_performance_overview", "description": "Get clicks/impressions/CTR/position summary"},
    {"name": "compare_periods", "description": "Compare performance between two date periods"},
    {"name": "get_position_band_report", "description": "Filter pages by position band (1-3, 4-10, 11-20)"},
    {"name": "get_ctr_optimization_report", "description": "Find pages with high impressions but low CTR"},
    {"name": "get_keyword_cannibalization", "description": "Identify queries with multiple competing pages"},
    {"name": "batch_search_analytics", "description": "Run multiple analytics queries in one call"},
    {"name": "export_full_dataset", "description": "Export all rows bypassing 5K row limit"},
    {"name": "inspect_url", "description": "Inspect a URL for indexing, mobile usability, and rich results"},
    {"name": "batch_url_inspection", "description": "Inspect multiple URLs at once"},
    {"name": "list_sitemaps", "description": "List sitemaps with health classification"},
    {"name": "get_sitemap", "description": "Get details for a specific sitemap"},
    {"name": "submit_sitemap", "description": "Submit a sitemap to GSC"},
    {"name": "delete_sitemap", "description": "Remove a sitemap from GSC"},
    {"name": "analyze_site_health", "description": "One-call site health report: traffic + indexing + mobile"},
    {"name": "identify_quick_wins", "description": "Find pages worth optimizing (high impressions, low CTR, ranked 4-10)"},
    {"name": "crawl_error_summary", "description": "Aggregate indexing and mobile errors across a property"},
    {"name": "property_migration_checklist", "description": "Checklist for safely migrating a site"}
  ],
  "keywords": ["google", "search-console", "gsc", "seo", "analytics", "indexing", "sitemap", "oauth"],
  "license": "MIT",
  "user_config": {
    "oauth_config_path": {
      "type": "string",
      "title": "OAuth Configuration Path",
      "description": "Full path to your Google Cloud OAuth 2.0 client credentials JSON file",
      "required": true
    },
    "mcp_user_email": {
      "type": "string",
      "title": "Your Google Account Email",
      "description": "Your Google account email — used to identify your stored credentials",
      "required": true
    }
  },
  "compatibility": {
    "claude_desktop": ">=0.10.0",
    "platforms": ["darwin", "win32", "linux"],
    "runtimes": {"python": ">=3.10.0 <4"}
  }
}
```

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass, no warnings about missing modules.

- [ ] **Step 4: Final commit**

```bash
git add setup_local_auth.py manifest.json README.md client_secret.json.example .env.example
git add -u  # stage any modified files
git commit -m "feat: add open-source prep — setup_local_auth, manifest.json, README"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Search Analytics: query with all dimensions + filters → `get_search_analytics`
- [x] Search Analytics: batch query → `batch_search_analytics`
- [x] Search Analytics: search type filter → `search_type` param on all analytics tools
- [x] Search Analytics: data freshness control → `data_state` param
- [x] Search Analytics: row limit pagination → `export_full_dataset`
- [x] Search Analytics: CTR optimization → `get_ctr_optimization_report`
- [x] Search Analytics: keyword cannibalization → `get_keyword_cannibalization`
- [x] Search Analytics: position band filtering → `get_position_band_report`
- [x] Sites: list, get, add, delete → Task 4
- [x] URL Inspection: single + batch with full fields → Task 7
- [x] Sitemaps: list, get, submit, delete + error classification → Task 8
- [x] Compare periods → `compare_periods`
- [x] `analyze_site_health` composite → Task 9
- [x] `identify_quick_wins` composite → Task 9
- [x] `export_full_dataset` → in search_analytics.py
- [x] `crawl_error_summary` → Task 9
- [x] `property_migration_checklist` → Task 9
- [x] Dockerfile → Task 11
- [x] Deploy script → Task 11
- [x] Rate limiting → gsc/client.py
- [x] Audit logging → gsc/client.py `_audit()`
- [x] Structured JSON response format → `format_response()` / `format_error()`
- [x] Unit tests with mocked API → Tasks 4–9
- [x] Open source prep → Task 12

**Gaps identified:**
- `add_site` and `delete_site` have no unit tests — add them to `tests/test_sites.py` (simple: mock `gsc_put`/`gsc_delete`, assert `success: True`)
- `export_full_dataset` has no unit test — add to `tests/test_search_analytics.py` (mock `gsc_post` to return two pages, assert pagination loops)
- Permission level enrichment (owner vs full vs restricted) on `list_properties` is present but sites don't expose verification method via API — documented in `get_site_details` response, which returns raw GSC response including `permissionLevel`

**Type consistency:**
- `_encode_site` used consistently across all modules
- `format_response` / `format_error` used consistently
- `_audit` called at top of every tool function
- `inspect_post` imported into `composite.py` directly from `gsc.client`
