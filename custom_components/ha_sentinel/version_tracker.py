"""Storage-backed version stability tracker."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .github_client import GitHubClient


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
    def __init__(self, hass: "HomeAssistant", github_client: "GitHubClient | None" = None) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._tracked: dict[str, dict] = {}
        self._github_client = github_client

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

    async def update(self, candidate: UpdateCandidate) -> None:
        """Update tracking record. Uses GitHub published_at if available, else first_seen."""
        key = self._key(candidate)
        record = self._tracked.get(key)

        if record is None or _version_gt(candidate.new_version, record["version"]):
            resolved = await self._resolve_date(candidate)
            self._tracked[key] = {
                "version": candidate.new_version,
                "first_seen": resolved["date"],
                "date_source": resolved["source"],
            }
        elif _version_lt(candidate.new_version, record["version"]):
            self._tracked.pop(key, None)
        else:
            # Same version: retry GitHub only if we're still using first_seen
            if record.get("date_source") != "github" and self._github_client:
                resolved = await self._resolve_date(candidate)
                if resolved["source"] == "github":
                    record["first_seen"] = resolved["date"]
                    record["date_source"] = "github"

    async def _resolve_date(self, candidate: UpdateCandidate) -> dict:
        """Return {"date": ISO str, "source": "github" | "first_seen"}."""
        if self._github_client and candidate.release_url:
            dt = await self._github_client.get_release_date(candidate.release_url)
            if dt is not None:
                return {"date": dt.isoformat(), "source": "github"}
        return {"date": datetime.now(UTC).isoformat(), "source": "first_seen"}

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
