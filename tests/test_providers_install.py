"""Install-path error handling (issue #2)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.ha_sentinel.models import UpdateCandidate
from custom_components.ha_sentinel.providers.addon import AddonProvider
from custom_components.ha_sentinel.providers.core import CoreProvider
from custom_components.ha_sentinel.providers.hacs import HacsProvider


def _cand(provider, slug):
    return UpdateCandidate(provider=provider, slug=slug, name=slug, current_version="1", new_version="2")


def _session(status=200, body=None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=None if status < 400 else aiohttp.ClientResponseError(MagicMock(), (), status=status)
    )
    resp.json = AsyncMock(return_value={"result": "ok"} if body is None else body)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post = MagicMock(return_value=cm)
    return session


def _addon(session):
    with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "t"}):
        p = AddonProvider(MagicMock())
    return p, patch("custom_components.ha_sentinel.providers.addon.async_get_clientsession", return_value=session)


@pytest.mark.asyncio
async def test_addon_install_ok():
    p, patcher = _addon(_session())
    with patcher:
        await p.install(_cand("addon", "core_ssh"))


@pytest.mark.asyncio
async def test_addon_install_http_error_raises():
    p, patcher = _addon(_session(status=500))
    with patcher, pytest.raises(aiohttp.ClientResponseError):
        await p.install(_cand("addon", "core_ssh"))


@pytest.mark.asyncio
async def test_addon_install_result_not_ok_raises():
    p, patcher = _addon(_session(body={"result": "error", "message": "nope"}))
    with patcher, pytest.raises(RuntimeError):
        await p.install(_cand("addon", "core_ssh"))


@pytest.mark.asyncio
async def test_core_unknown_slug_raises():
    with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "t"}):
        p = CoreProvider(MagicMock())
    with pytest.raises(ValueError):
        await p.install(_cand("core", "bogus"))


@pytest.mark.asyncio
async def test_core_install_http_error_raises():
    with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "t"}):
        p = CoreProvider(MagicMock())
    with patch("custom_components.ha_sentinel.providers.core.async_get_clientsession", return_value=_session(status=403)):
        with pytest.raises(aiohttp.ClientResponseError):
            await p.install(_cand("core", "core"))


@pytest.mark.asyncio
async def test_hacs_install_error_propagates():
    hass = MagicMock()
    repo = MagicMock()
    repo.async_install = AsyncMock(side_effect=RuntimeError("boom"))
    hass.data = {"hacs": MagicMock()}
    hass.data["hacs"].repositories.get_by_full_name.return_value = repo
    with pytest.raises(RuntimeError):
        await HacsProvider(hass).install(_cand("hacs", "a/b"))


@pytest.mark.asyncio
async def test_hacs_install_repo_not_found_raises():
    hass = MagicMock()
    hass.data = {"hacs": MagicMock()}
    hass.data["hacs"].repositories.get_by_full_name.return_value = None
    with pytest.raises(ValueError):
        await HacsProvider(hass).install(_cand("hacs", "a/b"))
