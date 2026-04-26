"""Tests for HACS provider — including graceful degradation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ha_sentinel.providers.hacs import HacsProvider


def _hass_without_hacs():
    hass = MagicMock()
    hass.data = {}
    return hass


def _hass_with_hacs(repos=None):
    hass = MagicMock()
    mock_repo = MagicMock()
    mock_repo.pending_update = True
    mock_repo.data.installed_version = "1.0.0"
    mock_repo.data.last_version = "1.1.0"
    mock_repo.data.full_name = "user/my-integration"
    mock_repo.data.name = "My Integration"

    mock_hacs = MagicMock()
    mock_hacs.repositories.list_all = repos if repos is not None else [mock_repo]
    hass.data = {"hacs": mock_hacs}
    return hass


def test_unavailable_when_hacs_not_installed():
    provider = HacsProvider(_hass_without_hacs())
    assert provider.available is False


def test_available_when_hacs_installed():
    provider = HacsProvider(_hass_with_hacs())
    assert provider.available is True


@pytest.mark.asyncio
async def test_fetch_returns_empty_when_hacs_missing():
    provider = HacsProvider(_hass_without_hacs())
    result = await provider.fetch_candidates()
    assert result == []


@pytest.mark.asyncio
async def test_fetch_returns_candidates():
    provider = HacsProvider(_hass_with_hacs())
    result = await provider.fetch_candidates()
    assert len(result) == 1
    assert result[0].slug == "user/my-integration"
    assert result[0].new_version == "1.1.0"
    assert result[0].provider == "hacs"


@pytest.mark.asyncio
async def test_fetch_skips_repos_without_update():
    hass = MagicMock()
    mock_repo = MagicMock()
    mock_repo.pending_update = False
    mock_hacs = MagicMock()
    mock_hacs.repositories.list_all = [mock_repo]
    hass.data = {"hacs": mock_hacs}

    provider = HacsProvider(hass)
    result = await provider.fetch_candidates()
    assert result == []


@pytest.mark.asyncio
async def test_install_no_op_when_hacs_missing():
    from custom_components.ha_sentinel.models import UpdateCandidate  # noqa: PLC0415
    provider = HacsProvider(_hass_without_hacs())
    c = UpdateCandidate(provider="hacs", slug="x", name="X", current_version="1.0", new_version="1.1")
    await provider.install(c)  # should not raise
