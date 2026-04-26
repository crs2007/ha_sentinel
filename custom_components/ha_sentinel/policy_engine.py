"""Pure decision function for update policy."""
from __future__ import annotations

from . import breaking_changes
from .models import Decision, SentinelConfig, UpdateCandidate
from .version_tracker import VersionTracker


def decide(
    candidate: UpdateCandidate,
    config: SentinelConfig,
    tracker: VersionTracker,
) -> Decision:
    if candidate.is_beta and config.ignore_beta:
        return Decision("SKIP", "Beta release filtered")

    if not tracker.is_stable(candidate, config.stability_delay_days):
        remaining = tracker.delay_remaining_seconds(candidate, config.stability_delay_days)
        return Decision("DELAY", "Stability window not met", delay_remaining_seconds=remaining)

    bscore = breaking_changes.score(candidate)

    if config.pause_on_breaking and bscore >= config.breaking_threshold:
        return Decision(
            "SKIP",
            f"Breaking change suspected (score={bscore:.2f})",
            breaking_score=bscore,
        )

    if config.dry_run or candidate.provider not in config.enabled_providers:
        return Decision("NOTIFY_ONLY", "Dry-run mode", breaking_score=bscore)

    if candidate.slug in config.blocklist:
        return Decision("SKIP", "On blocklist", breaking_score=bscore)

    if config.allowlist and candidate.slug not in config.allowlist:
        return Decision("SKIP", "Not on allowlist", breaking_score=bscore)

    return Decision("INSTALL", "All checks passed", breaking_score=bscore)
