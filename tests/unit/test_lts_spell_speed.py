"""Verify ``ls_spel_spell_speed`` parity with ls_spel.c."""

from __future__ import annotations

import pytest

from dectalk.lts import spell_speed as ss


@pytest.mark.parametrize("word", ["A", "X", "Z", "a", "x", "z"])
def test_single_letter_fast(word: str) -> None:
    """A single letter is always FAST."""
    assert ss.ls_spel_spell_speed(word) == ss.FAST


@pytest.mark.parametrize("word", ["AB", "abc", "TTY"])
def test_short_word_fast(word: str) -> None:
    """Words with fewer than 4 letters are FAST."""
    assert ss.ls_spel_spell_speed(word) == ss.FAST


@pytest.mark.parametrize("word", ["AT&T", "FA&T", "R&B"])
def test_ampersand_special_case(word: str) -> None:
    """Length-4-with-1-ampersand (e.g. ``AT&T``) and length-3 are FAST."""
    assert ss.ls_spel_spell_speed(word) == ss.FAST


@pytest.mark.parametrize("word", ["HELLO", "BANANA", "DECTALK", "longer"])
def test_long_words_slow(word: str) -> None:
    """Length >= 4 (and not the AT&T pattern) is SLOW."""
    assert ss.ls_spel_spell_speed(word) == ss.SLOW


@pytest.mark.parametrize("word", ["AB1", "X9Y", "ABC1", "$#@"])
def test_non_alpha_slow(word: str) -> None:
    """A non-alpha non-ampersand character forces SLOW."""
    assert ss.ls_spel_spell_speed(word) == ss.SLOW


def test_bytes_input_accepted() -> None:
    """Accepts bytes."""
    assert ss.ls_spel_spell_speed(b"AT&T") == ss.FAST
    assert ss.ls_spel_spell_speed(b"HELLO") == ss.SLOW


def test_case_insensitivity_via_ls_lower() -> None:
    """Case-folding via ls_lower means upper-case is treated as alpha."""
    assert ss.ls_spel_spell_speed("ABCD") == ss.SLOW  # 4 letters → SLOW (no &)
    assert ss.ls_spel_spell_speed("abcd") == ss.SLOW
    assert ss.ls_spel_spell_speed("Ab") == ss.FAST  # 2 letters


def test_multiple_ampersands() -> None:
    """4 chars with TWO ampersands is NOT the special case (needs 1)."""
    # 'A&B&': 4 chars, 2 ampersands — fails the namper==1 check → SLOW
    assert ss.ls_spel_spell_speed("A&B&") == ss.SLOW


def test_long_with_ampersand_slow() -> None:
    """A long string with an ampersand isn't the AT&T pattern."""
    assert ss.ls_spel_spell_speed("ATM&T&") == ss.SLOW
