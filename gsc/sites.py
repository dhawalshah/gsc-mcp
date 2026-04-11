"""GSC Sites (property) tools."""
from typing import Dict
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
