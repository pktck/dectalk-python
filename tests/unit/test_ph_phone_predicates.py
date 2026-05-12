"""Verify phone-range predicates match ph_defs.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import (
    COMMA,
    EXCLAIM,
    HYPHEN,
    MBOUND,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    S1,
    SBOUND,
    SPECIALWORD,
    VPSTART,
    WBOUND,
)
from dectalk.ph.phone_predicates import isbound, isdelim, ispause, issmark

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_predicate_defines_present() -> None:
    """All four range-check macros exist in ph_defs.h."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    for name in ("isbound", "ispause", "issmark", "isdelim"):
        assert re.search(rf"#define\s+{name}\(ph\)", text), name


def test_isbound_inclusive_endpoints() -> None:
    """``isbound`` covers WBOUND..VPSTART (inclusive)."""
    assert isbound(WBOUND)
    assert isbound(PPSTART)
    assert isbound(VPSTART)
    assert not isbound(WBOUND - 1)
    assert not isbound(VPSTART + 1)


def test_ispause_inclusive_endpoints() -> None:
    """``ispause`` covers VPSTART..EXCLAIM (inclusive)."""
    assert ispause(VPSTART)
    assert ispause(RELSTART)
    assert ispause(COMMA)
    assert ispause(PERIOD)
    assert ispause(QUEST)
    assert ispause(EXCLAIM)
    assert not ispause(VPSTART - 1)
    assert not ispause(EXCLAIM + 1)


def test_issmark_inclusive_endpoints() -> None:
    """``issmark`` covers WBOUND..EXCLAIM (inclusive)."""
    assert issmark(WBOUND)
    assert issmark(PPSTART)
    assert issmark(COMMA)
    assert issmark(EXCLAIM)
    assert not issmark(WBOUND - 1)
    assert not issmark(EXCLAIM + 1)


def test_isdelim_inclusive_endpoints() -> None:
    """``isdelim`` covers COMMA..EXCLAIM (inclusive)."""
    assert isdelim(COMMA)
    assert isdelim(PERIOD)
    assert isdelim(QUEST)
    assert isdelim(EXCLAIM)
    assert not isdelim(COMMA - 1)
    assert not isdelim(EXCLAIM + 1)


def test_non_boundary_phones_rejected() -> None:
    """Non-boundary control phones return False for all four predicates."""
    for ph in (S1, SBOUND, MBOUND, HYPHEN):
        for pred in (isbound, ispause, issmark, isdelim):
            assert not pred(ph) or (pred is isbound and ph == WBOUND)


def test_specialword_outside_range() -> None:
    """``SPECIALWORD`` and ``NEW_PARAGRAPH`` sit outside all four ranges."""
    assert not isbound(SPECIALWORD)
    assert not ispause(SPECIALWORD)
    assert not issmark(SPECIALWORD)
    assert not isdelim(SPECIALWORD)
    assert not isbound(NEW_PARAGRAPH)
    assert not ispause(NEW_PARAGRAPH)


def test_overlap_at_endpoints() -> None:
    """``VPSTART`` is the meeting point of ``isbound`` and ``ispause``."""
    assert isbound(VPSTART)
    assert ispause(VPSTART)
    # WBOUND is the start of issmark / isbound but not ispause.
    assert issmark(WBOUND)
    assert isbound(WBOUND)
    assert not ispause(WBOUND)
    assert not isdelim(WBOUND)
