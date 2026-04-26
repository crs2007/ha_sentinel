"""ConfigFlow and OptionsFlow for HA Sentinel."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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

_PROVIDER_OPTIONS = [
    {"value": "core", "label": "Home Assistant Core & OS"},
    {"value": "addon", "label": "Add-ons"},
    {"value": "hacs", "label": "HACS Integrations"},
]


class SentinelConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="HA Sentinel", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "SentinelOptionsFlow":
        return SentinelOptionsFlow()


class SentinelOptionsFlow(OptionsFlow):
    """Three-step wizard: Operation → Safety → Schedule & Filters."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_operation()

    # ------------------------------------------------------------------
    # Step 1 — What to Monitor
    # ------------------------------------------------------------------

    async def async_step_operation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        opts = self.config_entry.options

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_safety()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DRY_RUN,
                    default=opts.get(CONF_DRY_RUN, DEFAULT_DRY_RUN),
                ): BooleanSelector(),
                vol.Required(
                    CONF_ENABLED_PROVIDERS,
                    default=opts.get(CONF_ENABLED_PROVIDERS, ALL_PROVIDERS),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_PROVIDER_OPTIONS,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_BACKUP_BEFORE_UPGRADE,
                    default=opts.get(CONF_BACKUP_BEFORE_UPGRADE, DEFAULT_BACKUP_BEFORE_UPGRADE),
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="operation", data_schema=schema)

    # ------------------------------------------------------------------
    # Step 2 — Safety Rules
    # ------------------------------------------------------------------

    async def async_step_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        opts = self.config_entry.options

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_schedule()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_IGNORE_BETA,
                    default=opts.get(CONF_IGNORE_BETA, DEFAULT_IGNORE_BETA),
                ): BooleanSelector(),
                vol.Required(
                    CONF_STABILITY_DELAY_DAYS,
                    default=opts.get(CONF_STABILITY_DELAY_DAYS, DEFAULT_STABILITY_DELAY_DAYS),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=90,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                            unit_of_measurement="days",
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Required(
                    CONF_PAUSE_ON_BREAKING,
                    default=opts.get(CONF_PAUSE_ON_BREAKING, DEFAULT_PAUSE_ON_BREAKING),
                ): BooleanSelector(),
                vol.Required(
                    CONF_BREAKING_THRESHOLD,
                    default=opts.get(CONF_BREAKING_THRESHOLD, DEFAULT_BREAKING_THRESHOLD),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0.0,
                            max=1.0,
                            step=0.05,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Coerce(float),
                ),
            }
        )

        return self.async_show_form(step_id="safety", data_schema=schema)

    # ------------------------------------------------------------------
    # Step 3 — Schedule & Filters (final; writes options entry)
    # ------------------------------------------------------------------

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        opts = self.config_entry.options

        if user_input is not None:
            for key in (CONF_ALLOWLIST, CONF_BLOCKLIST):
                raw = user_input.get(key, "")
                user_input[key] = [s.strip() for s in raw.splitlines() if s.strip()]
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        allowlist_display = "\n".join(opts.get(CONF_ALLOWLIST, []))
        blocklist_display = "\n".join(opts.get(CONF_BLOCKLIST, []))

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHECK_INTERVAL_HOURS,
                    default=opts.get(CONF_CHECK_INTERVAL_HOURS, DEFAULT_CHECK_INTERVAL_HOURS),
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=168,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                            unit_of_measurement="hours",
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Optional(
                    CONF_ALLOWLIST,
                    default=allowlist_display,
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)),
                vol.Optional(
                    CONF_BLOCKLIST,
                    default=blocklist_display,
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)),
            }
        )

        return self.async_show_form(step_id="schedule", data_schema=schema)
