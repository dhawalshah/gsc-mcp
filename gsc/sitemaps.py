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
