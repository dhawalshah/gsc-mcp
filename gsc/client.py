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
    _check_rate_limit(email)
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
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.get(url, headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def gsc_post(path: str, body: Dict, site_url: str = "") -> Dict:
    """POST request to GSC webmasters API."""
    headers = get_headers_with_auto_token()
    headers["Content-Type"] = "application/json"
    url = f"{GSC_BASE}/{path}"
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


def gsc_put(path: str, site_url: str = "") -> Dict:
    """PUT request to GSC webmasters API (for add site / submit sitemap)."""
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.put(url, headers=headers)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def gsc_delete(path: str, site_url: str = "") -> Dict:
    """DELETE request to GSC webmasters API."""
    headers = get_headers_with_auto_token()
    url = f"{GSC_BASE}/{path}"
    resp = requests.delete(url, headers=headers)
    resp.raise_for_status()
    return {}


def inspect_post(body: Dict) -> Dict:
    """POST request to URL Inspection API v1."""
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
