"""Provider for HA Core, OS, and Supervisor updates via Supervisor REST API."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import UpdateCandidate
from .base import UpdateProvider, supervisor_post

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
SUPERVISOR_BASE = "http://supervisor"
_ENDPOINTS = [
    ("core", "home-assistant", "/core/info"),
    ("os", "Home Assistant OS", "/os/info"),
    ("supervisor", "Supervisor", "/supervisor/info"),
]


def _is_beta(version: str) -> bool:
    v = version.lower()
    return any(tag in v for tag in ("beta", "rc", "dev", "alpha"))


class CoreProvider(UpdateProvider):
    name = "core"

    def __init__(self, hass: "HomeAssistant") -> None:
        super().__init__(hass)
        self._token = os.environ.get("SUPERVISOR_TOKEN")

    @property
    def available(self) -> bool:
        return bool(self._token)

    async def fetch_candidates(self) -> list[UpdateCandidate]:
        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self._token}"}
        candidates: list[UpdateCandidate] = []

        failures: list[str] = []

        async def fetch_one(slug: str, name: str, path: str) -> None:
            try:
                async with session.get(
                    f"{SUPERVISOR_BASE}{path}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    data = (await resp.json(content_type=None)).get("data", {})
            except aiohttp.ClientResponseError as exc:
                if exc.status == 404:  # e.g. /os/info on a non-HAOS install
                    _LOGGER.debug("Endpoint %s not available: %s", path, exc)
                else:
                    failures.append(f"{slug}: HTTP {exc.status}")
                return
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{slug}: {exc or type(exc).__name__}")
                return
            current = data.get("version", "")
            latest = data.get("version_latest", "")
            if current and latest and current != latest:
                candidates.append(
                    UpdateCandidate(
                        provider=self.name,
                        slug=slug,
                        name=name,
                        current_version=current,
                        new_version=latest,
                        is_beta=_is_beta(latest),
                        # home-assistant and os updates are backed up via the
                        # Supervisor homeassistant snapshot scope; supervisor
                        # self-updates are low-risk and don't need a snapshot.
                        backup_supported=(slug in ("core", "os")),
                    )
                )

        await asyncio.gather(*(fetch_one(*e) for e in _ENDPOINTS))
        order = {slug: i for i, (slug, _, _) in enumerate(_ENDPOINTS)}
        candidates.sort(key=lambda c: order[c.slug])

        if failures:
            _LOGGER.warning("Core provider endpoint errors: %s", "; ".join(failures))
            if not candidates:
                raise RuntimeError("; ".join(failures))

        return candidates

    async def install(self, candidate: UpdateCandidate) -> None:
        path_map = {
            "core": "/core/update",
            "os": "/os/update",
            "supervisor": "/supervisor/update",
        }
        path = path_map.get(candidate.slug)
        if path is None:
            raise ValueError(f"Unknown core update slug: {candidate.slug!r}")
        session = async_get_clientsession(self.hass)
        await supervisor_post(session, f"{SUPERVISOR_BASE}{path}", self._token)
