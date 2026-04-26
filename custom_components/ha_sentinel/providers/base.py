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
