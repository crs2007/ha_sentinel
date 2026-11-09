"""Install ordering and restart handling (issue #3)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_sentinel import update_manager as um
from custom_components.ha_sentinel.models import Decision, SentinelConfig, UpdateCandidate


def _c(provider, slug):
    return UpdateCandidate(provider=provider, slug=slug, name=slug, current_version="1", new_version="2")


def test_install_order():
    cs = [_c("core", "os"), _c("hacs", "a/b"), _c("core", "core"), _c("addon", "x"), _c("core", "supervisor")]
    order = [c.slug for c in sorted(cs, key=um.install_order)]
    assert order == ["supervisor", "x", "a/b", "core", "os"]


@pytest.mark.asyncio
async def test_one_restart_install_last_and_others_deferred():
    calls = []

    def _prov(cands):
        p = MagicMock()
        p.available = True
        p.fetch_candidates = AsyncMock(return_value=cands)
        async def inst(c):
            calls.append(c.slug)
        p.install = inst
        return p

    core = _prov([_c("core", "os"), _c("core", "core"), _c("core", "supervisor")])
    addon = _prov([_c("addon", "x")])
    with patch.object(um, "GitHubClient"), patch.object(um, "VersionTracker") as vt, \
         patch.object(um, "async_get_clientsession"), \
         patch.object(um.policy_engine, "decide", return_value=Decision(action="INSTALL", reason="")) , \
         patch.object(um.notifier, "notify_summary", new=AsyncMock()), \
         patch.object(um.backup, "create_backup", new=AsyncMock()):
        vt.return_value.update = AsyncMock()
        vt.return_value.async_save = AsyncMock()
        m = um.UpdateManager(MagicMock(), SentinelConfig(backup_before_upgrade=False))
        m._providers = [core, addon]
        await m.run_cycle(install=True)

    assert calls == ["supervisor", "x", "core"]
