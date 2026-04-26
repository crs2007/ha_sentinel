"""Shared data models for HA Sentinel."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class UpdateCandidate:
    provider: str
    slug: str
    name: str
    current_version: str
    new_version: str
    release_notes: str | None = None
    release_url: str | None = None
    is_beta: bool = False
    backup_supported: bool = False


@dataclass(frozen=True)
class Decision:
    action: Literal["INSTALL", "SKIP", "DELAY", "NOTIFY_ONLY"]
    reason: str
    breaking_score: float = 0.0
    delay_remaining_seconds: int | None = None


@dataclass
class SentinelConfig:
    dry_run: bool = True
    enabled_providers: list[str] = field(default_factory=lambda: ["core", "addon", "hacs"])
    ignore_beta: bool = True
    pause_on_breaking: bool = True
    breaking_threshold: float = 0.5
    stability_delay_days: int = 7
    check_interval_hours: int = 6
    allowlist: list[str] = field(default_factory=list)
    blocklist: list[str] = field(default_factory=list)
    backup_before_upgrade: bool = True

    @classmethod
    def from_options(cls, options: dict) -> "SentinelConfig":
        return cls(
            dry_run=options.get("dry_run", True),
            enabled_providers=options.get("enabled_providers", ["core", "addon", "hacs"]),
            ignore_beta=options.get("ignore_beta", True),
            pause_on_breaking=options.get("pause_on_breaking", True),
            breaking_threshold=options.get("breaking_threshold", 0.5),
            stability_delay_days=options.get("stability_delay_days", 7),
            check_interval_hours=options.get("check_interval_hours", 6),
            allowlist=options.get("allowlist", []),
            blocklist=options.get("blocklist", []),
            backup_before_upgrade=options.get("backup_before_upgrade", True),
        )
