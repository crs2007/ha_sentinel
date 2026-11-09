"""HA Sentinel — safe auto-update integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from . import notifier
from .const import DOMAIN, SERVICE_CHECK_NOW, SERVICE_DISMISS, SERVICE_INSTALL_NOW
from .coordinator import SentinelCoordinator
from .models import SentinelConfig

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    config = SentinelConfig.from_options(dict(entry.options))
    coordinator = SentinelCoordinator(hass, config, entry)
    await coordinator.manager.async_init()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # No entities subscribe to the coordinator, so keep it polling explicitly.
    entry.async_on_unload(coordinator.async_keep_polling())
    await coordinator.async_config_entry_first_refresh()

    async def handle_check_now(call: ServiceCall) -> None:
        await coordinator.manager.check_now()

    async def handle_install_now(call: ServiceCall) -> None:
        await coordinator.manager.install_slug(
            call.data["slug"], call.data.get("provider")
        )

    hass.services.async_register(DOMAIN, SERVICE_CHECK_NOW, handle_check_now)
    async def handle_dismiss(call: ServiceCall) -> None:
        notifier.dismiss(hass)

    hass.services.async_register(DOMAIN, SERVICE_DISMISS, handle_dismiss)
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_INSTALL_NOW,
        handle_install_now,
        schema=vol.Schema(
            {
                vol.Required("slug"): cv.string,
                vol.Optional("provider"): vol.In(["core", "addon", "hacs"]),
            }
        ),
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(coordinator.async_unsubscribe_schedule)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    hass.services.async_remove(DOMAIN, SERVICE_CHECK_NOW)
    hass.services.async_remove(DOMAIN, SERVICE_INSTALL_NOW)
    hass.services.async_remove(DOMAIN, SERVICE_DISMISS)
    return True
