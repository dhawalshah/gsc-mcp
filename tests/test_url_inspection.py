# tests/test_url_inspection.py
import pytest
from unittest.mock import patch


MOCK_INSPECT_RESP = {
    "inspectionResult": {
        "inspectionResultLink": "https://search.google.com/search-console/inspect?...",
        "indexStatusResult": {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "robotsTxtState": "ALLOWED",
            "indexingState": "INDEXING_ALLOWED",
            "lastCrawlTime": "2025-01-10T08:00:00Z",
            "pageFetchState": "SUCCESSFUL",
            "googleCanonical": "https://example.com/page",
            "userCanonical": "https://example.com/page",
        },
        "mobileUsabilityResult": {"verdict": "PASS", "issues": []},
        "richResultsResult": {
            "verdict": "PASS",
            "detectedItems": [{"richResultType": "FAQ"}],
        },
        "ampResult": None,
    }
}


def test_inspect_url_returns_all_fields():
    from gsc.url_inspection import inspect_url
    with patch("gsc.url_inspection.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = inspect_url("https://example.com/page", "https://example.com/")
    assert result["success"] is True
    data = result["data"]
    assert data["verdict"] == "PASS"
    assert data["coverage_state"] == "Submitted and indexed"
    assert data["last_crawl_time"] == "2025-01-10T08:00:00Z"
    assert data["mobile_usability"]["verdict"] == "PASS"
    assert data["mobile_usability"]["issues"] == []
    assert data["rich_results"]["verdict"] == "PASS"
    assert data["rich_results"]["detected_items"] == [{"richResultType": "FAQ"}]
    assert data["amp"] is None  # ampResult was None
    assert data["inspection_link"] is not None


def test_inspect_url_api_error():
    from gsc.url_inspection import inspect_url
    import requests
    with patch("gsc.url_inspection.inspect_post", side_effect=requests.HTTPError("403")):
        result = inspect_url("https://example.com/page", "https://example.com/")
    assert result["success"] is False
    assert "403" in result["error"]


def test_batch_url_inspection_all_pass():
    from gsc.url_inspection import batch_url_inspection
    with patch("gsc.url_inspection.inspect_post", return_value=MOCK_INSPECT_RESP):
        result = batch_url_inspection(
            ["https://example.com/page-1", "https://example.com/page-2"],
            "https://example.com/",
        )
    assert result["success"] is True
    assert len(result["data"]["results"]) == 2
    assert result["data"]["results"][0]["url"] == "https://example.com/page-1"
    assert result["data"]["results"][0]["verdict"] == "PASS"
    assert result["data"]["summary"]["total"] == 2
    assert result["data"]["summary"]["passed"] == 2
    assert result["data"]["summary"]["failed"] == 0


def test_batch_url_inspection_partial_failure():
    from gsc.url_inspection import batch_url_inspection
    import requests
    # First URL succeeds, second fails
    with patch("gsc.url_inspection.inspect_post", side_effect=[MOCK_INSPECT_RESP, requests.HTTPError("500")]):
        result = batch_url_inspection(
            ["https://example.com/ok", "https://example.com/fail"],
            "https://example.com/",
        )
    assert result["success"] is True  # Overall call succeeds even if some URLs fail
    assert len(result["data"]["results"]) == 2
    assert result["data"]["results"][0]["success"] is True
    assert result["data"]["results"][1]["success"] is False
    assert "500" in result["data"]["results"][1]["error"]


def test_inspect_url_with_amp_result():
    from gsc.url_inspection import inspect_url
    resp_with_amp = dict(MOCK_INSPECT_RESP)
    resp_with_amp["inspectionResult"] = dict(MOCK_INSPECT_RESP["inspectionResult"])
    resp_with_amp["inspectionResult"]["ampResult"] = {
        "verdict": "PASS",
        "issues": []
    }
    with patch("gsc.url_inspection.inspect_post", return_value=resp_with_amp):
        result = inspect_url("https://example.com/amp-page", "https://example.com/")
    assert result["success"] is True
    assert result["data"]["amp"] is not None
    assert result["data"]["amp"]["verdict"] == "PASS"
