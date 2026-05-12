"""Verify ``speak_2_digits`` / ``speak_3_digits`` / ``speak_4_digits``."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.number_words import (
    _US_IX,
    _US_TH,
    speak_2_digits,
    speak_3_digits,
    speak_4_digits,
    speak_digit_group,
)
from dectalk.lts.phone_list import iter_phone_list_until_sil
from dectalk.lts.phoneme_words import (
    p11,
    p20,
    pand,
    phundred,
    pordin,
    ptens,
    pthousand,
    punits,
    upunits,
)


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
    expected_prefix = iter_phone_list_until_sil(ptens[4 - 2])
    assert result[: len(expected_prefix)] == expected_prefix
    assert WBOUND in result


def test_3_digit_leading_zero_returns_none() -> None:
    """``0XX`` returns None."""
    assert speak_3_digits(0, 1, 2) is None


def test_3_digit_round_hundred() -> None:
    """``200`` returns punits[2] + WBOUND + phundred (no trailing)."""
    result = speak_3_digits(2, 0, 0)
    assert result is not None
    expected_prefix = iter_phone_list_until_sil(punits[2])
    assert result[: len(expected_prefix)] == expected_prefix
    hundred = iter_phone_list_until_sil(phundred)
    assert hundred[0] in result


def test_3_digit_full_form() -> None:
    """``234`` includes ``two``, ``hundred``, and ``thirty four``."""
    result = speak_3_digits(2, 3, 4)
    assert result is not None
    assert result.count(WBOUND) >= 2


def test_4_digit_leading_zero_returns_none() -> None:
    """``0XXX`` returns None."""
    assert speak_4_digits(0, 1, 2, 3) is None


def test_4_digit_thousands_round() -> None:
    """``5000`` → upunits[5] WBOUND pthousand."""
    result = speak_4_digits(5, 0, 0, 0)
    assert result is not None
    expected_unit = iter_phone_list_until_sil(upunits[5])
    expected_thousand = iter_phone_list_until_sil(pthousand)
    assert result[: len(expected_unit)] == expected_unit
    assert result[-len(expected_thousand) :] == expected_thousand
    assert WBOUND in result


def test_4_digit_x_hundred() -> None:
    """``3400`` → 'thirty-four hundred'."""
    result = speak_4_digits(3, 4, 0, 0)
    assert result is not None
    expected_hundred = iter_phone_list_until_sil(phundred)
    assert result[-len(expected_hundred) :] == expected_hundred


def test_4_digit_year_style() -> None:
    """``1984`` (year-style) → '19 84' as two 2-digit numbers."""
    result = speak_4_digits(1, 9, 8, 4)
    assert result is not None
    assert WBOUND in result


# ---- speak_digit_group ----


def test_digit_group_round_hundreds() -> None:
    """``500`` → 'five hundred'."""
    result = speak_digit_group(5, 0, 0)
    expected_unit = iter_phone_list_until_sil(upunits[5])
    expected_hundred = iter_phone_list_until_sil(phundred)
    assert result[: len(expected_unit)] == expected_unit
    assert result[-len(expected_hundred) :] == expected_hundred


def test_digit_group_with_and() -> None:
    """``123`` → 'one hundred and twenty three'. The pand bytes appear."""
    result = speak_digit_group(1, 2, 3)
    pand_inner = iter_phone_list_until_sil(pand)
    joined = bytes(result)
    assert bytes(pand_inner) in joined or len(pand_inner) == 0


def test_digit_group_teen_handling() -> None:
    """``015`` (zero-hundreds, teen tens) → 'fifteen'."""
    from dectalk.lts.phoneme_words import pteens  # noqa: PLC0415 — keep test imports tight

    result = speak_digit_group(0, 1, 5)
    expected = iter_phone_list_until_sil(pteens[5])
    assert result == expected


def test_digit_group_ordinal_thirtieth() -> None:
    """``030`` ordinal → 'thirtieth' (ptens[30/10-2] + IX + TH)."""
    result = speak_digit_group(0, 3, 0, ordinal=True)
    assert result[-2:] == [_US_IX, _US_TH]


def test_digit_group_ordinal_second() -> None:
    """``002`` ordinal → 'second' (pordin[2])."""
    result = speak_digit_group(0, 0, 2, ordinal=True)
    expected = iter_phone_list_until_sil(pordin[2])
    assert result == expected
