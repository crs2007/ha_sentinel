"""Tests for maintenance-window scheduling behaviour in SentinelCoordinator."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_sentinel.models import SentinelConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**kwargs) -> SentinelConfig:
    defaults = dict(
        schedule_enabled=False,
        schedule_time="02:00",
        schedule_days=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    )
    defaults.update(kwargs)
    return SentinelConfig(**defaults)


def _make_coordinator(hass, config):
    """Create a SentinelCoordinator with UpdateManager and time-change listener mocked."""
    mock_manager = MagicMock()
    mock_manager.run_cycle = AsyncMock(return_value=[])

    with patch("custom_components.ha_sentinel.coordinator.UpdateManager", return_value=mock_manager), \
         patch("custom_components.ha_sentinel.coordinator.async_track_time_change") as mock_track:
        mock_track.return_value = MagicMock()  # unsub callable
        from custom_components.ha_sentinel.coordinator import SentinelCoordinator
        coordinator = SentinelCoordinator(hass, config)

    # _schedule_unsub is set inside the with block while patch is active;
    # coordinator.manager already holds mock_manager
    return coordinator, mock_track


# ---------------------------------------------------------------------------
# Poll-cycle install flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_installs_when_schedule_disabled(mock_hass):
    config = _config(schedule_enabled=False)
    coordinator, _ = _make_coordinator(mock_hass, config)

    await coordinator._async_update_data()

    coordinator.manager.run_cycle.assert_called_once_with(install=True)


@pytest.mark.asyncio
async def test_poll_skips_install_when_schedule_enabled(mock_hass):
    config = _config(schedule_enabled=True, schedule_time="02:00")
    coordinator, _ = _make_coordinator(mock_hass, config)

    await coordinator._async_update_data()

    coordinator.manager.run_cycle.assert_called_once_with(install=False)


# ---------------------------------------------------------------------------
# Listener registration
# ---------------------------------------------------------------------------

def test_no_listener_when_schedule_disabled(mock_hass):
    config = _config(schedule_enabled=False)
    _, mock_track = _make_coordinator(mock_hass, config)

    mock_track.assert_not_called()


def test_listener_registered_when_schedule_enabled(mock_hass):
    config = _config(schedule_enabled=True, schedule_time="03:30")
    _, mock_track = _make_coordinator(mock_hass, config)

    mock_track.assert_called_once()
    _args, kwargs = mock_track.call_args
    assert kwargs["hour"] == 3
    assert kwargs["minute"] == 30
    assert kwargs["second"] == 0


def test_listener_registered_with_hhmmss_format(mock_hass):
    """TimeSelector in HA returns HH:MM:SS — coordinator should handle it."""
    config = _config(schedule_enabled=True, schedule_time="22:15:00")
    _, mock_track = _make_coordinator(mock_hass, config)

    mock_track.assert_called_once()
    _args, kwargs = mock_track.call_args
    assert kwargs["hour"] == 22
    assert kwargs["minute"] == 15


def test_invalid_schedule_time_logs_error_and_skips_registration(mock_hass):
    config = _config(schedule_enabled=True, schedule_time="NOT_A_TIME")
    mock_manager = MagicMock()

    with patch("custom_components.ha_sentinel.coordinator.UpdateManager", return_value=mock_manager), \
         patch("custom_components.ha_sentinel.coordinator.async_track_time_change") as mock_track, \
         patch("custom_components.ha_sentinel.coordinator._LOGGER") as mock_logger:
        from custom_components.ha_sentinel.coordinator import SentinelCoordinator
        coordinator = SentinelCoordinator(mock_hass, config)

    mock_track.assert_not_called()
    mock_logger.error.assert_called_once()
    assert coordinator._schedule_unsub is None


# ---------------------------------------------------------------------------
# Scheduled install callback — day filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduled_install_fires_on_correct_day(mock_hass):
    # 2026-05-04 is a Monday (weekday=0 → "mon")
    config = _config(schedule_enabled=True, schedule_days=["mon"])
    coordinator, _ = _make_coordinator(mock_hass, config)

    monday = datetime(2026, 5, 4, 2, 0, 0, tzinfo=timezone.utc)
    await coordinator._scheduled_install(monday)

    coordinator.manager.run_cycle.assert_called_once_with(install=True)


@pytest.mark.asyncio
async def test_scheduled_install_skips_wrong_day(mock_hass):
    # Only allow Monday; fire on Tuesday
    config = _config(schedule_enabled=True, schedule_days=["mon"])
    coordinator, _ = _make_coordinator(mock_hass, config)

    tuesday = datetime(2026, 5, 5, 2, 0, 0, tzinfo=timezone.utc)
    await coordinator._scheduled_install(tuesday)

    coordinator.manager.run_cycle.assert_not_called()


@pytest.mark.asyncio
async def test_scheduled_install_fires_all_days_by_default(mock_hass):
    config = _config(schedule_enabled=True)  # default: all 7 days
    coordinator, _ = _make_coordinator(mock_hass, config)

    # 2026-05-04 is Monday; iterate Mon–Sun
    for day_offset in range(7):
        dt = datetime(2026, 5, 4 + day_offset, 2, 0, 0, tzinfo=timezone.utc)
        coordinator.manager.run_cycle.reset_mock()
        await coordinator._scheduled_install(dt)
        coordinator.manager.run_cycle.assert_called_once_with(install=True)


@pytest.mark.asyncio
async def test_scheduled_install_skips_when_days_empty(mock_hass):
    config = _config(schedule_enabled=True, schedule_days=[])
    coordinator, _ = _make_coordinator(mock_hass, config)

    for day_offset in range(7):
        dt = datetime(2026, 5, 4 + day_offset, 2, 0, 0, tzinfo=timezone.utc)
        await coordinator._scheduled_install(dt)

    coordinator.manager.run_cycle.assert_not_called()


# ---------------------------------------------------------------------------
# Cleanup / unsubscribe
# ---------------------------------------------------------------------------

def test_unsubscribe_calls_unsub_callable(mock_hass):
    mock_unsub = MagicMock()
    config = _config(schedule_enabled=True, schedule_time="02:00")
    mock_manager = MagicMock()

    with patch("custom_components.ha_sentinel.coordinator.UpdateManager", return_value=mock_manager), \
         patch(
             "custom_components.ha_sentinel.coordinator.async_track_time_change",
             return_value=mock_unsub,
         ):
        from custom_components.ha_sentinel.coordinator import SentinelCoordinator
        coordinator = SentinelCoordinator(mock_hass, config)

    coordinator.async_unsubscribe_schedule()

    mock_unsub.assert_called_once()
    assert coordinator._schedule_unsub is None


def test_unsubscribe_is_noop_when_schedule_disabled(mock_hass):
    config = _config(schedule_enabled=False)
    coordinator, _ = _make_coordinator(mock_hass, config)

    coordinator.async_unsubscribe_schedule()  # must not raise
    assert coordinator._schedule_unsub is None


def test_double_unsubscribe_is_safe(mock_hass):
    mock_unsub = MagicMock()
    config = _config(schedule_enabled=True, schedule_time="02:00")
    mock_manager = MagicMock()

    with patch("custom_components.ha_sentinel.coordinator.UpdateManager", return_value=mock_manager), \
         patch(
             "custom_components.ha_sentinel.coordinator.async_track_time_change",
             return_value=mock_unsub,
         ):
        from custom_components.ha_sentinel.coordinator import SentinelCoordinator
        coordinator = SentinelCoordinator(mock_hass, config)

    coordinator.async_unsubscribe_schedule()
    coordinator.async_unsubscribe_schedule()  # second call must not raise

    mock_unsub.assert_called_once()  # called exactly once, not twice
