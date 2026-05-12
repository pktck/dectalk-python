"""Verify ``cm_phon_lookup_asc`` parity with cm_phon.c."""

from __future__ import annotations

from dectalk.cmd.phon_lookup import cm_phon_lookup_asc
from dectalk.include.usa_ascky import usa_ascky


def test_lookup_first_underscore() -> None:
    """The ``_`` glyph (silence) is at index 0."""
    assert cm_phon_lookup_asc(ord("_")) == 0


def test_lookup_letter_i() -> None:
    """``i`` is at index 1 in usa_ascky."""
    assert cm_phon_lookup_asc(ord("i")) == 1


def test_lookup_not_found() -> None:
    """A non-ASCII-phoneme byte returns -1."""
    # 0x00 isn't in the allophone range of usa_ascky.
    # Actually 0 IS in the table at index 59 (zero padding). Pick a
    # byte that's definitely not present.
    assert cm_phon_lookup_asc(0xFF) == -1


def test_lookup_custom_table() -> None:
    """A caller can pass a different lookup table."""
    custom = b"ABCDE"
    assert cm_phon_lookup_asc(ord("C"), ascky=custom) == 2
    assert cm_phon_lookup_asc(ord("Z"), ascky=custom) == -1


def test_lookup_returns_first_match() -> None:
    """When duplicates exist, the first match wins."""
    # The default usa_ascky has 'l' at both indices 27 and 30. Verify
    # we get the first one.
    result = cm_phon_lookup_asc(ord("l"))
    # The first occurrence — check it matches the table.
    assert result < len(usa_ascky)
    assert usa_ascky[result] == ord("l")
    # And it's the earliest.
    for i in range(result):
        assert usa_ascky[i] != ord("l")
