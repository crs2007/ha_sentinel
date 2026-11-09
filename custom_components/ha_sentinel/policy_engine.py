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

    if _matches(candidate, config.blocklist):
        return Decision("SKIP", "On blocklist")

    if config.allowlist and not _matches(candidate, config.allowlist):
        return Decision("SKIP", "Not on allowlist")

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

    if candidate.provider not in config.enabled_providers:
        return Decision("NOTIFY_ONLY", "Provider not enabled", breaking_score=bscore)

    if config.dry_run:
        return Decision("NOTIFY_ONLY", "Would install (dry-run)", breaking_score=bscore)

    return Decision("INSTALL", "All checks passed", breaking_score=bscore)


def _matches(candidate: UpdateCandidate, entries) -> bool:
    """Case-insensitive match on `slug` or the unambiguous `provider:slug` form."""
    slug = candidate.slug.casefold()
    qualified = f"{candidate.provider}:{slug}"
    return any(str(e).casefold() in (slug, qualified) for e in entries)
