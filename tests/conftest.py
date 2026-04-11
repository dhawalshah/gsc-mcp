"""Pytest configuration and shared fixtures."""
import pytest


@pytest.fixture(autouse=True)
def reset_rate_limit_windows():
    """Reset rate-limit state before every test so tests don't bleed into each other."""
    import gsc.client as client
    client._rate_windows.clear()
    yield
    client._rate_windows.clear()
