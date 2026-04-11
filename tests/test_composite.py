# tests/test_composite.py
import pytest
from unittest.mock import patch, MagicMock


MOCK_INSPECT_RESP = {
    "inspectionResult": {
        "inspectionResultLink": "https://search.google.com/inspect",
        "indexStatusResult": {
            "verdict": "PASS", "coverageState": "Submitted and indexed",
            "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED",
            "lastCrawlTime": "2025-01-10T08:00:00Z", "pageFetchState": "SUCCESSFUL",
            "googleCanonical": "https://example.com/top-page",
            "userCanonical": "https://example.com/top-page",
        },
        "mobileUsabilityResult": {"verdict": "PASS", "issues": []},
        "richResultsResult": {"verdict": "PASS", "detectedItems": []},
        "ampResult": None,
    }
}

MOCK_ANALYTICS = {
    "rows": [
        {"keys": ["/top-page"], "clicks": 500.0, "impressions": 5000.0, "ctr": 0.1, "position": 3.2},
    ]
}


def test_analyze_site_health_returns_top_pages():
    from gsc.composite import analyze_site_health
    with patch("gsc.composite.gsc_post", return_value=MOCK_ANALYTICS), \
         patch("gsc.composite.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = analyze_site_health("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    pages = result["data"]["top_pages"]
    assert len(pages) == 1
    assert pages[0]["url"] == "/top-page"
    assert pages[0]["traffic"]["clicks"] == 500.0
    assert pages[0]["indexing"]["verdict"] == "PASS"
    assert "summary" in result["data"]


def test_analyze_site_health_api_error():
    from gsc.composite import analyze_site_health
    import requests
    with patch("gsc.composite.gsc_post", side_effect=requests.HTTPError("403")):
        result = analyze_site_health("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is False


def test_identify_quick_wins():
    from gsc.composite import identify_quick_wins
    mock_resp = {
        "rows": [
            {"keys": ["/win-page"], "clicks": 5.0, "impressions": 500.0, "ctr": 0.01, "position": 6.5},
            {"keys": ["/good-ctr-page"], "clicks": 100.0, "impressions": 1000.0, "ctr": 0.1, "position": 2.0},
            {"keys": ["/low-impressions"], "clicks": 1.0, "impressions": 50.0, "ctr": 0.01, "position": 7.0},
        ]
    }
    with patch("gsc.composite.gsc_post", return_value=mock_resp), \
         patch("gsc.composite.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = identify_quick_wins("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    wins = result["data"]["quick_wins"]
    # /win-page: impressions=500>=100, ctr=1%<2%, position=6.5 in 4-10 range ✓
    # /good-ctr-page: ctr=10% fails max_ctr_pct=2% ✗
    # /low-impressions: impressions=50<100 ✗
    assert len(wins) == 1
    assert wins[0]["page"] == "/win-page"
    assert "suggestion" in wins[0]


def test_crawl_error_summary():
    from gsc.composite import crawl_error_summary
    fail_inspect = {
        "inspectionResult": {
            "inspectionResultLink": "https://search.google.com/inspect",
            "indexStatusResult": {
                "verdict": "FAIL", "coverageState": "Excluded",
                "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED",
                "lastCrawlTime": None, "pageFetchState": "SOFT_404",
                "googleCanonical": None, "userCanonical": "/broken",
            },
            "mobileUsabilityResult": {"verdict": "FAIL", "issues": [{"type": "MOBILE_ISSUE"}]},
            "richResultsResult": {"verdict": "NEUTRAL", "detectedItems": []},
            "ampResult": None,
        }
    }
    mock_resp = {
        "rows": [{"keys": ["/broken"], "clicks": 0.0, "impressions": 100.0, "ctr": 0.0, "position": 30.0}]
    }
    with patch("gsc.composite.gsc_post", return_value=mock_resp), \
         patch("gsc.composite.inspect_post", return_value=fail_inspect):
        result = crawl_error_summary("https://example.com/", "2025-01-01", "2025-01-07")
    assert result["success"] is True
    assert result["data"]["total_errors"] >= 1
    assert result["data"]["total_mobile_issues"] >= 1
    assert result["data"]["pages_sampled"] == 1


def test_property_migration_checklist():
    from gsc.composite import property_migration_checklist
    old_analytics = {"rows": [{"keys": ["/page-1"], "clicks": 100.0, "impressions": 1000.0, "ctr": 0.1, "position": 3.0}]}
    old_sitemaps = {"sitemap": [{"path": "https://old.com/sitemap.xml"}]}
    new_sites = {"siteEntry": [{"siteUrl": "https://new.com/", "permissionLevel": "siteOwner"}]}
    with patch("gsc.composite.gsc_post", return_value=old_analytics), \
         patch("gsc.composite.gsc_get", side_effect=[old_sitemaps, new_sites]):
        result = property_migration_checklist(
            "https://old.com/", "https://new.com/", "2025-01-01", "2025-01-07"
        )
    assert result["success"] is True
    checklist = result["data"]["checklist"]
    # Should have at least the 3 API-driven items + 4 manual items
    assert len(checklist) >= 7
    # New site found
    new_site_item = next((c for c in checklist if "new site" in c["item"].lower()), None)
    assert new_site_item is not None
    assert new_site_item["status"] == "done"
