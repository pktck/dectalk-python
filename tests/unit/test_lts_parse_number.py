"""Verify ls_task_parse_number against ls_task.c."""

from __future__ import annotations

from dectalk.lts.parse_number import ls_task_parse_number


def test_empty_word_returns_zero_end() -> None:
    """Empty input scans nothing."""
    num, end = ls_task_parse_number(b"")
    assert end == 0
    assert num.n_ilp is None


def test_non_digit_returns_zero_end() -> None:
    """A word not starting with a digit / fraction is rejected."""
    num, end = ls_task_parse_number(b"hello")
    assert end == 0
    assert num.n_ilp is None


def test_simple_integer() -> None:
    """``42`` parses as 2-digit integer."""
    num, end = ls_task_parse_number(b"42")
    assert end == 2
    assert num.n_ilp is not None
    # Integer part covers offsets 0..2.


def test_long_integer() -> None:
    """``1234567`` parses as 7-digit integer (no separator)."""
    num, end = ls_task_parse_number(b"1234567")
    assert end == 7
    assert num.n_ilp is not None


def test_thousands_separator_us() -> None:
    """``1,234`` parses 1..234 as a thousands group."""
    num, end = ls_task_parse_number(b"1,234")
    assert end == 5
    assert num.n_ilp is not None


def test_thousands_separator_european() -> None:
    """In European mode, ``.`` is the thousands separator."""
    num, end = ls_task_parse_number(b"1.234", schar=ord("."), fchar=ord(","))
    assert end == 5
    assert num.n_ilp is not None


def test_decimal_point() -> None:
    """``3.14`` integer + fractional part."""
    num, end = ls_task_parse_number(b"3.14")
    assert end == 4
    assert num.n_ilp is not None
    assert num.n_flp is not None


def test_decimal_only_without_integer() -> None:
    """``.5`` parses the fractional part only — n_ilp is None.

    The C source's integer-part scan is gated on starting with a
    digit or fraction byte; ``.`` fails that test, so the integer
    part stays NULL. The fractional-part scan that follows then
    matches ``fchar`` and walks the trailing digits.
    """
    num, end = ls_task_parse_number(b".5")
    assert end == 2
    assert num.n_ilp is None  # integer part not matched
    assert num.n_flp is not None  # fractional part matched


def test_quarter_fraction() -> None:
    """``¼`` (0xBC) terminates the integer part immediately."""
    num, end = ls_task_parse_number(b"\xbc")
    assert end == 1
    assert num.n_ilp is not None


def test_half_fraction() -> None:
    """``½`` (0xBD) terminates the integer part immediately."""
    num, end = ls_task_parse_number(b"\xbd")
    assert end == 1
    assert num.n_ilp is not None


def test_exponent_math_mode() -> None:
    """``1.5e10`` parses integer + fraction + exponent in math mode."""
    num, end = ls_task_parse_number(b"1.5e10", math_mode=True)
    assert end == 6
    assert num.n_ilp is not None
    assert num.n_flp is not None
    assert num.n_elp is not None


def test_exponent_without_math_mode() -> None:
    """Outside math mode, ``e10`` does not become an exponent."""
    num, end = ls_task_parse_number(b"1.5e10", math_mode=False)
    # The 'e' isn't matched, scan stops at offset 3.
    assert end == 3
    assert num.n_ilp is not None
    assert num.n_flp is not None
    assert num.n_elp is None


def test_exponent_with_sign() -> None:
    """``1e-5`` and ``1e+5`` both match in math mode."""
    for word in (b"1e-5", b"1e+5"):
        _, end = ls_task_parse_number(word, math_mode=True)
        assert end == len(word)


def test_stops_at_non_digit() -> None:
    """``123foo`` stops scanning at ``f``."""
    _, end = ls_task_parse_number(b"123foo")
    assert end == 3


def test_thousands_group_must_be_exactly_3() -> None:
    """``1,2345`` doesn't qualify (group has 4 digits)."""
    _, end = ls_task_parse_number(b"1,2345")
    # Scan stops at the separator since the group fails the 3-digit test.
    assert end == 1
