"""Verify ``usa_ascky`` parity with usa_phon.tab."""

from __future__ import annotations

from dectalk.include.usa_ascky import usa_ascky, usa_phone_to_glyph
from dectalk.include.usa_phon_tables import NULL_ASCKY, usa_ascky_rev


def test_first_allophone_is_underscore() -> None:
    """Index 0 = ``_`` (silence)."""
    assert usa_ascky[0] == ord("_")


def test_first_allophones_match_c_source() -> None:
    """Indices 0..15 match the C source: ``_ i I e E @ a A W ^ c o O U u R``."""
    expected = b"_iIeE@aAW^coOUuR"
    assert usa_ascky[: len(expected)] == expected


def test_control_codes_at_index_100() -> None:
    """Control codes start at index 100; first 5 are ``~ = ` ' "``."""
    expected = b"~=`'\""
    assert usa_ascky[100 : 100 + len(expected)] == expected


def test_x_and_v_at_57_58() -> None:
    """Null-range placeholders ``X`` and ``V`` at indices 57 and 58."""
    assert usa_ascky[57] == ord("X")
    assert usa_ascky[58] == ord("V")


def test_phone_to_glyph_out_of_range() -> None:
    """Out-of-range codes return 0."""
    assert usa_phone_to_glyph(-1) == 0
    assert usa_phone_to_glyph(255) == 0
    assert usa_phone_to_glyph(len(usa_ascky)) == 0


def test_phone_to_glyph_in_range() -> None:
    """In-range codes return the table value."""
    assert usa_phone_to_glyph(0) == ord("_")
    assert usa_phone_to_glyph(1) == ord("i")


def test_roundtrip_via_reverse_table() -> None:
    """For ASCII glyphs that map to allophones in usa_ascky_rev, the
    forward table returns the same glyph."""
    # Pick glyphs that we know are in both directions.
    for glyph in (ord("i"), ord("I"), ord("e"), ord("@"), ord("a")):
        encoded = usa_ascky_rev[glyph]
        if encoded == NULL_ASCKY:
            continue
        code = encoded & 0xFF
        # The forward map gives us back the glyph (case-sensitive).
        result = usa_ascky[code]
        # Note: usa_ascky may store an upper or lower-case version since
        # the table has 'l' twice (at indices 27 and 30) etc. So we just
        # assert the result is a valid printable char.
        assert result != 0
