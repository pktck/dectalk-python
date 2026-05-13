"""Verify par_check_word_string matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_check_word_string import par_check_word_string
from dectalk.cmd.par_structs import ReturnValue
from dectalk.cmd.rule_states import FAIL, SUCCESS


def test_word_with_vowel_and_consonant_passes() -> None:
    """A normal word "cat" passes (has both vowel and consonant)."""
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_check_word_string(b"cat", rv)
    assert rv.value == SUCCESS


def test_no_vowel_fails() -> None:
    """A string of only consonants fails."""
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_check_word_string(b"bcd", rv)
    assert rv.value == FAIL


def test_no_consonant_fails() -> None:
    """A string of only vowels fails."""
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_check_word_string(b"aei", rv)
    assert rv.value == FAIL


def test_single_letter_fails() -> None:
    """A single-letter span (length 1) fails the >=2 length check."""
    rv = ReturnValue(output_pos=0, output_offset=1, value=SUCCESS)
    par_check_word_string(b"a", rv)
    assert rv.value == FAIL


def test_non_alpha_in_middle_fails() -> None:
    """A digit in the span fails the TYPE_alpha check."""
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_check_word_string(b"c4t", rv)
    assert rv.value == FAIL


def test_optional_minus_one_is_noop() -> None:
    """When optional==-1, the function returns without checking."""
    rv = ReturnValue(output_pos=0, output_offset=1, optional=-1, value=SUCCESS)
    par_check_word_string(b"a", rv)
    # Would normally fail (length 1) — but optional==-1 skips the check.
    assert rv.value == SUCCESS


def test_starts_from_output_pos() -> None:
    """``output_pos`` is the start of the checked span."""
    rv = ReturnValue(output_pos=3, output_offset=3, value=SUCCESS)
    par_check_word_string(b"xyzcat", rv)
    # "cat" at offset 3 has both vowel and consonant.
    assert rv.value == SUCCESS
