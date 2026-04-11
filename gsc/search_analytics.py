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
