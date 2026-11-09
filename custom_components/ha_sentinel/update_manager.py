"""Orchestrates fetch → track → decide → install → notify pipeline."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import backup, notifier, policy_engine
from .github_client import GitHubClient
from .models import Decision, SentinelConfig, UpdateCandidate
from .providers.addon import AddonProvider
from .providers.core import CoreProvider
from .providers.hacs import HacsProvider
from .version_tracker import VersionTracker

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def is_restart_causing(candidate: UpdateCandidate) -> bool:
    return candidate.provider == "core" and candidate.slug in ("core", "os")


def install_order(candidate: UpdateCandidate) -> int:
    """supervisor first, then add-ons, HACS, and finally core, then OS."""
    if candidate.provider == "core":
        return {"supervisor": 0, "core": 3, "os": 4}.get(candidate.slug, 0)
    return {"addon": 1, "hacs": 2}.get(candidate.provider, 2)


class UpdateManager:
    def __init__(self, hass: "HomeAssistant", config: SentinelConfig) -> None:
        self.hass = hass
        self.config = config
        self.tracker = VersionTracker(hass, GitHubClient(async_get_clientsession(hass)))
        self._lock = asyncio.Lock()
        self._providers = [
            CoreProvider(hass),
            AddonProvider(hass),
            HacsProvider(hass),
        ]

    async def async_init(self) -> None:
        await self.tracker.async_load()

    async def run_cycle(self, install: bool = True) -> list[tuple[UpdateCandidate, Decision, bool | None]]:
        """Run one cycle; cycles are serialised so concurrent callers wait."""
        async with self._lock:
            return await self._run_cycle_locked(install)

    async def _run_cycle_locked(self, install: bool) -> list[tuple[UpdateCandidate, Decision, bool | None]]:
        available = [p for p in self._providers if p.available]

        fetch_results = await asyncio.gather(
            *[p.fetch_candidates() for p in available],
            return_exceptions=True,
        )

        all_candidates: list[tuple[UpdateCandidate, "UpdateProvider"]] = []
        errors: dict[str, str] = {}
        for provider, result in zip(available, fetch_results):
            if isinstance(result, Exception):
                _LOGGER.warning("Provider %s fetch failed: %s", provider.name, result)
                errors[provider.name] = str(result) or type(result).__name__
                continue
            for candidate in result:
                await self.tracker.update(candidate)
                all_candidates.append((candidate, provider))

        self.tracker.prune(
            {p.name for p, r in zip(available, fetch_results) if not isinstance(r, Exception)},
            {(c.provider, c.slug) for c, _ in all_candidates},
        )
        await self.tracker.async_save()

        decided = [
            (c, p, policy_engine.decide(c, self.config, self.tracker))
            for c, p in all_candidates
        ]
        outcomes: dict[int, bool | None] = {}

        if install:
            to_install = sorted(
                (i for i, (_, _, d) in enumerate(decided) if d.action == "INSTALL"),
                key=lambda i: install_order(decided[i][0]),
            )
            # Restart-causing installs (core/os) must be last and at most one per
            # cycle: they kill this process, abandoning anything queued after them.
            restart_idx = [i for i in to_install if is_restart_causing(decided[i][0])]
            normal_idx = [i for i in to_install if i not in restart_idx]
            for i in normal_idx:
                outcomes[i] = await self._install_one(*decided[i][:2])

            if restart_idx:
                i = restart_idx[0]
                # Write the summary first: the install below may restart HA.
                await notifier.notify_summary(
                    self.hass, self._build_results(decided, outcomes), errors
                )
                outcomes[i] = await self._install_one(*decided[i][:2])
                for skipped in restart_idx[1:]:
                    _LOGGER.info(
                        "Deferring %s to next cycle: one restart-causing install per cycle",
                        decided[skipped][0].slug,
                    )

        results = self._build_results(decided, outcomes)
        await notifier.notify_summary(self.hass, results, errors)
        return results

    @staticmethod
    def _build_results(decided, outcomes):
        return [(c, d, outcomes.get(i)) for i, (c, _, d) in enumerate(decided)]

    async def _install_one(self, candidate: UpdateCandidate, provider) -> bool:
        if self.config.backup_before_upgrade and candidate.backup_supported:
            if not await backup.create_backup(self.hass, candidate):
                _LOGGER.error(
                    "Skipping install of %s/%s: backup failed", candidate.provider, candidate.slug
                )
                return False
        try:
            await provider.install(candidate)
            _LOGGER.info("Installed %s %s", candidate.name, candidate.new_version)
            return True
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error(
                "Failed to install %s/%s v%s -> v%s: %s",
                candidate.provider,
                candidate.slug,
                candidate.current_version,
                candidate.new_version,
                exc,
            )
            return False

    async def check_now(self) -> list[tuple[UpdateCandidate, Decision, bool | None]]:
        """Fetch and decide without installing."""
        return await self.run_cycle(install=False)

    async def install_slug(self, slug: str, provider_name: str | None = None) -> None:
        """Install a specific slug, bypassing dry-run and the stability delay only.

        Blocklist and pre-update backup are still enforced. Raises
        ServiceValidationError when the slug is unknown, blocked, or fails.
        """
        from homeassistant.exceptions import ServiceValidationError

        if slug in self.config.blocklist:
            raise ServiceValidationError(f"{slug} is on the blocklist")
        async with self._lock:
            await self._install_slug_locked(slug, provider_name)

    async def _install_slug_locked(self, slug: str, provider_name: str | None) -> None:
        from homeassistant.exceptions import ServiceValidationError

        available = [
            p for p in self._providers
            if p.available and (provider_name is None or p.name == provider_name)
        ]
        fetch_results = await asyncio.gather(
            *[p.fetch_candidates() for p in available], return_exceptions=True
        )
        for provider, result in zip(available, fetch_results):
            if isinstance(result, Exception):
                continue
            for candidate in result:
                if candidate.slug == slug:
                    if not await self._install_one(candidate, provider):
                        raise ServiceValidationError(f"Install of {slug} failed; see log")
                    return
        raise ServiceValidationError(f"No pending update found for {slug}")
