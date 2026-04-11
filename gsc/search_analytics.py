"""GSC Search Analytics tools."""
from typing import Any, Dict, List, Optional
from .client import gsc_post, format_response, format_error, _encode_site, _audit

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
    search_type: str = "web",
) -> Dict:
    """Compare search performance between two date periods.

    Args:
        site_url: Property URL
        current_start / current_end: Current period (YYYY-MM-DD)
        previous_start / previous_end: Comparison period (YYYY-MM-DD)
        search_type: One of: web, image, video, news, discover, googleNews
    """
    _audit("compare_periods", site_url)

    def _query(start, end):
        body: Dict[str, Any] = {
            "startDate": start, "endDate": end,
            "searchType": search_type, "rowLimit": 1,
        }
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


def get_position_band_report(
    site_url: str,
    start_date: str,
    end_date: str,
    band: str = "4-10",
    search_type: str = "web",
) -> Dict:
    """Get pages filtered by position band.

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
