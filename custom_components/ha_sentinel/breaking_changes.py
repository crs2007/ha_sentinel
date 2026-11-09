"""Breaking-change confidence scorer."""
from __future__ import annotations

from .const import BREAKING_KEYWORDS
from .models import UpdateCandidate


def _version_jump_weight(old: str, new: str) -> float:
    try:
        from packaging.version import Version
        v_old = Version(old)
        v_new = Version(new)
        # CalVer (HA Core): year or month changes ship the monthly release with
        # its "backward-incompatible changes" section; patch bumps are low risk.
        if v_old.major >= 2000:
            if v_new.major > v_old.major:
                return 0.5
            return 0.5 if v_new.minor > v_old.minor else 0.0
        # Regular semver: a major bump reaches the default threshold on its own.
        if v_new.major > v_old.major:
            return 0.5
        if v_new.minor > v_old.minor:
            return 0.1
        return 0.0
    except Exception:
        pass
    return 0.0


def score(candidate: UpdateCandidate) -> float:
    notes = (candidate.release_notes or "").lower()
    total = sum(w for kw, w in BREAKING_KEYWORDS.items() if kw in notes)
    total += _version_jump_weight(candidate.current_version, candidate.new_version)
    return min(total, 1.0)
