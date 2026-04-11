# tests/test_sitemaps.py
import pytest
from unittest.mock import patch


MOCK_SITEMAP = {
    "path": "https://example.com/sitemap.xml",
    "lastSubmitted": "2025-01-01T00:00:00Z",
    "isPending": False,
    "isSitemapsIndex": False,
    "type": "sitemap",
    "lastDownloaded": "2025-01-02T00:00:00Z",
    "warnings": 0,
    "errors": 2,
    "contents": [
        {"type": "web", "submitted": 100, "indexed": 95}
    ],
}


def test_list_sitemaps_returns_parsed_data():
    from gsc.sitemaps import list_sitemaps
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [MOCK_SITEMAP]}):
        result = list_sitemaps("https://example.com/")
    assert result["success"] is True
    assert len(result["data"]["sitemaps"]) == 1
    s = result["data"]["sitemaps"][0]
    assert s["path"] == "https://example.com/sitemap.xml"
    assert s["submitted"] == 100
    assert s["indexed"] == 95
    assert s["errors"] == 2


def test_list_sitemaps_health_good():
    from gsc.sitemaps import list_sitemaps
    good = {**MOCK_SITEMAP, "errors": 0, "contents": [{"type": "web", "submitted": 100, "indexed": 98}]}
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [good]}):
        result = list_sitemaps("https://example.com/")
    assert result["data"]["sitemaps"][0]["health"] == "good"


def test_list_sitemaps_health_poor():
    from gsc.sitemaps import list_sitemaps
    bad = {**MOCK_SITEMAP, "errors": 90, "contents": [{"type": "web", "submitted": 100, "indexed": 10}]}
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [bad]}):
        result = list_sitemaps("https://example.com/")
    assert result["data"]["sitemaps"][0]["health"] == "poor"


def test_list_sitemaps_includes_health_summary():
    from gsc.sitemaps import list_sitemaps
    with patch("gsc.sitemaps.gsc_get", return_value={"sitemap": [MOCK_SITEMAP]}):
        result = list_sitemaps("https://example.com/")
    assert "health_summary" in result["data"]
    assert "alerts" in result["data"]


def test_list_sitemaps_empty():
    from gsc.sitemaps import list_sitemaps
    with patch("gsc.sitemaps.gsc_get", return_value={}):
        result = list_sitemaps("https://example.com/")
    assert result["success"] is True
    assert result["data"]["sitemaps"] == []
    assert result["data"]["total"] == 0


def test_get_sitemap():
    from gsc.sitemaps import get_sitemap
    with patch("gsc.sitemaps.gsc_get", return_value=MOCK_SITEMAP):
        result = get_sitemap("https://example.com/", "https://example.com/sitemap.xml")
    assert result["success"] is True
    assert result["data"]["path"] == "https://example.com/sitemap.xml"


def test_submit_sitemap():
    from gsc.sitemaps import submit_sitemap
    with patch("gsc.sitemaps.gsc_put", return_value={}):
        result = submit_sitemap("https://example.com/", "https://example.com/sitemap-new.xml")
    assert result["success"] is True
    assert result["data"]["submitted"] == "https://example.com/sitemap-new.xml"


def test_delete_sitemap():
    from gsc.sitemaps import delete_sitemap
    with patch("gsc.sitemaps.gsc_delete", return_value={}):
        result = delete_sitemap("https://example.com/", "https://example.com/sitemap.xml")
    assert result["success"] is True
    assert result["data"]["deleted"] == "https://example.com/sitemap.xml"
