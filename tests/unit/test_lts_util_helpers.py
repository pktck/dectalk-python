"""Verify ``ls_util_is_year`` parity with ls_util.c."""

from __future__ import annotations

import pytest

from dectalk.lts import util_helpers as uh


@pytest.mark.parametrize(
    "year",
    [
        "1234",
        "1999",
        "2026",
        "9999",
        "1900",
        "2024",
        "1492",
        "1066",
    ],
)
def test_valid_years_accepted(year: str) -> None:
    """Plausible 4-digit years return True."""
    assert uh.ls_util_is_year(year) is True


@pytest.mark.parametrize(
    "non_year",
    [
        "0",  # too short, leading 0
        "12",  # too short
        "123",  # too short
        "12345",  # too long
        "abcd",  # non-digit
        "12ab",  # mixed
        "12 4",  # space
        "",  # empty
        "0234",  # leading 0
        "0000",  # leading 0
    ],
)
def test_non_year_rejected(non_year: str) -> None:
    """Strings that don't match the year shape return False."""
    assert uh.ls_util_is_year(non_year) is False


def test_double_zero_after_first_digit_rejected() -> None:
    """The C source rejects "X00Y" patterns (e.g. '1001')."""
    assert uh.ls_util_is_year("1001") is False
    assert uh.ls_util_is_year("9009") is False


def test_double_zero_handling() -> None:
    """The C source rejects when positions 1 AND 2 are BOTH '0' (X00Y form).

    - '1100' has positions 1-2 = '1', '0' → accepted
    - '2000' has positions 1-2 = '0', '0' → rejected (X00Y form)
    - '2050' has positions 1-2 = '0', '5' → accepted
    """
    assert uh.ls_util_is_year("1100") is True
    assert uh.ls_util_is_year("2000") is False
    assert uh.ls_util_is_year("2050") is True


def test_trailing_fraction_rejected() -> None:
    """Latin-1 ¼ (0xBC) and ½ (0xBD) at end → False."""
    # These never pass digit-check anyway, but document the intent.
    assert uh.ls_util_is_year("123\xbc") is False  # ¼
    assert uh.ls_util_is_year("123\xbd") is False  # ½


def test_bytes_input_accepted() -> None:
    """The function accepts bytes input as well as str."""
    assert uh.ls_util_is_year(b"1999") is True
    assert uh.ls_util_is_year(b"0234") is False


def test_x00y_form_rejected() -> None:
    """The C source rejects 4-digit numbers whose 2nd and 3rd digits are BOTH '0'.

    Examples: 1001 (rejected), 2009 (rejected), 9000 (rejected).
    But 1010, 2020, 2050, etc. have position 2 != '0' so accepted.
    """
    # X00Y forms — both positions 1 AND 2 are '0'.
    rejected_x00y = ["1001", "2009", "9000", "5006", "1004"]
    for year in rejected_x00y:
        assert uh.ls_util_is_year(year) is False, year

    # Years where position 2 is non-zero — accepted.
    accepted = ["2010", "2020", "1050", "1234", "9876"]
    for year in accepted:
        assert uh.ls_util_is_year(year) is True, year
