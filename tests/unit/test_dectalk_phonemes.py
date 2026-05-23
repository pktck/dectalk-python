"""Tests for the DECtalk-phonemic-string → ARPABET converter."""

from __future__ import annotations

import pytest

from dectalk.dic.dectalk_phonemes import decode


@pytest.mark.parametrize(
    ("source", "expected_codes"),
    [
        # "hello" — DECtalk: hxl'o. The C oracle's
        # ``TextToSpeechConvertToPhonemes`` returns ``hx ax ll ' ow`` for
        # "hello" (see issue #133); ``x`` in the DECtalk phonemic
        # alphabet is the unstressed schwa US_AX, distinct from the
        # stressed wedge ``^`` = US_AH.
        ("hxl'o", ["HH", "AX0", "L", "OW1"]),
        # "world" — DECtalk: wRld
        ("wRld", ["W", "ER0", "L", "D"]),
        # "cat" — DECtalk: k@t
        ("k@t", ["K", "AE0", "T"]),
        # "say" — DECtalk: s'e
        ("s'e", ["S", "EY1"]),
    ],
)
def test_decode_known_words(source: str, expected_codes: list[str]) -> None:
    assert decode(source) == expected_codes


def test_primary_stress_attaches_to_next_vowel() -> None:
    """A leading apostrophe should give the following vowel a 1-digit."""
    out = decode("'a")
    assert out == ["AA1"]


def test_secondary_stress_attaches_to_next_vowel() -> None:
    out = decode("`a")
    assert out == ["AA2"]


def test_default_stress_is_zero() -> None:
    out = decode("a")
    assert out == ["AA0"]


def test_letter_separator_is_skipped() -> None:
    """The ``*`` in initialisms (e.g. AARP) should not affect output."""
    a = decode("'i*'i")
    b = decode("'i'i")
    assert a == b == ["IY1", "IY1"]


def test_unknown_char_is_skipped() -> None:
    """Unknown characters should be silently dropped, not crash."""
    assert decode("k?@t") == ["K", "AE0", "T"]


def test_consonants_get_no_stress_digit() -> None:
    out = decode("p")
    assert out == ["P"]


def test_empty_string() -> None:
    assert decode("") == []


# -----------------------------------------------------------------------
# Issue #133 — IX vs AH vs AX schwa-quality distinctions.
# -----------------------------------------------------------------------
# The DECtalk phonemic alphabet uses three different symbols for the
# reduced/centralised vowel family that English merges into "schwa":
#   ``^`` -> US_AH = ARPABET AH  (stressed wedge: "but", "cup")
#   ``x`` -> US_AX = ARPABET AX  (unstressed mid-central: "sofa", "banana")
#   ``|`` -> US_IX = ARPABET IX  (unstressed high-front: "roses", "hospital")
# Per the C source ``src/dapi/src/include/usa_phon.tab`` the
# ``usa_ascky[]`` row maps these directly; before issue #133 all three
# Python entries collapsed to ARPABET AH, losing the alternation. The
# tests below pin each symbol to its distinct ARPABET output so the
# regression cannot reappear.


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("^", ["AH0"]),  # caret -> US_AH (stressed wedge)
        ("x", ["AX0"]),  # lowercase x -> US_AX (mid-central schwa)
        ("|", ["IX0"]),  # vertical bar -> US_IX (high-front schwa)
        ("X", ["AX0"]),  # uppercase X aliased to AX
    ],
)
def test_schwa_quality_distinctions(source: str, expected: list[str]) -> None:
    """``^`` / ``x`` / ``|`` decode to three distinct ARPABET symbols."""
    assert decode(source) == expected


def test_ix_distinct_from_ah_and_ax() -> None:
    """The three schwa-family ARPABET outputs are pairwise distinct."""
    ah = decode("^")[0].rstrip("012")
    ax = decode("x")[0].rstrip("012")
    ix = decode("|")[0].rstrip("012")
    assert ah == "AH"
    assert ax == "AX"
    assert ix == "IX"
    assert len({ah, ax, ix}) == 3, "schwa-quality codes must not collapse"
