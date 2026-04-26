"""Storage-backed version stability tracker."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _parse_version(v: str):
    try:
        from packaging.version import Version
        return Version(v)
    except Exception:
        return v


def _version_gt(a: str, b: str) -> bool:
    va, vb = _parse_version(a), _parse_version(b)
    try:
        return va > vb
    except TypeError:
        return str(va) > str(vb)


def _version_lt(a: str, b: str) -> bool:
    va, vb = _parse_version(a), _parse_version(b)
    try:
        return va < vb
    except TypeError:
        return str(va) < str(vb)


class VersionTracker:
    def __init__(self, hass: "HomeAssistant") -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._tracked: dict[str, dict] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data and "tracked" in data:
            self._tracked = data["tracked"]
        else:
            self._tracked = {}

    async def async_save(self) -> None:
        await self._store.async_save({"tracked": self._tracked})

    def _key(self, candidate: UpdateCandidate) -> str:
        return f"{candidate.provider}:{candidate.slug}"

    def update(self, candidate: UpdateCandidate) -> None:
        """Update tracking record for a candidate. Resets timer on version bump."""
        key = self._key(candidate)
        record = self._tracked.get(key)
        now = datetime.now(UTC).isoformat()

        if record is None or _version_gt(candidate.new_version, record["version"]):
            self._tracked[key] = {"version": candidate.new_version, "first_seen": now}
        elif _version_lt(candidate.new_version, record["version"]):
            self._tracked.pop(key, None)
        # else: same version → keep first_seen unchanged

    def is_stable(self, candidate: UpdateCandidate, delay_days: int) -> bool:
        key = self._key(candidate)
        record = self._tracked.get(key)
        if record is None:
            return False
        first_seen = datetime.fromisoformat(record["first_seen"])
        return (datetime.now(UTC) - first_seen) >= timedelta(days=delay_days)

    def delay_remaining_seconds(self, candidate: UpdateCandidate, delay_days: int) -> int:
        key = self._key(candidate)
        record = self._tracked.get(key)
        if record is None:
            return delay_days * 86400
        first_seen = datetime.fromisoformat(record["first_seen"])
        elapsed = datetime.now(UTC) - first_seen
        remaining = timedelta(days=delay_days) - elapsed
        return max(0, int(remaining.total_seconds()))

    def get_record(self, candidate: UpdateCandidate) -> dict | None:
        return self._tracked.get(self._key(candidate))
