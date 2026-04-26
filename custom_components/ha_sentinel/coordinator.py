"""DataUpdateCoordinator wrapper for HA Sentinel."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import SentinelConfig
from .update_manager import UpdateManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SentinelCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: "HomeAssistant", config: SentinelConfig) -> None:
        self.manager = UpdateManager(hass, config)
        super().__init__(
            hass,
            _LOGGER,
            name="ha_sentinel",
            update_interval=timedelta(hours=config.check_interval_hours),
        )

    async def _async_update_data(self):
        return await self.manager.run_cycle()
