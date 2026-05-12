"""Verify ``toph`` / ``from_ph`` parity with dic_comm.c."""

from __future__ import annotations

import pytest

from dectalk.dic import glyph_lookup as gl
from dectalk.dic.ptab import ptab_us


@pytest.mark.parametrize("glyph", ["e", "a", "i", "p", "t", "k", "@", "^", "&"])
def test_toph_roundtrip(glyph: str) -> None:
    """``toph`` returns the code from ptab_us[glyph]."""
    assert gl.toph(glyph) == ptab_us[glyph]


def test_toph_zero_returns_zero() -> None:
    """The C source guard: ``if (c == 0) return c``."""
    assert gl.toph(0) == 0


def test_toph_int_byte() -> None:
    """Int byte values are accepted."""
    assert gl.toph(ord("e")) == ptab_us["e"]


def test_toph_unknown_raises() -> None:
    """Unknown glyphs raise UnknownGlyphError."""
    with pytest.raises(gl.UnknownGlyphError):
        gl.toph("?")  # not in ptab_us


def test_from_ph_known_codes() -> None:
    """from_ph returns a glyph for every code that has one."""
    for glyph, code in ptab_us.items():
        # from_ph may return any glyph mapping to that code (first match).
        result = gl.from_ph(code)
        assert ptab_us[result] == code, (
            f"from_ph({code}) returned {result!r}, "
            f"but ptab_us[{result!r}]={ptab_us[result]} != {code} (called with {glyph})"
        )


def test_from_ph_first_glyph_wins() -> None:
    """When two glyphs map to the same code, the first ptab_us entry wins."""
    # Find a code with two mappings (if any).
    code_counts: dict[int, list[str]] = {}
    for g, c in ptab_us.items():
        code_counts.setdefault(c, []).append(g)
    dups = {c: gs for c, gs in code_counts.items() if len(gs) > 1}
    for code, glyphs in dups.items():
        assert gl.from_ph(code) == glyphs[0]


def test_from_ph_unknown_returns_dash() -> None:
    """Unknown codes return ``-`` (mirroring C's fall-off behaviour)."""
    # 0xFFFE is well outside any allophone code range.
    assert gl.from_ph(0xFFFE) == "-"


def test_toph_from_ph_roundtrip() -> None:
    """toph(from_ph(code)) == code for every recognised code."""
    seen_codes: set[int] = set()
    for glyph in ptab_us:
        code = gl.toph(glyph)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        # The first glyph for this code roundtrips.
        first_glyph = gl.from_ph(code)
        assert gl.toph(first_glyph) == code
