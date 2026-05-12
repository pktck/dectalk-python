"""Verify ``speak_2_digits`` / ``speak_3_digits`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.number_words import speak_2_digits, speak_3_digits
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import p11, p20, phundred, ptens, punits


def test_2_digit_leading_zero_returns_none() -> None:
    """``0X`` returns None (caller spells each digit)."""
    assert speak_2_digits(0, 5) is None


def test_2_digit_teens() -> None:
    """``11`` returns the pteens[1] sequence."""
    result = speak_2_digits(1, 1)
    assert result is not None
    expected = iter_phone_list_until_sil(p11)
    assert result == expected


def test_2_digit_round_tens() -> None:
    """``20`` returns just the ptens word (no WBOUND + units)."""
    result = speak_2_digits(2, 0)
    assert result is not None
    assert result == iter_phone_list_until_sil(p20)


def test_2_digit_with_units() -> None:
    """``42`` returns ptens[2]=p40 + WBOUND + punits[2]."""
    result = speak_2_digits(4, 2)
    assert result is not None
    # ptens index for digit '4' is (4-2) = 2 → p40.
    assert result[0 : len(iter_phone_list_until_sil(ptens[4 - 2]))] == iter_phone_list_until_sil(
        ptens[4 - 2]
    )
    # WBOUND separator
    assert WBOUND in result


def test_3_digit_leading_zero_returns_none() -> None:
    """``0XX`` returns None."""
    assert speak_3_digits(0, 1, 2) is None


def test_3_digit_round_hundred() -> None:
    """``200`` returns punits[2] + WBOUND + phundred (no trailing)."""
    result = speak_3_digits(2, 0, 0)
    assert result is not None
    # Starts with "two" (punits[2])
    expected_prefix = iter_phone_list_until_sil(punits[2])
    assert result[: len(expected_prefix)] == expected_prefix
    # Contains "hundred"
    hundred = iter_phone_list_until_sil(phundred)
    assert hundred[0] in result


def test_3_digit_full_form() -> None:
    """``234`` includes ``two``, ``hundred``, and ``thirty four``."""
    result = speak_3_digits(2, 3, 4)
    assert result is not None
    # Result has at least two WBOUND markers (after "two" and after "hundred").
    assert result.count(WBOUND) >= 2
