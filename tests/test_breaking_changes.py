"""Tests for breaking-change confidence scorer."""
from __future__ import annotations

import pytest

from custom_components.ha_sentinel.breaking_changes import score, _version_jump_weight
from custom_components.ha_sentinel.models import UpdateCandidate


def _cand(notes: str = "", old: str = "1.0.0", new: str = "1.0.1") -> UpdateCandidate:
    return UpdateCandidate(
        provider="addon", slug="x", name="X",
        current_version=old, new_version=new,
        release_notes=notes,
    )


def test_no_notes_no_score():
    assert score(_cand(notes="")) == 0.0


def test_none_notes_no_score():
    c = UpdateCandidate(provider="addon", slug="x", name="X", current_version="1.0.0", new_version="1.0.1")
    assert score(c) == 0.0


def test_breaking_change_keyword():
    s = score(_cand(notes="This release contains a breaking change in the API."))
    assert s >= 0.6


def test_multiple_keywords_additive():
    s = score(_cand(notes="breaking change: migration required, some things removed"))
    assert s > 0.6


def test_score_clamped_to_1():
    notes = "breaking change migration required incompatible removed deprecated you must no longer"
    assert score(_cand(notes=notes)) == 1.0


def test_major_version_jump():
    w = _version_jump_weight("1.9.0", "2.0.0")
    assert w == 0.4


def test_minor_version_jump():
    w = _version_jump_weight("1.0.0", "1.1.0")
    assert w == 0.1


def test_patch_no_jump():
    w = _version_jump_weight("1.0.0", "1.0.1")
    assert w == 0.0


def test_calver_year_jump():
    w = _version_jump_weight("2025.4.0", "2026.4.0")
    assert w == 0.3


def test_calver_same_year_no_jump():
    w = _version_jump_weight("2026.3.0", "2026.4.0")
    assert w == 0.0


def test_bad_version_strings_dont_raise():
    w = _version_jump_weight("unknown", "also-unknown")
    assert w == 0.0
