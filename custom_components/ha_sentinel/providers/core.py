"""Provider for HA Core, OS, and Supervisor updates via Supervisor REST API."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import UpdateCandidate
from .base import UpdateProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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

        for slug, name, path in _ENDPOINTS:
            try:
                resp = await session.get(f"{SUPERVISOR_BASE}{path}", headers=headers)
                data = (await resp.json()).get("data", {})
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
            except Exception:  # noqa: BLE001
                pass

        return candidates

    async def install(self, candidate: UpdateCandidate) -> None:
        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self._token}"}
        path_map = {
            "core": "/core/update",
            "os": "/os/update",
            "supervisor": "/supervisor/update",
        }
        path = path_map.get(candidate.slug)
        if path:
            await session.post(f"{SUPERVISOR_BASE}{path}", headers=headers)
