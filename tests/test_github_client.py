"""Tests for GitHubClient — URL parsing and HTTP response handling."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_sentinel.github_client import GitHubClient


def _make_client(resp_status: int = 200, resp_json: dict | None = None, raise_exc: Exception | None = None):
    """Return a GitHubClient backed by a mock aiohttp session."""
    mock_resp = MagicMock()
    mock_resp.status = resp_status
    mock_resp.json = AsyncMock(return_value=resp_json or {})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    if raise_exc:
        mock_session.get.side_effect = raise_exc
    else:
        mock_session.get.return_value = mock_resp

    return GitHubClient(mock_session)


VALID_URL = "https://github.com/home-assistant/core/releases/tag/2024.1.0"
EXPECTED_DT = datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_valid_github_url_returns_date():
    client = _make_client(resp_json={"published_at": "2024-01-03T12:00:00Z"})
    result = await client.get_release_date(VALID_URL)
    assert result == EXPECTED_DT


@pytest.mark.asyncio
async def test_non_github_url_returns_none():
    client = _make_client()
    result = await client.get_release_date("https://example.com/release/1.0.0")
    assert result is None
    client._session.get.assert_not_called()


@pytest.mark.asyncio
async def test_empty_url_returns_none():
    client = _make_client()
    result = await client.get_release_date("")
    assert result is None


@pytest.mark.asyncio
async def test_none_url_returns_none():
    client = _make_client()
    result = await client.get_release_date(None)  # type: ignore[arg-type]
    assert result is None


@pytest.mark.asyncio
async def test_http_404_returns_none():
    client = _make_client(resp_status=404)
    result = await client.get_release_date(VALID_URL)
    assert result is None


@pytest.mark.asyncio
async def test_http_403_rate_limit_returns_none():
    client = _make_client(resp_status=403)
    result = await client.get_release_date(VALID_URL)
    assert result is None


@pytest.mark.asyncio
async def test_missing_published_at_returns_none():
    client = _make_client(resp_json={"name": "2024.1.0"})
    result = await client.get_release_date(VALID_URL)
    assert result is None


@pytest.mark.asyncio
async def test_network_error_returns_none():
    client = _make_client(raise_exc=OSError("network unreachable"))
    result = await client.get_release_date(VALID_URL)
    assert result is None


@pytest.mark.asyncio
async def test_hacs_repo_url_parses_correctly():
    url = "https://github.com/hacs/integration/releases/tag/2.0.1"
    client = _make_client(resp_json={"published_at": "2024-06-01T08:00:00Z"})
    result = await client.get_release_date(url)
    assert result == datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
