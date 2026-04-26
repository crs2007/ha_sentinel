"""Provider for Home Assistant add-on updates via Supervisor REST API."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import UpdateCandidate
from .base import UpdateProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SUPERVISOR_BASE = "http://supervisor"


def _is_beta(version: str) -> bool:
    v = version.lower()
    return any(tag in v for tag in ("beta", "rc", "dev", "alpha"))


class AddonProvider(UpdateProvider):
    name = "addon"

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

        try:
            resp = await session.get(f"{SUPERVISOR_BASE}/addons", headers=headers)
            addons = (await resp.json()).get("data", {}).get("addons", [])
        except Exception:  # noqa: BLE001
            return candidates

        for addon in addons:
            current = addon.get("version", "")
            latest = addon.get("version_latest", "")
            if not current or not latest or current == latest:
                continue
            if not addon.get("update_available", False):
                continue
            candidates.append(
                UpdateCandidate(
                    provider=self.name,
                    slug=addon.get("slug", ""),
                    name=addon.get("name", addon.get("slug", "")),
                    current_version=current,
                    new_version=latest,
                    is_beta=_is_beta(latest),
                    backup_supported=True,
                )
            )

        return candidates

    async def install(self, candidate: UpdateCandidate) -> None:
        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self._token}"}
        await session.post(
            f"{SUPERVISOR_BASE}/addons/{candidate.slug}/update",
            headers=headers,
        )
