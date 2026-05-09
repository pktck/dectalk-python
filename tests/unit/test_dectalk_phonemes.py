"""Tests for the DECtalk-phonemic-string → ARPABET converter."""

from __future__ import annotations

import pytest

from dectalk.dic.dectalk_phonemes import decode


@pytest.mark.parametrize(
    ("source", "expected_codes"),
    [
        # "hello" — DECtalk: hxl'o
        ("hxl'o", ["HH", "AH0", "L", "OW1"]),
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
