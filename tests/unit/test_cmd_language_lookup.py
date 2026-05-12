"""Verify ``cm_phon_lookup_language`` parity with cm_phon.c."""

from __future__ import annotations

import pytest

from dectalk.cmd import language_lookup as ll


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (b"us", 0),  # US English
        (b"uk", 1),  # UK English
        (b"sp", 2),  # Castilian Spanish
        (b"gr", 3),  # German
        (b"la", 4),  # Latin-American Spanish
        (b"fr", 5),  # French
    ],
)
def test_known_languages(code: bytes, expected: int) -> None:
    """Each canonical 2-letter code returns its index."""
    assert ll.cm_phon_lookup_language(code[0], code[1]) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (b"US", 0),
        (b"Uk", 1),
        (b"SP", 2),
        (b"Gr", 3),
        (b"LA", 4),
        (b"FR", 5),
    ],
)
def test_case_insensitive(code: bytes, expected: int) -> None:
    """Upper / mixed case input is case-folded via ls_lower."""
    assert ll.cm_phon_lookup_language(code[0], code[1]) == expected


@pytest.mark.parametrize(
    "code",
    [b"xx", b"de", b"jp", b"ru", b"ab"],
)
def test_unknown_languages_return_negative_one(code: bytes) -> None:
    """Unknown codes return -1."""
    assert ll.cm_phon_lookup_language(code[0], code[1]) == -1


def test_language_prefixes_layout() -> None:
    """The table contains exactly the 6 canonical codes in order."""
    assert ll.language_prefixes == b"usukspgrlafr"
    assert ll.language_size == 12


def test_lookup_partial_match_no() -> None:
    """A correct first byte but wrong second returns -1."""
    # 'u' is the first byte of both 'us' and 'uk', so a partial match
    # could be ambiguous. With 'X' as the second byte, no entry matches.
    assert ll.cm_phon_lookup_language(ord("u"), ord("X")) == -1
