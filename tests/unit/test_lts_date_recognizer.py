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
