"""GitHub API client for fetching release publication dates."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp

_LOGGER = logging.getLogger(__name__)

_GITHUB_RELEASE_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/releases/tag/(?P<tag>.+)$"
)
_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, session: "aiohttp.ClientSession") -> None:
        self._session = session

    async def get_release_date(self, release_url: str) -> datetime | None:
        """Return published_at for a GitHub release URL, or None on any failure."""
        m = _GITHUB_RELEASE_RE.match(release_url or "")
        if not m:
            return None
        owner, repo, tag = m.group("owner"), m.group("repo"), m.group("tag")
        api_url = f"{_API_BASE}/repos/{owner}/{repo}/releases/tags/{tag}"
        try:
            import aiohttp as _aiohttp
            async with self._session.get(
                api_url,
                headers={"Accept": "application/vnd.github+json"},
                timeout=_aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                raw = data.get("published_at")
                if not raw:
                    return None
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            _LOGGER.debug("GitHub API call failed for %s", api_url)
            return None
