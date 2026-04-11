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


def test_get_position_band_report_filters_correctly():
    from gsc.search_analytics import get_position_band_report
    mock_resp = {
        "rows": [
            {"keys": ["/page-a"], "clicks": 50.0, "impressions": 200.0, "ctr": 0.25, "position": 2.1},
            {"keys": ["/page-b"], "clicks": 10.0, "impressions": 500.0, "ctr": 0.02, "position": 7.5},
            {"keys": ["/page-c"], "clicks": 5.0, "impressions": 100.0, "ctr": 0.05, "position": 15.0},
        ]
    }
    with patch("gsc.search_analytics.gsc_post", return_value=mock_resp):
        result = get_position_band_report("https://example.com/", "2025-01-01", "2025-01-07", band="4-10")
    assert result["success"] is True
    pages = result["data"]["pages"]
    # Only page-b (position 7.5) is in 4-10 band
    assert len(pages) == 1
    assert pages[0]["page"] == "/page-b"
    assert pages[0]["position"] == 7.5


def test_get_position_band_report_invalid_band():
    from gsc.search_analytics import get_position_band_report
    result = get_position_band_report("https://example.com/", "2025-01-01", "2025-01-07", band="99-100")
    assert result["success"] is False
    assert result["error_code"] == "INVALID_PARAM"


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
    opportunities = result["data"]["opportunities"]
    # Only low-ctr qualifies (impressions>=100 AND ctr<2%)
    assert len(opportunities) == 1
    assert opportunities[0]["page"] == "/low-ctr"
    assert "suggestion" in opportunities[0]


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
    # Only "seo tips" has multiple pages
    assert len(conflicts) == 1
    assert conflicts[0]["query"] == "seo tips"
    assert len(conflicts[0]["pages"]) == 2
    assert "recommendation" in conflicts[0]


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
    assert result["data"]["total_queries"] == 2
    assert result["data"]["results"][0]["success"] is True


def test_export_full_dataset_paginates():
    from gsc.search_analytics import export_full_dataset
    # First call returns 5000 rows (full page), second returns 3 (partial = last page)
    page1 = {"rows": [{"keys": ["q", "/p"], "clicks": 1.0, "impressions": 10.0, "ctr": 0.1, "position": 5.0}] * 5000}
    page2 = {"rows": [{"keys": ["q2", "/p2"], "clicks": 2.0, "impressions": 20.0, "ctr": 0.1, "position": 6.0}] * 3}
    with patch("gsc.search_analytics.gsc_post", side_effect=[page1, page2]):
        result = export_full_dataset("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    assert result["metadata"]["rows_returned"] == 5003
    assert result["data"]["paginated"] is True
