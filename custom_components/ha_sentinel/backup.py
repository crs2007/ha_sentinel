"""Supervisor partial-backup helper — called before installs when configured."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_BASE = "http://supervisor"
BACKUP_ENDPOINT = f"{SUPERVISOR_BASE}/backups/new/partial"


def _build_payload(candidate: UpdateCandidate) -> dict | None:
    """Return a partial-backup request body, or None if provider is unsupported."""
    name = f"pre-update-{candidate.slug}-{candidate.new_version}"
    if candidate.provider == "core":
        # Covers home-assistant, os, and supervisor slugs — all backed up via
        # the homeassistant snapshot scope in the Supervisor API.
        return {"homeassistant": True, "name": name}
    if candidate.provider == "addon":
        return {"addons": [candidate.slug], "name": name}
    return None  # HACS updates live outside Supervisor's backup scope


async def create_backup(hass: "HomeAssistant", candidate: UpdateCandidate) -> bool:
    """Create a targeted partial backup before installing a candidate.

    Returns True if the backup completed successfully, False otherwise.
    A failed backup is logged as a warning but does NOT abort the install —
    that decision belongs to the caller.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        _LOGGER.debug("Skipping backup for %s — not a supervised install", candidate.slug)
        return False

    payload = _build_payload(candidate)
    if payload is None:
        _LOGGER.debug("Skipping backup for %s — provider %s not supported", candidate.slug, candidate.provider)
        return False

    try:
        session = async_get_clientsession(hass)
        resp = await session.post(
            BACKUP_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        if resp.status == 200:
            _LOGGER.info("Backup created before upgrading %s to %s", candidate.name, candidate.new_version)
            return True
        body = await resp.text()
        _LOGGER.warning("Backup request failed (HTTP %s) for %s: %s", resp.status, candidate.slug, body)
        return False
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Backup request raised for %s: %s", candidate.slug, exc)
        return False
