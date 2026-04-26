"""Provider for HACS integration updates — soft-detects HACS via hass.data."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import UpdateCandidate
from .base import UpdateProvider

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _is_beta(version: str) -> bool:
    v = version.lower()
    return any(tag in v for tag in ("beta", "rc", "dev", "alpha"))


class HacsProvider(UpdateProvider):
    name = "hacs"

    def __init__(self, hass: "HomeAssistant") -> None:
        super().__init__(hass)

    @property
    def available(self) -> bool:
        return self.hass.data.get("hacs") is not None

    def _get_hacs(self):
        return self.hass.data.get("hacs")

    async def fetch_candidates(self) -> list[UpdateCandidate]:
        hacs = self._get_hacs()
        if hacs is None:
            return []

        candidates: list[UpdateCandidate] = []
        try:
            repositories = hacs.repositories.list_all
            for repo in repositories:
                if not getattr(repo, "pending_update", False):
                    continue
                current = getattr(repo.data, "installed_version", "") or ""
                latest = getattr(repo.data, "last_version", "") or ""
                if not current or not latest or current == latest:
                    continue
                candidates.append(
                    UpdateCandidate(
                        provider=self.name,
                        slug=getattr(repo.data, "full_name", repo.data.id),
                        name=getattr(repo.data, "name", ""),
                        current_version=current,
                        new_version=latest,
                        release_notes=None,
                        release_url=f"https://github.com/{getattr(repo.data, 'full_name', '')}",
                        is_beta=_is_beta(latest),
                        backup_supported=False,
                    )
                )
        except Exception:  # noqa: BLE001
            pass

        return candidates

    async def install(self, candidate: UpdateCandidate) -> None:
        hacs = self._get_hacs()
        if hacs is None:
            return
        try:
            repo = hacs.repositories.get_by_full_name(candidate.slug)
            if repo:
                await repo.async_install()
        except Exception:  # noqa: BLE001
            pass
