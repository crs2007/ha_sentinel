"""Abstract provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from ..models import UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class UpdateProvider(ABC):
    name: ClassVar[str]

    def __init__(self, hass: "HomeAssistant") -> None:
        self.hass = hass

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    async def fetch_candidates(self) -> list[UpdateCandidate]: ...

    @abstractmethod
    async def install(self, candidate: UpdateCandidate) -> None: ...


async def supervisor_post(session, url: str, token: str, timeout: float = 600) -> None:
    """POST to the Supervisor API; raise unless it reports result == "ok"."""
    import aiohttp

    async with session.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=aiohttp.ClientTimeout(total=timeout),
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)
    if not isinstance(body, dict) or body.get("result") != "ok":
        raise RuntimeError(f"Supervisor call {url} failed: {body!r}")
