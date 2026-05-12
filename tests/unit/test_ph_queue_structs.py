"""Verify Limit / IndexEvent dataclasses and NIQUEUE / GUARD constants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.queue_structs import GUARD, NIQUEUE, IndexEvent, Limit

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/viphdefs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_niqueue_matches_c() -> None:
    """``NIQUEUE`` (250) matches viphdefs.h."""
    assert _parse_define("NIQUEUE") == 250
    assert NIQUEUE == 250


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_guard_matches_c() -> None:
    """``GUARD`` (25) matches viphdefs.h."""
    assert _parse_define("GUARD") == 25
    assert GUARD == 25


def test_limit_default() -> None:
    """Limit defaults to (0, 0)."""
    lim = Limit()
    assert lim.l_min == 0
    assert lim.l_max == 0


def test_limit_construction() -> None:
    """Limit fields are settable at construction."""
    lim = Limit(l_min=100, l_max=5000)
    assert lim.l_min == 100
    assert lim.l_max == 5000


def test_index_event_default() -> None:
    """IndexEvent defaults to (0, 0, 0)."""
    ev = IndexEvent()
    assert ev.i_offset == 0
    assert ev.i_type == 0
    assert ev.i_value == 0


def test_index_event_construction() -> None:
    """IndexEvent fields are settable."""
    ev = IndexEvent(i_offset=10, i_type=1, i_value=42)
    assert ev.i_offset == 10
    assert ev.i_type == 1
    assert ev.i_value == 42


def test_limit_uses_slots() -> None:
    """Limit uses slots=True (no __dict__)."""
    lim = Limit()
    assert not hasattr(lim, "__dict__")


def test_index_event_uses_slots() -> None:
    """IndexEvent uses slots=True (no __dict__)."""
    ev = IndexEvent()
    assert not hasattr(ev, "__dict__")
