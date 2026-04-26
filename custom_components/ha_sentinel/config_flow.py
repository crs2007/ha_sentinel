"""ConfigFlow and OptionsFlow for HA Sentinel."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    ALL_PROVIDERS,
    CONF_ALLOWLIST,
    CONF_BACKUP_BEFORE_UPGRADE,
    CONF_BLOCKLIST,
    CONF_BREAKING_THRESHOLD,
    CONF_CHECK_INTERVAL_HOURS,
    CONF_DRY_RUN,
    CONF_ENABLED_PROVIDERS,
    CONF_IGNORE_BETA,
    CONF_PAUSE_ON_BREAKING,
    CONF_STABILITY_DELAY_DAYS,
    DEFAULT_BACKUP_BEFORE_UPGRADE,
    DEFAULT_BREAKING_THRESHOLD,
    DEFAULT_CHECK_INTERVAL_HOURS,
    DEFAULT_DRY_RUN,
    DEFAULT_IGNORE_BETA,
    DEFAULT_PAUSE_ON_BREAKING,
    DEFAULT_STABILITY_DELAY_DAYS,
    DOMAIN,
)


class SentinelConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="HA Sentinel", data={})

        return self.async_show_form(
            step_id="user",
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "SentinelOptionsFlow":
        return SentinelOptionsFlow(config_entry)


class SentinelOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        opts = self.config_entry.options

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_DRY_RUN, default=opts.get(CONF_DRY_RUN, DEFAULT_DRY_RUN)): bool,
                vol.Required(
                    CONF_BACKUP_BEFORE_UPGRADE,
                    default=opts.get(CONF_BACKUP_BEFORE_UPGRADE, DEFAULT_BACKUP_BEFORE_UPGRADE),
                ): bool,
                vol.Required(
                    CONF_ENABLED_PROVIDERS,
                    default=opts.get(CONF_ENABLED_PROVIDERS, ALL_PROVIDERS),
                ): vol.All([vol.In(ALL_PROVIDERS)]),
                vol.Required(
                    CONF_IGNORE_BETA, default=opts.get(CONF_IGNORE_BETA, DEFAULT_IGNORE_BETA)
                ): bool,
                vol.Required(
                    CONF_PAUSE_ON_BREAKING,
                    default=opts.get(CONF_PAUSE_ON_BREAKING, DEFAULT_PAUSE_ON_BREAKING),
                ): bool,
                vol.Required(
                    CONF_BREAKING_THRESHOLD,
                    default=opts.get(CONF_BREAKING_THRESHOLD, DEFAULT_BREAKING_THRESHOLD),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                vol.Required(
                    CONF_STABILITY_DELAY_DAYS,
                    default=opts.get(CONF_STABILITY_DELAY_DAYS, DEFAULT_STABILITY_DELAY_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                vol.Required(
                    CONF_CHECK_INTERVAL_HOURS,
                    default=opts.get(CONF_CHECK_INTERVAL_HOURS, DEFAULT_CHECK_INTERVAL_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
                vol.Optional(CONF_ALLOWLIST, default=opts.get(CONF_ALLOWLIST, [])): [str],
                vol.Optional(CONF_BLOCKLIST, default=opts.get(CONF_BLOCKLIST, [])): [str],
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
