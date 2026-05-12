"""Verify ``ls_proc_is_date`` parity with l_us_pr1.c."""

from __future__ import annotations

import pytest

from dectalk.lts import date_recognizer as dr


@pytest.mark.parametrize(
    "date",
    [
        "1-jan",  # 1-digit day, no year
        "5-feb",
        "23-aug",  # 2-digit day, no year
        "31-dec",
        "1-jan-25",  # 2-digit year
        "23-aug-84",
        "5-jan-2025",  # 4-digit year
        "23-aug-1984",
        "12-mar-99",
        "9-apr-2026",
    ],
)
def test_valid_dates_accepted(date: str) -> None:
    """Each plausible date format returns True."""
    assert dr.ls_proc_is_date(date) is True


@pytest.mark.parametrize(
    "non_date",
    [
        "",
        "abc",
        "23",
        "23-",
        "23-aug-",  # trailing dash, no year
        "-jan-25",
        "23-xyz",  # not a real month
        "1-fff-25",
        "ja-jan-25",  # non-digit day
        "23/aug/84",  # wrong separator
        "23-aug-12345",  # 5-digit year — too long
        "23-aug-1",  # 1-digit year — too short
        "23-aug-1a",  # non-digit in year
        "1-jan-2",  # 1-digit year
        "999-jan",  # 3-digit day
        " 1-jan",  # leading space
        "1-jan ",  # trailing space
        "1-jan-1234x",  # extra char
    ],
)
def test_non_dates_rejected(non_date: str) -> None:
    """Non-date strings return False."""
    assert dr.ls_proc_is_date(non_date) is False


def test_bytes_input_accepted() -> None:
    """The function accepts bytes input."""
    assert dr.ls_proc_is_date(b"23-aug-84") is True
    assert dr.ls_proc_is_date(b"xxx") is False


def test_month_case_sensitivity() -> None:
    """The C source compares bytes directly; ``months`` is lowercase.

    Upper-case ``Jan`` doesn't match because the C compares ``buf[i]``
    (a raw byte) against ``months[i][k]`` (lower-case byte).
    """
    assert dr.ls_proc_is_date("23-jan-84") is True
    # 'JAN' should NOT match against 'jan' (case-sensitive in C).
    assert dr.ls_proc_is_date("23-JAN-84") is False


# ---- ls_proc_is_frac ----


@pytest.mark.parametrize(
    "frac",
    [
        "1/2",
        "1/3",
        "1/4",
        "1/8",
        "3/4",
        "5/8",
        "9/10",
        "9/16",
        "1/32",
        "1/100",
        "9/100",
        "11/100",
        "99/100",
        "1/2%",  # trailing %
        "1/3%",
        "50/100%",
    ],
)
def test_valid_fractions_accepted(frac: str) -> None:
    """Each plausible fraction returns True."""
    assert dr.ls_proc_is_frac(frac) is True


@pytest.mark.parametrize(
    "non_frac",
    [
        "",
        "0/2",  # leading zero numerator
        "1/0",  # leading zero in 1-digit denominator
        "/2",  # missing numerator
        "1/",  # missing denominator
        "1.2",  # period instead of /
        "1//2",  # double slash
        "a/2",  # non-digit
        "1/2a",  # extra char
        "1/1000",  # 4-digit denominator
        "1/250",  # 3-digit denominator not 100
        "1/01",  # leading zero in denominator
        "1/2 ",  # trailing space
        " 1/2",  # leading space
        "1/2%a",  # extra after %
        "1/2%%",  # double %
    ],
)
def test_non_fractions_rejected(non_frac: str) -> None:
    """Non-fraction strings return False."""
    assert dr.ls_proc_is_frac(non_frac) is False


def test_frac_bytes_input_accepted() -> None:
    """The function accepts bytes input."""
    assert dr.ls_proc_is_frac(b"1/2") is True
    assert dr.ls_proc_is_frac(b"abc") is False


def test_frac_3_digit_denominator_must_be_100() -> None:
    """3-digit denominator only valid if exactly ``100``."""
    assert dr.ls_proc_is_frac("1/100") is True
    assert dr.ls_proc_is_frac("1/101") is False
    assert dr.ls_proc_is_frac("1/110") is False
    assert dr.ls_proc_is_frac("1/999") is False


def test_frac_2_digit_numerator() -> None:
    """2-digit numerator accepted (1..99)."""
    assert dr.ls_proc_is_frac("10/100") is True
    assert dr.ls_proc_is_frac("99/100") is True
    assert dr.ls_proc_is_frac("99/100%") is True
