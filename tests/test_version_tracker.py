"""Tests for VersionTracker — timer-reset is the headline behavior."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_sentinel.models import UpdateCandidate
from custom_components.ha_sentinel.version_tracker import VersionTracker


def _make_candidate(slug: str = "core_ssh", new_version: str = "10.2.0", current: str = "10.1.0") -> UpdateCandidate:
    return UpdateCandidate(
        provider="addon",
        slug=slug,
        name="SSH",
        current_version=current,
        new_version=new_version,
    )


def _make_tracker(hass=None) -> VersionTracker:
    if hass is None:
        hass = MagicMock()
    tracker = VersionTracker(hass)
    tracker._tracked = {}
    return tracker


# ── basic timer-reset behaviour ───────────────────────────────────────────────

def test_new_candidate_recorded():
    tracker = _make_tracker()
    c = _make_candidate(new_version="10.2.0")
    tracker.update(c)
    assert tracker.get_record(c) is not None
    assert tracker.get_record(c)["version"] == "10.2.0"


def test_same_version_keeps_first_seen():
    tracker = _make_tracker()
    c = _make_candidate(new_version="10.2.0")
    tracker.update(c)
    first_seen = tracker.get_record(c)["first_seen"]

    # second update with same version — first_seen must not change
    tracker.update(c)
    assert tracker.get_record(c)["first_seen"] == first_seen


def test_higher_version_resets_timer():
    tracker = _make_tracker()
    c1 = _make_candidate(new_version="10.2.0")
    tracker.update(c1)
    old_first_seen = tracker.get_record(c1)["first_seen"]

    # small sleep to ensure timestamps differ
    import time; time.sleep(0.01)

    c2 = _make_candidate(new_version="10.3.0")
    tracker.update(c2)

    record = tracker.get_record(c2)
    assert record["version"] == "10.3.0"
    assert record["first_seen"] != old_first_seen


def test_rollback_deletes_record():
    tracker = _make_tracker()
    c_high = _make_candidate(new_version="10.3.0")
    tracker.update(c_high)

    # rolled back to lower version
    c_low = _make_candidate(new_version="10.1.0")
    tracker.update(c_low)

    assert tracker.get_record(c_low) is None


def test_missing_record_is_not_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    assert tracker.is_stable(c, delay_days=7) is False


def test_fresh_record_is_not_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    tracker.update(c)
    assert tracker.is_stable(c, delay_days=7) is False


def test_old_record_is_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    tracker.update(c)
    # backdate first_seen by 8 days
    key = f"{c.provider}:{c.slug}"
    old_ts = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    tracker._tracked[key]["first_seen"] = old_ts

    assert tracker.is_stable(c, delay_days=7) is True


def test_delay_remaining_decreases_over_time():
    tracker = _make_tracker()
    c = _make_candidate()
    tracker.update(c)
    # backdate by 3 days
    key = f"{c.provider}:{c.slug}"
    ts = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    tracker._tracked[key]["first_seen"] = ts

    remaining = tracker.delay_remaining_seconds(c, delay_days=7)
    expected = 4 * 86400  # 4 days left
    assert abs(remaining - expected) < 5  # within 5 seconds tolerance


def test_zero_delay_immediately_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    tracker.update(c)
    assert tracker.is_stable(c, delay_days=0) is True


def test_multiple_slugs_independent():
    tracker = _make_tracker()
    c1 = _make_candidate(slug="core_ssh", new_version="10.2.0")
    c2 = _make_candidate(slug="mosquitto", new_version="6.5.0")
    tracker.update(c1)
    tracker.update(c2)

    key1 = f"{c1.provider}:{c1.slug}"
    tracker._tracked[key1]["first_seen"] = (datetime.now(UTC) - timedelta(days=10)).isoformat()

    assert tracker.is_stable(c1, delay_days=7) is True
    assert tracker.is_stable(c2, delay_days=7) is False
