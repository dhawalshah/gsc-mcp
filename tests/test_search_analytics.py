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


def test_get_search_analytics_invalid_search_type():
    from gsc.search_analytics import get_search_analytics
    result = get_search_analytics("https://example.com/", "2025-01-01", "2025-01-07", search_type="invalid")
    assert result["success"] is False
    assert result["error_code"] == "INVALID_PARAM"


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
    assert result["data"]["summary"]["average_ctr"] == 5.0  # 0.05 * 100


def test_get_performance_overview_empty_rows():
    from gsc.search_analytics import get_performance_overview
    with patch("gsc.search_analytics.gsc_post", return_value={"rows": []}):
        result = get_performance_overview("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    assert result["data"]["summary"]["total_clicks"] == 0


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
