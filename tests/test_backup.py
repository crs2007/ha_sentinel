"""Tests for backup.py — payload logic and create_backup integration."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_sentinel.backup import _build_payload, create_backup
from custom_components.ha_sentinel.models import UpdateCandidate


def _cand(provider: str = "core", slug: str = "core") -> UpdateCandidate:
    return UpdateCandidate(
        provider=provider,
        slug=slug,
        name="Test",
        current_version="1.0.0",
        new_version="1.1.0",
        backup_supported=True,
    )


# ── payload builder ───────────────────────────────────────────────────────────

def test_core_payload_uses_homeassistant_scope():
    payload = _build_payload(_cand(provider="core", slug="core"))
    assert payload is not None
    assert payload["homeassistant"] is True
    assert "name" in payload


def test_os_payload_uses_homeassistant_scope():
    payload = _build_payload(_cand(provider="core", slug="os"))
    assert payload is not None
    assert payload["homeassistant"] is True


def test_addon_payload_uses_addons_scope():
    payload = _build_payload(_cand(provider="addon", slug="core_ssh"))
    assert payload is not None
    assert payload["addons"] == ["core_ssh"]
    assert "name" in payload


def test_hacs_payload_is_none():
    payload = _build_payload(_cand(provider="hacs", slug="user/repo"))
    assert payload is None


def test_backup_name_contains_slug_and_version():
    payload = _build_payload(_cand(provider="addon", slug="mosquitto"))
    assert "mosquitto" in payload["name"]
    assert "1.1.0" in payload["name"]


# ── create_backup integration ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backup_skipped_without_supervisor_token():
    hass = MagicMock()
    c = _cand()
    with patch.dict(os.environ, {}, clear=True):
        result = await create_backup(hass, c)
    assert result is False


@pytest.mark.asyncio
async def test_backup_skipped_for_hacs_provider():
    hass = MagicMock()
    c = _cand(provider="hacs", slug="user/repo")
    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "tok"}):
        result = await create_backup(hass, c)
    assert result is False


@pytest.mark.asyncio
async def test_backup_returns_true_on_200(socket_enabled):
    mock_resp = AsyncMock()
    mock_resp.status = 200

    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_resp)

    hass = MagicMock()

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "tok"}), \
         patch("custom_components.ha_sentinel.backup.async_get_clientsession", return_value=mock_session):
        result = await create_backup(hass, _cand(provider="core", slug="core"))

    assert result is True
    mock_session.post.assert_called_once()
    _, kwargs = mock_session.post.call_args
    assert kwargs["json"]["homeassistant"] is True


@pytest.mark.asyncio
async def test_backup_returns_false_on_non_200(socket_enabled):
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.text = AsyncMock(return_value="internal error")

    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_resp)

    hass = MagicMock()

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "tok"}), \
         patch("custom_components.ha_sentinel.backup.async_get_clientsession", return_value=mock_session):
        result = await create_backup(hass, _cand(provider="addon", slug="core_ssh"))

    assert result is False


@pytest.mark.asyncio
async def test_backup_returns_false_on_exception(socket_enabled):
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(side_effect=OSError("connection refused"))

    hass = MagicMock()

    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "tok"}), \
         patch("custom_components.ha_sentinel.backup.async_get_clientsession", return_value=mock_session):
        result = await create_backup(hass, _cand(provider="addon", slug="core_ssh"))

    assert result is False


# ── backup_supported flag on providers ────────────────────────────────────────

def test_addon_candidates_have_backup_supported():
    from custom_components.ha_sentinel.models import UpdateCandidate
    c = UpdateCandidate(
        provider="addon", slug="core_ssh", name="SSH", backup_supported=True,
        current_version="10.1.0", new_version="10.2.0",
    )
    assert c.backup_supported is True


def test_hacs_candidates_do_not_have_backup_supported():
    from custom_components.ha_sentinel.models import UpdateCandidate
    c = UpdateCandidate(
        provider="hacs", slug="user/repo", name="Repo", backup_supported=False,
        current_version="1.0", new_version="1.1",
    )
    assert c.backup_supported is False
