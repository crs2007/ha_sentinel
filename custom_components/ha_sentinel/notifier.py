"""Aggregated persistent_notification builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.persistent_notification import async_create

from .const import NOTIFICATION_ID
from .models import Decision, UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _days_remaining(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    days = seconds // 86400
    return f"{days}d"


def build_summary(results: list[tuple[UpdateCandidate, Decision, bool | None]]) -> str:
    installed, delayed, skipped, notify_only = [], [], [], []

    for candidate, decision, success in results:
        label = f"{candidate.name} {candidate.current_version}→{candidate.new_version}"
        if decision.action == "INSTALL" and success:
            installed.append(label)
        elif decision.action == "DELAY":
            delayed.append(f"{candidate.name} ({_days_remaining(decision.delay_remaining_seconds)} remaining)")
        elif decision.action == "SKIP":
            extra = f" (breaking score {decision.breaking_score:.2f})" if decision.breaking_score >= 0.5 else ""
            skipped.append(f"{label}{extra}")
        elif decision.action == "NOTIFY_ONLY":
            notify_only.append(label)

    lines = []
    if installed:
        lines.append(f"✔ Installed ({len(installed)}): {', '.join(installed)}")
    if notify_only:
        lines.append(f"ℹ Available ({len(notify_only)}): {', '.join(notify_only)}")
    if delayed:
        lines.append(f"⏳ Delayed ({len(delayed)}): {', '.join(delayed)}")
    if skipped:
        lines.append(f"⚠ Skipped ({len(skipped)}): {', '.join(skipped)}")

    return "\n".join(lines)


async def notify_summary(
    hass: "HomeAssistant",
    results: list[tuple[UpdateCandidate, Decision, bool | None]],
) -> None:
    if not results:
        return

    message = build_summary(results)
    if not message:
        return

    async_create(
        hass,
        message=message,
        title="HA Sentinel",
        notification_id=NOTIFICATION_ID,
    )
