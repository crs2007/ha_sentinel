"""Tests for VersionTracker — timer-reset is the headline behavior."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ha_sentinel.models import UpdateCandidate
from custom_components.ha_sentinel.version_tracker import VersionTracker


def _make_candidate(
    slug: str = "core_ssh",
    new_version: str = "10.2.0",
    current: str = "10.1.0",
    release_url: str | None = None,
) -> UpdateCandidate:
    return UpdateCandidate(
        provider="addon",
        slug=slug,
        name="SSH",
        current_version=current,
        new_version=new_version,
        release_url=release_url,
    )


def _make_tracker(github_client=None) -> VersionTracker:
    hass = MagicMock()
    tracker = VersionTracker(hass, github_client)
    tracker._tracked = {}
    return tracker


def _make_github_client(published_at: datetime | None) -> MagicMock:
    client = MagicMock()
    client.get_release_date = AsyncMock(return_value=published_at)
    return client


# ── basic timer-reset behaviour ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_candidate_recorded():
    tracker = _make_tracker()
    c = _make_candidate(new_version="10.2.0")
    await tracker.update(c)
    assert tracker.get_record(c) is not None
    assert tracker.get_record(c)["version"] == "10.2.0"


@pytest.mark.asyncio
async def test_same_version_keeps_first_seen():
    tracker = _make_tracker()
    c = _make_candidate(new_version="10.2.0")
    await tracker.update(c)
    first_seen = tracker.get_record(c)["first_seen"]

    await tracker.update(c)
    assert tracker.get_record(c)["first_seen"] == first_seen


@pytest.mark.asyncio
async def test_higher_version_resets_timer():
    tracker = _make_tracker()
    c1 = _make_candidate(new_version="10.2.0")
    await tracker.update(c1)
    old_first_seen = tracker.get_record(c1)["first_seen"]

    import time; time.sleep(0.01)

    c2 = _make_candidate(new_version="10.3.0")
    await tracker.update(c2)

    record = tracker.get_record(c2)
    assert record["version"] == "10.3.0"
    assert record["first_seen"] != old_first_seen


@pytest.mark.asyncio
async def test_rollback_deletes_record():
    tracker = _make_tracker()
    c_high = _make_candidate(new_version="10.3.0")
    await tracker.update(c_high)

    c_low = _make_candidate(new_version="10.1.0")
    await tracker.update(c_low)

    assert tracker.get_record(c_low) is None


def test_missing_record_is_not_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    assert tracker.is_stable(c, delay_days=7) is False


@pytest.mark.asyncio
async def test_fresh_record_is_not_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    await tracker.update(c)
    assert tracker.is_stable(c, delay_days=7) is False


@pytest.mark.asyncio
async def test_old_record_is_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    await tracker.update(c)
    key = f"{c.provider}:{c.slug}"
    old_ts = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    tracker._tracked[key]["first_seen"] = old_ts

    assert tracker.is_stable(c, delay_days=7) is True


@pytest.mark.asyncio
async def test_delay_remaining_decreases_over_time():
    tracker = _make_tracker()
    c = _make_candidate()
    await tracker.update(c)
    key = f"{c.provider}:{c.slug}"
    ts = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    tracker._tracked[key]["first_seen"] = ts

    remaining = tracker.delay_remaining_seconds(c, delay_days=7)
    expected = 4 * 86400
    assert abs(remaining - expected) < 5


@pytest.mark.asyncio
async def test_zero_delay_immediately_stable():
    tracker = _make_tracker()
    c = _make_candidate()
    await tracker.update(c)
    assert tracker.is_stable(c, delay_days=0) is True


@pytest.mark.asyncio
async def test_multiple_slugs_independent():
    tracker = _make_tracker()
    c1 = _make_candidate(slug="core_ssh", new_version="10.2.0")
    c2 = _make_candidate(slug="mosquitto", new_version="6.5.0")
    await tracker.update(c1)
    await tracker.update(c2)

    key1 = f"{c1.provider}:{c1.slug}"
    tracker._tracked[key1]["first_seen"] = (datetime.now(UTC) - timedelta(days=10)).isoformat()

    assert tracker.is_stable(c1, delay_days=7) is True
    assert tracker.is_stable(c2, delay_days=7) is False


# ── GitHub hybrid date resolution ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_version_uses_github_date():
    published = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    gh = _make_github_client(published)
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url="https://github.com/owner/repo/releases/tag/10.2.0")
    await tracker.update(c)

    record = tracker.get_record(c)
    assert record["date_source"] == "github"
    assert record["first_seen"] == published.isoformat()


@pytest.mark.asyncio
async def test_new_version_falls_back_to_first_seen_when_github_fails():
    gh = _make_github_client(None)
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url="https://github.com/owner/repo/releases/tag/10.2.0")
    before = datetime.now(UTC)
    await tracker.update(c)

    record = tracker.get_record(c)
    assert record["date_source"] == "first_seen"
    first_seen_dt = datetime.fromisoformat(record["first_seen"])
    assert first_seen_dt >= before


@pytest.mark.asyncio
async def test_no_github_client_uses_first_seen():
    tracker = _make_tracker()  # no github_client
    c = _make_candidate()
    before = datetime.now(UTC)
    await tracker.update(c)

    record = tracker.get_record(c)
    assert record["date_source"] == "first_seen"
    first_seen_dt = datetime.fromisoformat(record["first_seen"])
    assert first_seen_dt >= before


@pytest.mark.asyncio
async def test_same_version_retries_github_when_source_is_first_seen():
    # First update: GitHub fails → first_seen
    gh = _make_github_client(None)
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url="https://github.com/owner/repo/releases/tag/10.2.0")
    await tracker.update(c)
    assert tracker.get_record(c)["date_source"] == "first_seen"

    # Second update: GitHub now succeeds
    published = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    gh.get_release_date = AsyncMock(return_value=published)
    await tracker.update(c)

    record = tracker.get_record(c)
    assert record["date_source"] == "github"
    assert record["first_seen"] == published.isoformat()


@pytest.mark.asyncio
async def test_same_version_skips_github_when_already_github():
    published = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    gh = _make_github_client(published)
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url="https://github.com/owner/repo/releases/tag/10.2.0")
    await tracker.update(c)

    call_count_after_first = gh.get_release_date.call_count

    # Second update with same version — should NOT call GitHub again
    await tracker.update(c)
    assert gh.get_release_date.call_count == call_count_after_first


@pytest.mark.asyncio
async def test_old_github_date_makes_record_immediately_stable():
    published = datetime.now(UTC) - timedelta(days=10)
    gh = _make_github_client(published)
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url="https://github.com/owner/repo/releases/tag/10.2.0")
    await tracker.update(c)

    assert tracker.is_stable(c, delay_days=7) is True


@pytest.mark.asyncio
async def test_no_release_url_falls_back_to_first_seen():
    gh = _make_github_client(datetime(2024, 1, 1, tzinfo=timezone.utc))
    tracker = _make_tracker(github_client=gh)
    c = _make_candidate(release_url=None)
    await tracker.update(c)

    record = tracker.get_record(c)
    assert record["date_source"] == "first_seen"
    gh.get_release_date.assert_not_called()
