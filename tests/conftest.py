"""Shared pytest fixtures."""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def event_loop(socket_enabled):  # socket_enabled re-enables sockets for event loop internals
    """Event loop fixture that works on Windows with pytest-socket.

    Both ProactorEventLoop and SelectorEventLoop call socket.socketpair() during
    __init__ for their internal self-pipe, which pytest-socket blocks. Depending
    on socket_enabled lifts the block for the duration of this fixture.
    """
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def basic_candidate():
    from custom_components.ha_sentinel.models import UpdateCandidate
    return UpdateCandidate(
        provider="addon",
        slug="core_ssh",
        name="SSH Server",
        current_version="10.1.0",
        new_version="10.2.0",
    )
