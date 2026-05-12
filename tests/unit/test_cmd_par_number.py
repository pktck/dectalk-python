"""Verify ``par_convert_number*`` parity with par_pars.c."""

from __future__ import annotations

import pytest

from dectalk.cmd import par_number as pn


@pytest.mark.parametrize(
    ("buf", "expected"),
    [
        (b"0", 0),
        (b"1", 1),
        (b"42", 42),
        (b"1234", 1234),
        (b"32767", 32767),  # max short
        (b"99999", 99999),  # larger; Python has no short limit
        (b"100", 100),
        (b"007", 7),  # leading zeros — still 7
    ],
)
def test_decimal_values(buf: bytes, expected: int) -> None:
    """Pure-digit buffer → digit value."""
    assert pn.par_convert_number_new2(buf) == expected


@pytest.mark.parametrize(
    ("buf", "expected"),
    [
        (b"42abc", 42),  # stops at first non-digit
        (b"100 ", 100),  # stops at space
        (b"5,6", 5),  # stops at comma
        (b"7.0", 7),  # stops at period (so this is digit-only parse, not float)
        (b"", 0),  # empty
        (b"abc", 0),  # no leading digit
        (b" 42", 0),  # leading space — no digits at start
    ],
)
def test_stops_at_non_digit(buf: bytes, expected: int) -> None:
    """Scanner stops at the first non-digit byte."""
    assert pn.par_convert_number_new2(buf) == expected


def test_str_input() -> None:
    """Accepts str as well as bytes (consistent with other helpers)."""
    assert pn.par_convert_number_new2("123") == 123
    assert pn.par_convert_number_new2("42 abc") == 42


def test_matches_int_for_pure_digits() -> None:
    """For pure-digit strings, the function == int(str)."""
    for n in (0, 1, 5, 10, 42, 100, 999, 1000, 12345):
        assert pn.par_convert_number_new2(str(n)) == n


# ---- par_convert_number (fixed length) ----


@pytest.mark.parametrize(
    ("buf", "num", "expected"),
    [
        (b"12345", 5, 12345),  # consume all 5 digits
        (b"12345", 3, 123),  # capped at 3
        (b"12345", 0, 0),  # consume zero bytes → 0
        (b"42abc", 5, 42),  # stops at 'a'
        (b"42abc", 2, 42),  # stops at the cap
        (b"007", 3, 7),  # leading zeros
        (b"abc", 3, 0),  # no leading digits
    ],
)
def test_convert_number_fixed_length(buf: bytes, num: int, expected: int) -> None:
    """``par_convert_number`` honours both the digit-stop and the length cap."""
    assert pn.par_convert_number(buf, num) == expected


def test_convert_number_short_buffer() -> None:
    """``num`` larger than the buffer should not over-read."""
    assert pn.par_convert_number(b"42", 10) == 42


# ---- par_convert_number_new (returns length) ----


@pytest.mark.parametrize(
    ("buf", "expected_value", "expected_length"),
    [
        (b"42abc", 42, 2),
        (b"12345", 12345, 5),
        (b"0", 0, 1),
        (b"007abc", 7, 3),
        (b"", 0, 0),
        (b"abc", 0, 0),
        (b" 42", 0, 0),  # leading space — no digits at start
    ],
)
def test_convert_number_new_reports_length(
    buf: bytes,
    expected_value: int,
    expected_length: int,
) -> None:
    """``par_convert_number_new`` returns both the value and digit count."""
    assert pn.par_convert_number_new(buf) == (expected_value, expected_length)


def test_convert_number_new_str_input() -> None:
    """Accepts str input as well as bytes."""
    assert pn.par_convert_number_new("123abc") == (123, 3)
