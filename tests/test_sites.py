"""Tests for GSC Sites (property) tools."""
import pytest
from unittest.mock import patch, MagicMock


def test_list_properties_returns_sites():
    from gsc.sites import list_properties
    mock_resp = {
        "siteEntry": [
            {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
            {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteFullUser"},
        ]
    }
    with patch("gsc.sites.gsc_get", return_value=mock_resp):
        result = list_properties()
    assert result["success"] is True
    assert len(result["data"]["sites"]) == 2
    assert result["data"]["sites"][0]["siteUrl"] == "https://example.com/"
    assert result["data"]["sites"][0]["permissionLevel"] == "siteOwner"


def test_list_properties_empty():
    from gsc.sites import list_properties
    with patch("gsc.sites.gsc_get", return_value={}):
        result = list_properties()
    assert result["success"] is True
    assert result["data"]["sites"] == []


def test_get_site_details_returns_details():
    from gsc.sites import get_site_details
    mock_resp = {
        "siteUrl": "https://example.com/",
        "permissionLevel": "siteOwner",
    }
    with patch("gsc.sites.gsc_get", return_value=mock_resp):
        result = get_site_details("https://example.com/")
    assert result["success"] is True
    assert result["data"]["siteUrl"] == "https://example.com/"


def test_get_site_details_api_error():
    from gsc.sites import get_site_details
    import requests
    with patch("gsc.sites.gsc_get", side_effect=requests.HTTPError("404")):
        result = get_site_details("https://notfound.com/")
    assert result["success"] is False
    assert "404" in result["error"]


def test_add_site_returns_success():
    from gsc.sites import add_site
    with patch("gsc.sites.gsc_put", return_value={}):
        result = add_site("https://newsite.com/")
    assert result["success"] is True
    assert result["data"]["added"] == "https://newsite.com/"


def test_delete_site_returns_success():
    from gsc.sites import delete_site
    with patch("gsc.sites.gsc_delete", return_value={}):
        result = delete_site("https://oldsite.com/")
    assert result["success"] is True
    assert result["data"]["deleted"] == "https://oldsite.com/"
