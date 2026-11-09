"""Aggregated persistent_notification builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.persistent_notification import async_create, async_dismiss

from homeassistant.core import callback

from .const import NOTIFICATION_ID
from .models import Decision, UpdateCandidate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LAST_KEY = "ha_sentinel_last_notification"


def _days_remaining(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    days = seconds // 86400
    return f"{days}d"


def build_summary(
    results: list[tuple[UpdateCandidate, Decision, bool | None]],
    errors: dict[str, str] | None = None,
    breaking_threshold: float = 0.5,
) -> str:
    installed, failed, delayed, skipped, notify_only = [], [], [], [], []

    for candidate, decision, success in results:
        label = f"{candidate.name} {candidate.current_version}→{candidate.new_version}"
        if decision.action == "INSTALL" and success:
            installed.append(label)
        elif decision.action == "INSTALL" and success is False:
            failed.append(label)
        elif decision.action == "INSTALL":
            notify_only.append(label)  # eligible, but no install attempted this cycle
        elif decision.action == "DELAY":
            delayed.append(f"{candidate.name} ({_days_remaining(decision.delay_remaining_seconds)} remaining)")
        elif decision.action == "SKIP":
            extra = f" (breaking score {decision.breaking_score:.2f})" if decision.breaking_score >= breaking_threshold else ""
            skipped.append(f"{label}{extra}")
        elif decision.action == "NOTIFY_ONLY":
            notify_only.append(label)

    lines = []
    if installed:
        lines.append(f"✔ Installed ({len(installed)}): {', '.join(installed)}")
    if failed:
        lines.append(f"✘ Failed ({len(failed)}): {', '.join(failed)}")
    if notify_only:
        lines.append(f"ℹ Available ({len(notify_only)}): {', '.join(notify_only)}")
    if delayed:
        lines.append(f"⏳ Delayed ({len(delayed)}): {', '.join(delayed)}")
    if skipped:
        lines.append(f"⚠ Skipped ({len(skipped)}): {', '.join(skipped)}")

    if errors:
        lines.append(
            "⚠ Provider errors: " + ", ".join(f"{k} ({v})" for k, v in errors.items())
        )

    return "\n".join(lines)


async def notify_summary(
    hass: "HomeAssistant",
    results: list[tuple[UpdateCandidate, Decision, bool | None]],
    errors: dict[str, str] | None = None,
    breaking_threshold: float = 0.5,
) -> None:
    message = build_summary(results, errors, breaking_threshold) if (results or errors) else ""

    if not message:
        # Nothing to report: clear any stale notification.
        if hass.data.pop(_LAST_KEY, None) is not None:
            async_dismiss(hass, NOTIFICATION_ID)
        return

    if hass.data.get(_LAST_KEY) == message:
        return  # unchanged; don't re-surface it
    hass.data[_LAST_KEY] = message

    async_create(
        hass,
        message=message,
        title="HA Sentinel",
        notification_id=NOTIFICATION_ID,
    )


@callback
def dismiss(hass: "HomeAssistant") -> None:
    hass.data.pop(_LAST_KEY, None)
    async_dismiss(hass, NOTIFICATION_ID)
