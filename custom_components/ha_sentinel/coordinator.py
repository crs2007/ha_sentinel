"""DataUpdateCoordinator wrapper for HA Sentinel."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import SentinelConfig
from .update_manager import UpdateManager

if TYPE_CHECKING:
    import datetime as dt

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Maps Python weekday() index (Mon=0 … Sun=6) to schedule_days token
_WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class SentinelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: "HomeAssistant", config: SentinelConfig) -> None:
        self.config = config
        self.manager = UpdateManager(hass, config)
        self._schedule_unsub: Callable[[], None] | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="ha_sentinel",
            update_interval=timedelta(hours=config.check_interval_hours),
        )
        self._setup_schedule()

    # ------------------------------------------------------------------
    # Scheduled install support
    # ------------------------------------------------------------------

    def _setup_schedule(self) -> None:
        """Register async_track_time_change when schedule_enabled=True."""
        if not self.config.schedule_enabled:
            return

        try:
            parts = self.config.schedule_time.split(":")
            hour, minute = int(parts[0]), int(parts[1])
        except (ValueError, AttributeError, IndexError):
            _LOGGER.error(
                "Invalid schedule_time %r — expected HH:MM. Maintenance window disabled.",
                self.config.schedule_time,
            )
            return

        self._schedule_unsub = async_track_time_change(
            self.hass,
            self._scheduled_install,
            hour=hour,
            minute=minute,
            second=0,
        )
        _LOGGER.debug(
            "Maintenance window scheduled: %02d:%02d on %s",
            hour,
            minute,
            ", ".join(self.config.schedule_days),
        )

    async def _scheduled_install(self, now: "dt.datetime") -> None:
        """Callback fired by async_track_time_change; installs only on scheduled days."""
        day_token = _WEEKDAY_NAMES[now.weekday()]
        if day_token not in self.config.schedule_days:
            _LOGGER.debug(
                "Maintenance window skipped: %s not in configured days %s",
                day_token,
                self.config.schedule_days,
            )
            return
        _LOGGER.info("Maintenance window triggered — running install cycle")
        await self.manager.run_cycle(install=True)

    def async_unsubscribe_schedule(self) -> None:
        """Unsubscribe the time-change listener. Called on entry unload."""
        if self._schedule_unsub is not None:
            self._schedule_unsub()
            self._schedule_unsub = None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator polling
    # ------------------------------------------------------------------

    async def _async_update_data(self):
        # When schedule is active, polling cycles are check-only (no installs).
        # The scheduled listener handles actual installs.
        install = not self.config.schedule_enabled
        return await self.manager.run_cycle(install=install)
