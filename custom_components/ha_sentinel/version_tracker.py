"""Storage-backed version stability tracker."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store
from packaging.version import InvalidVersion, Version

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .github_client import GitHubClient


GITHUB_RETRY_INTERVAL = timedelta(hours=24)


def _natural_key(v: str) -> tuple:
    """Numeric-aware ordering for non-PEP440 tags ('v1.10' > 'v1.9')."""
    return tuple(
        (0, int(tok), "") if tok.isdigit() else (1, 0, tok)
        for tok in re.findall(r"\d+|[^\d.\-_+ ]+", v.lstrip("vV"))
    )


def _compare(a: str, b: str) -> int:
    try:
        va, vb = Version(a), Version(b)
        return (va > vb) - (va < vb)
    except InvalidVersion:
        ka, kb = _natural_key(a), _natural_key(b)
        return (ka > kb) - (ka < kb)


def _version_gt(a: str, b: str) -> bool:
    return _compare(a, b) > 0


def _version_lt(a: str, b: str) -> bool:
    return _compare(a, b) < 0


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

    def prune(self, succeeded_providers: set[str], seen: set[tuple[str, str]]) -> None:
        """Drop records no longer offered. Only for providers whose fetch succeeded."""
        for key in list(self._tracked):
            provider, _, slug = key.partition(":")
            if provider in succeeded_providers and (provider, slug) not in seen:
                del self._tracked[key]

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
                "github_checked_at": datetime.now(UTC).isoformat(),
            }
        elif _version_lt(candidate.new_version, record["version"]):
            # Rolled back: restart tracking immediately for the offered version.
            self._tracked.pop(key, None)
            resolved = await self._resolve_date(candidate)
            self._tracked[key] = {
                "version": candidate.new_version,
                "first_seen": resolved["date"],
                "date_source": resolved["source"],
                "github_checked_at": datetime.now(UTC).isoformat(),
            }
        else:
            # Same version: retry GitHub only if we're still using first_seen
            if (
                record.get("date_source") != "github"
                and self._github_client
                and self._github_retry_due(record)
            ):
                record["github_checked_at"] = datetime.now(UTC).isoformat()
                resolved = await self._resolve_date(candidate)
                if resolved["source"] == "github":
                    record["first_seen"] = resolved["date"]
                    record["date_source"] = "github"

    @staticmethod
    def _github_retry_due(record: dict) -> bool:
        """Negative lookups are cached for 24h to protect the GitHub rate limit."""
        checked = record.get("github_checked_at")
        if not checked:
            return True
        return datetime.now(UTC) - datetime.fromisoformat(checked) >= GITHUB_RETRY_INTERVAL

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
