"""GSC URL Inspection tools."""
from typing import Dict, List
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
            "verdict": amp.get("verdict"),
            "issues": amp.get("issues", []),
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


MAX_BATCH_URLS = 20


def batch_url_inspection(urls: List[str], site_url: str) -> Dict:
    """Inspect multiple URLs for indexing status, mobile usability, and rich results.

    Args:
        urls: List of page URLs to inspect (max 20 per call)
        site_url: The GSC property URL
    """
    _audit("batch_url_inspection", site_url)
    urls = urls[:MAX_BATCH_URLS]
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
