"""Full decision matrix for policy_engine.decide()."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.ha_sentinel.models import SentinelConfig, UpdateCandidate
from custom_components.ha_sentinel.policy_engine import decide
from custom_components.ha_sentinel.version_tracker import VersionTracker


def _candidate(
    slug: str = "core_ssh",
    provider: str = "addon",
    is_beta: bool = False,
    notes: str = "",
    old: str = "10.1.0",
    new: str = "10.2.0",
) -> UpdateCandidate:
    return UpdateCandidate(
        provider=provider, slug=slug, name="X",
        current_version=old, new_version=new,
        release_notes=notes, is_beta=is_beta,
    )


def _stable_tracker(candidate: UpdateCandidate) -> VersionTracker:
    tracker = VersionTracker(MagicMock())
    tracker._tracked = {}
    tracker.update(candidate)
    key = f"{candidate.provider}:{candidate.slug}"
    tracker._tracked[key]["first_seen"] = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    return tracker


def _fresh_tracker(candidate: UpdateCandidate) -> VersionTracker:
    tracker = VersionTracker(MagicMock())
    tracker._tracked = {}
    tracker.update(candidate)
    return tracker


def _config(**kwargs) -> SentinelConfig:
    defaults = dict(
        dry_run=False,
        enabled_providers=["addon", "core", "hacs"],
        ignore_beta=True,
        pause_on_breaking=True,
        breaking_threshold=0.5,
        stability_delay_days=7,
        check_interval_hours=6,
        allowlist=[],
        blocklist=[],
    )
    defaults.update(kwargs)
    return SentinelConfig(**defaults)


# ── beta filtering ────────────────────────────────────────────────────────────

def test_beta_skipped_when_ignore_beta():
    c = _candidate(is_beta=True)
    d = decide(c, _config(ignore_beta=True), _stable_tracker(c))
    assert d.action == "SKIP"
    assert "beta" in d.reason.lower()


def test_beta_allowed_when_ignore_beta_false():
    c = _candidate(is_beta=True)
    d = decide(c, _config(ignore_beta=False), _stable_tracker(c))
    assert d.action == "INSTALL"


# ── stability delay ───────────────────────────────────────────────────────────

def test_fresh_candidate_delayed():
    c = _candidate()
    d = decide(c, _config(), _fresh_tracker(c))
    assert d.action == "DELAY"
    assert d.delay_remaining_seconds is not None


def test_stable_candidate_proceeds():
    c = _candidate()
    d = decide(c, _config(), _stable_tracker(c))
    assert d.action == "INSTALL"


def test_zero_delay_passes_immediately():
    c = _candidate()
    d = decide(c, _config(stability_delay_days=0), _fresh_tracker(c))
    assert d.action == "INSTALL"


# ── breaking-change gate ──────────────────────────────────────────────────────

def test_breaking_change_skipped():
    c = _candidate(notes="breaking change: migration required")
    d = decide(c, _config(pause_on_breaking=True, breaking_threshold=0.5), _stable_tracker(c))
    assert d.action == "SKIP"
    assert d.breaking_score >= 0.5


def test_breaking_change_not_paused_when_disabled():
    c = _candidate(notes="breaking change: migration required")
    d = decide(c, _config(pause_on_breaking=False), _stable_tracker(c))
    assert d.action == "INSTALL"


# ── dry-run ───────────────────────────────────────────────────────────────────

def test_dry_run_gives_notify_only():
    c = _candidate()
    d = decide(c, _config(dry_run=True), _stable_tracker(c))
    assert d.action == "NOTIFY_ONLY"


def test_provider_not_enabled_gives_notify_only():
    c = _candidate(provider="hacs")
    d = decide(c, _config(dry_run=False, enabled_providers=["core", "addon"]), _stable_tracker(c))
    assert d.action == "NOTIFY_ONLY"


# ── blocklist / allowlist ─────────────────────────────────────────────────────

def test_blocklisted_slug_skipped():
    c = _candidate(slug="core_ssh")
    d = decide(c, _config(blocklist=["core_ssh"]), _stable_tracker(c))
    assert d.action == "SKIP"
    assert "blocklist" in d.reason.lower()


def test_not_on_allowlist_skipped():
    c = _candidate(slug="core_ssh")
    d = decide(c, _config(allowlist=["mosquitto"]), _stable_tracker(c))
    assert d.action == "SKIP"
    assert "allowlist" in d.reason.lower()


def test_on_allowlist_proceeds():
    c = _candidate(slug="core_ssh")
    d = decide(c, _config(allowlist=["core_ssh"]), _stable_tracker(c))
    assert d.action == "INSTALL"


def test_empty_allowlist_allows_all():
    c = _candidate(slug="core_ssh")
    d = decide(c, _config(allowlist=[]), _stable_tracker(c))
    assert d.action == "INSTALL"


# ── happy path ────────────────────────────────────────────────────────────────

def test_all_checks_pass_gives_install():
    c = _candidate()
    d = decide(c, _config(), _stable_tracker(c))
    assert d.action == "INSTALL"
    assert d.reason == "All checks passed"
