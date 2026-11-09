"""Provider for Home Assistant add-on updates via Supervisor REST API."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..models import UpdateCandidate
from .base import UpdateProvider, supervisor_post

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
            notes = await self._fetch_changelog(session, headers, addon.get("slug", ""))
            candidates.append(
                UpdateCandidate(
                    provider=self.name,
                    slug=addon.get("slug", ""),
                    name=addon.get("name", addon.get("slug", "")),
                    current_version=current,
                    new_version=latest,
                    release_notes=notes,
                    is_beta=_is_beta(latest),
                    backup_supported=True,
                )
            )

        return candidates

    async def _fetch_changelog(self, session, headers, slug: str) -> str | None:
        """Best-effort add-on changelog for breaking-change keyword scoring."""
        try:
            async with session.get(
                f"{SUPERVISOR_BASE}/addons/{slug}/changelog",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return None
                # Only the newest entries matter; changelogs list newest first.
                return (await resp.text())[:4000]
        except Exception:  # noqa: BLE001
            return None

    async def install(self, candidate: UpdateCandidate) -> None:
        session = async_get_clientsession(self.hass)
        await supervisor_post(
            session, f"{SUPERVISOR_BASE}/addons/{candidate.slug}/update", self._token
        )
