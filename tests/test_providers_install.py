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


@pytest.mark.asyncio
async def test_addon_fetch_http_error_propagates():
    p, patcher = _addon(_session(status=401))
    session = _session(status=401)
    session.get = session.post
    with patch("custom_components.ha_sentinel.providers.addon.async_get_clientsession", return_value=session):
        with pytest.raises(aiohttp.ClientResponseError):
            await p.fetch_candidates()


def test_summary_lists_provider_errors():
    from custom_components.ha_sentinel.notifier import build_summary

    assert "Provider errors: addon (HTTP 401)" in build_summary([], {"addon": "HTTP 401"})


@pytest.mark.asyncio
async def test_notifier_dedups_and_dismisses_stale():
    from custom_components.ha_sentinel import notifier
    from custom_components.ha_sentinel.models import Decision

    hass = MagicMock()
    hass.data = {}
    res = [(_cand("addon", "x"), Decision("NOTIFY_ONLY", "r"), None)]
    with patch.object(notifier, "async_create") as create, patch.object(notifier, "async_dismiss") as dismiss:
        await notifier.notify_summary(hass, res)
        await notifier.notify_summary(hass, res)  # identical -> skipped
        assert create.call_count == 1
        await notifier.notify_summary(hass, [])  # nothing left -> dismissed
        dismiss.assert_called_once()


def _get_session(responses):
    """responses: {path_suffix: (status, json_or_text)}"""
    def get(url, **kw):
        status, body = next(v for k, v in responses.items() if url.endswith(k))
        resp = MagicMock()
        resp.status = status
        resp.raise_for_status = MagicMock(
            side_effect=None if status < 400 else aiohttp.ClientResponseError(MagicMock(), (), status=status)
        )
        resp.json = AsyncMock(return_value=body)
        resp.text = AsyncMock(return_value=body if isinstance(body, str) else "")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    s = MagicMock()
    s.get = get
    return s


@pytest.mark.asyncio
async def test_core_fetch_tolerates_404_and_reports_candidates():
    with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "t"}):
        p = CoreProvider(MagicMock())
    s = _get_session({
        "/core/info": (200, {"data": {"version": "2026.10.0", "version_latest": "2026.11.0"}}),
        "/os/info": (404, {}),
        "/supervisor/info": (200, {"data": {"version": "1", "version_latest": "1"}}),
    })
    with patch("custom_components.ha_sentinel.providers.core.async_get_clientsession", return_value=s):
        cands = await p.fetch_candidates()
    assert [c.slug for c in cands] == ["core"]


@pytest.mark.asyncio
async def test_core_fetch_raises_when_all_endpoints_fail():
    with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "t"}):
        p = CoreProvider(MagicMock())
    s = _get_session({"/info": (401, {})})
    with patch("custom_components.ha_sentinel.providers.core.async_get_clientsession", return_value=s):
        with pytest.raises(RuntimeError):
            await p.fetch_candidates()


@pytest.mark.asyncio
async def test_addon_fetch_returns_candidate_with_changelog():
    p, _ = _addon(None)
    s = _get_session({
        "/addons": (200, {"data": {"addons": [
            {"slug": "a", "name": "A", "version": "1.0", "version_latest": "2.0", "update_available": True},
            {"slug": "b", "name": "B", "version": "1.0", "version_latest": "1.0", "update_available": False},
        ]}}),
        "/a/changelog": (200, "BREAKING CHANGE: x"),
    })
    with patch("custom_components.ha_sentinel.providers.addon.async_get_clientsession", return_value=s):
        cands = await p.fetch_candidates()
    assert [c.slug for c in cands] == ["a"]
    assert "BREAKING" in cands[0].release_notes
