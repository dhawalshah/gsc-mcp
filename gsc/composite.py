"""Cross-service composite GSC analysis tools."""
from typing import Dict, List, Optional
from .client import gsc_get, gsc_post, inspect_post, format_response, format_error, _encode_site, _audit
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
    body = {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "searchType": "web",
        "rowLimit": MAX_PAGES_FOR_HEALTH,
    }
    try:
        analytics_resp = gsc_post(f"sites/{_encode_site(site_url)}/searchAnalytics/query", body, site_url)
        top_rows = analytics_resp.get("rows", [])

        enriched = []
        for row in top_rows:
            page_url = row["keys"][0]
            traffic = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr_pct": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
            # Build absolute URL for inspection if page_url is a path
            inspect_url = page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url
            try:
                inspect_resp = inspect_post({"inspectionUrl": inspect_url, "siteUrl": site_url})
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
            inspect_url = page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url
            try:
                inspect_resp = inspect_post({"inspectionUrl": inspect_url, "siteUrl": site_url})
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


MAX_CRAWL_SAMPLE = 50


def crawl_error_summary(site_url: str, start_date: str, end_date: str, sample_size: int = 50) -> Dict:
    """Aggregate crawl and indexing errors across a property's sampled pages.

    Args:
        site_url: Property URL
        start_date / end_date: Date range (YYYY-MM-DD)
        sample_size: Number of pages to inspect (default: 50, max: 50)
    """
    _audit("crawl_error_summary", site_url)
    sample_size = min(sample_size, MAX_CRAWL_SAMPLE)
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
            inspect_url = page_url if page_url.startswith("http") else site_url.rstrip("/") + page_url
            try:
                inspect_resp = inspect_post({"inspectionUrl": inspect_url, "siteUrl": site_url})
                parsed = _parse_inspection_result(inspect_resp)
                if parsed.get("verdict") != "PASS":
                    errors.append({
                        "page": page_url,
                        "verdict": parsed.get("verdict"),
                        "state": parsed.get("coverage_state"),
                        "fetch_state": parsed.get("page_fetch_state"),
                    })
                if parsed.get("mobile_usability", {}).get("verdict") == "FAIL":
                    mobile_issues.append({
                        "page": page_url,
                        "issues": parsed["mobile_usability"]["issues"],
                    })
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
    """Generate a migration checklist when moving a site.

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
        {"item": "Set preferred domain in new GSC property", "status": "manual", "action": "GSC -> Settings -> Preferred domain"},
    ])

    return format_response(
        {"checklist": checklist, "data": data, "old_site": old_site_url, "new_site": new_site_url},
        site_url=old_site_url, date_range=[start_date, end_date],
    )
