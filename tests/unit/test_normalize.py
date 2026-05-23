"""Tests for date / phone / URL text-normalization helpers."""

from __future__ import annotations

import pytest

from dectalk.kernel.normalize import try_date, try_phone, try_url
from dectalk.kernel.text import TokenKind, tokenize


@pytest.mark.parametrize(
    ("token", "expected_first"),
    [
        ("2024-05-09", "MAY"),
        ("5/9/2024", "MAY"),
        ("05-09-2024", "MAY"),
        ("12/31/24", "DECEMBER"),
    ],
)
def test_try_date_recognises_iso_and_us(token: str, expected_first: str) -> None:
    out = try_date(token)
    assert out is not None
    assert out[0] == expected_first


def test_try_date_rejects_invalid_dates() -> None:
    """Out-of-range month/day should fall through (treated as plain text)."""
    assert try_date("2024-13-01") is None
    assert try_date("2024-05-32") is None
    assert try_date("notadate") is None


def test_try_date_rejects_two_component_mm_dd() -> None:
    """Two-component ``MM/DD`` (no year) is NOT a date in C — matches fraction.

    C's ``ls_proc_is_date`` (``l_us_pr1.c`` lines 826+) only matches
    ``D-MMM[-YY[YY]]`` (alphabetic month abbreviation, dash separator).
    A two-component slash-separated token like ``12/25`` falls through
    to ``ls_proc_is_frac`` (``l_us_pr1.c`` lines 991+) which accepts
    1-2 digit numerator over 1-3 digit denominator, producing
    ``"twelve twenty-fifths"`` not ``"December 25th"``.

    Python's ``try_date`` mirrors this by requiring three components
    (with a year). Adding ``MM/DD`` date detection would *diverge*
    from C oracle behavior. See issue #145 and the
    ``docs/c_audit/kernel_textnorm.md`` "Tracked divergences" section.
    """
    # All of these read as fractions in C, not dates.
    assert try_date("12/25") is None
    assert try_date("01/01") is None
    assert try_date("7/8") is None
    assert try_date("13/45") is None
    assert try_date("1/2") is None
    # Two-component dash forms also rejected (C requires alpha month).
    assert try_date("12-25") is None
    assert try_date("01-01") is None


def test_try_phone_recognises_us_format() -> None:
    out = try_phone("555-1212")
    assert out == ["FIVE", "FIVE", "FIVE", "ONE", "TWO", "ONE", "TWO"]


def test_try_phone_recognises_full_us() -> None:
    out = try_phone("(555) 555-1212")
    assert out is not None
    assert out[:3] == ["FIVE", "FIVE", "FIVE"]


def test_try_phone_rejects_random_digits() -> None:
    assert try_phone("12345") is None  # wrong length
    assert try_phone("hello") is None


def test_try_url_basic() -> None:
    out = try_url("https://example.com")
    assert out is not None
    assert "EXAMPLE" in out
    assert "COM" in out
    assert "DOT" in out


def test_try_url_with_path() -> None:
    out = try_url("https://example.com/path")
    assert out is not None
    # Path section should appear after the domain.
    assert "EXAMPLE" in out
    assert "P" in out and "A" in out and "T" in out and "H" in out


def test_tokenize_routes_dates_to_try_date() -> None:
    tokens = tokenize("the date is 2024-05-09 today")
    words = [t.text for t in tokens if t.kind is TokenKind.WORD]
    assert "MAY" in words


def test_tokenize_routes_phone_numbers() -> None:
    tokens = tokenize("call 555-1212 now")
    words = [t.text for t in tokens if t.kind is TokenKind.WORD]
    assert "CALL" in words
    assert words.count("FIVE") >= 3


def test_tokenize_routes_urls() -> None:
    tokens = tokenize("visit https://example.com please")
    words = [t.text for t in tokens if t.kind is TokenKind.WORD]
    assert "VISIT" in words
    assert "EXAMPLE" in words
    assert "PLEASE" in words
