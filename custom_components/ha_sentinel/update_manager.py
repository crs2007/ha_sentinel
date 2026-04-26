"""Orchestrates fetch → track → decide → install → notify pipeline."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from . import backup, notifier, policy_engine
from .models import Decision, SentinelConfig, UpdateCandidate
from .providers.addon import AddonProvider
from .providers.core import CoreProvider
from .providers.hacs import HacsProvider
from .version_tracker import VersionTracker

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class UpdateManager:
    def __init__(self, hass: "HomeAssistant", config: SentinelConfig) -> None:
        self.hass = hass
        self.config = config
        self.tracker = VersionTracker(hass)
        self._providers = [
            CoreProvider(hass),
            AddonProvider(hass),
            HacsProvider(hass),
        ]

    async def async_init(self) -> None:
        await self.tracker.async_load()

    async def run_cycle(self, install: bool = True) -> list[tuple[UpdateCandidate, Decision, bool | None]]:
        available = [p for p in self._providers if p.available]

        fetch_results = await asyncio.gather(
            *[p.fetch_candidates() for p in available],
            return_exceptions=True,
        )

        all_candidates: list[tuple[UpdateCandidate, "UpdateProvider"]] = []
        for provider, result in zip(available, fetch_results):
            if isinstance(result, Exception):
                _LOGGER.warning("Provider %s fetch failed: %s", provider.name, result)
                continue
            for candidate in result:
                self.tracker.update(candidate)
                all_candidates.append((candidate, provider))

        await self.tracker.async_save()

        results: list[tuple[UpdateCandidate, Decision, bool | None]] = []
        for candidate, provider in all_candidates:
            decision = policy_engine.decide(candidate, self.config, self.tracker)
            success: bool | None = None

            if install and decision.action == "INSTALL":
                if self.config.backup_before_upgrade and candidate.backup_supported:
                    await backup.create_backup(self.hass, candidate)
                try:
                    await provider.install(candidate)
                    success = True
                    _LOGGER.info("Installed %s %s", candidate.name, candidate.new_version)
                except Exception as exc:  # noqa: BLE001
                    success = False
                    _LOGGER.error("Failed to install %s: %s", candidate.name, exc)

            results.append((candidate, decision, success))

        await notifier.notify_summary(self.hass, results)
        return results

    async def check_now(self) -> list[tuple[UpdateCandidate, Decision, bool | None]]:
        """Fetch and decide without installing."""
        return await self.run_cycle(install=False)

    async def install_slug(self, slug: str) -> bool:
        """Force-install a specific slug, bypassing dry_run."""
        available = [p for p in self._providers if p.available]
        fetch_results = await asyncio.gather(*[p.fetch_candidates() for p in available], return_exceptions=True)

        for provider, result in zip(available, fetch_results):
            if isinstance(result, Exception):
                continue
            for candidate in result:
                if candidate.slug == slug:
                    try:
                        await provider.install(candidate)
                        return True
                    except Exception as exc:  # noqa: BLE001
                        _LOGGER.error("install_slug %s failed: %s", slug, exc)
                        return False
        return False
