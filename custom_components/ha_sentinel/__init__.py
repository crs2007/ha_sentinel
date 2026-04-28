"""HA Sentinel — safe auto-update integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SERVICE_CHECK_NOW, SERVICE_INSTALL_NOW
from .coordinator import SentinelCoordinator
from .models import SentinelConfig

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    config = SentinelConfig.from_options(dict(entry.options))
    coordinator = SentinelCoordinator(hass, config)
    await coordinator.manager.async_init()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    unsub_timer = async_track_time_interval(
        hass,
        lambda _: hass.async_create_task(coordinator.async_refresh()),
        timedelta(hours=config.check_interval_hours),
    )
    entry.async_on_unload(unsub_timer)

    async def handle_check_now(call: ServiceCall) -> None:
        await coordinator.manager.check_now()

    async def handle_install_now(call: ServiceCall) -> None:
        slug = call.data.get("slug", "")
        if slug:
            await coordinator.manager.install_slug(slug)

    hass.services.async_register(DOMAIN, SERVICE_CHECK_NOW, handle_check_now)
    hass.services.async_register(DOMAIN, SERVICE_INSTALL_NOW, handle_install_now)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    hass.services.async_remove(DOMAIN, SERVICE_CHECK_NOW)
    hass.services.async_remove(DOMAIN, SERVICE_INSTALL_NOW)
    return True
