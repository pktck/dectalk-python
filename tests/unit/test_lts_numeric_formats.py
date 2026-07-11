"""Verify ``lts.numeric_formats`` — the ls_task.c numeric dispatch.

Every expected byte string below was captured from
``CAPI.convert_to_phonemes`` against the shipped oracle binary before
pinning (issue #225); the oracle-backed equivalents live in
``tests/parity/test_stage_lts_parity.py::test_numeric_formats_match_c``.
These unit pins keep the no-oracle CI lane honest.
"""

from __future__ import annotations

import pytest

from dectalk.lts.numeric_formats import (
    NumericExpansion,
    am_pm_phonemes,
    numeric_chunk_phonemes,
)

# ---- ordinals (ls_task.c:3953 + do_digit_group oflag arms) ----


@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ("1st", b"f ' rrs t "),
        ("42nd", b"f ' ort iy  s ' ehk axn d "),
        ("103rd", b"w ' ahn   hx' ahn d r axd   ) ehn d   th' rrd "),
        ("20th", b"t w ' ehn t iyixth"),
        ("11th", b"axll' ehv axn th"),
    ],
    ids=["1st", "42nd", "103rd", "20th", "11th"],
)
def test_ordinal_forms(chunk: str, expected: bytes) -> None:
    """Units / tens+IX+TH / teens+TH / hundred+pand ordinal arms."""
    result = numeric_chunk_phonemes(chunk)
    assert result is not None
    assert result.phonemes == expected


def test_uppercase_ordinal_folds_case() -> None:
    """``1ST`` matches — C runs ls_task_remove_case before the check."""
    result = numeric_chunk_phonemes("1ST")
    assert result is not None
    assert result.phonemes == b"f ' rrs t "


# ---- currency (ls_task_currency_processing) ----


@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ("$5", b"f ' ayv   d ' aallrrz "),
        ("$1.50", b"w ' ahn   d ' aallrr  ) ehn d   f ' ihf t iy  s ' ehn t s "),
        ("$0.01", b"z ' iyr ow  d ' aallrrz   ) ehn d   w ' ahn   s ' ehn t "),
        ("$3.00", b"thr ' iy  d ' aallrrz "),
    ],
    ids=["dollars-plural", "dollar-and-cents", "zero-dollar-one-cent", "double-zero-suppressed"],
)
def test_currency_forms(chunk: str, expected: bytes) -> None:
    """Plural Z / singular dollar / leading-zero cent skip / .00 arms."""
    result = numeric_chunk_phonemes(chunk)
    assert result is not None
    assert result.phonemes == expected


def test_currency_scale_word_lookahead_consumes_next() -> None:
    """``$5 million`` reorders to "five million dollars" (nwdtab)."""
    result = numeric_chunk_phonemes("$5", next_word="million")
    assert result == NumericExpansion(b"f ' ayv   m ' ihllyxaxn   d ' aallrrz ", consumed_next=True)


def test_currency_non_scale_next_word_not_consumed() -> None:
    """A non-nwdtab next word leaves the plain ``$5`` reading."""
    result = numeric_chunk_phonemes("$5", next_word="bucks")
    assert result is not None
    assert not result.consumed_next
    assert result.phonemes == b"f ' ayv   d ' aallrrz "


# ---- clock times (ls_proc_is_time / do_time) ----


def test_time_basic() -> None:
    """``3:30`` — hour, VPSTART join, minutes."""
    result = numeric_chunk_phonemes("3:30")
    assert result is not None
    assert result.is_time
    assert result.phonemes == b"thr ' iy) th' rrt iy"


def test_time_leading_zero_minutes_spelled() -> None:
    """``3:05`` spells the minutes "zero five" (C do_2_digits)."""
    result = numeric_chunk_phonemes("3:05")
    assert result is not None
    assert result.phonemes == b"thr ' iy) z ' iyr ow  f ' ayv "


def test_time_declines_wrapping_punctuation() -> None:
    """``(3:30)`` reads "three colon thirty" in C — do not claim."""
    assert numeric_chunk_phonemes("3:30", had_leading_punct=True) is None


def test_am_pm_lookahead_spells() -> None:
    """After-time am/pm words spell out, case-insensitively."""
    assert am_pm_phonemes("pm") == b"p ' iy  ' ehm "
    assert am_pm_phonemes("PM") == b"p ' iy  ' ehm "
    assert am_pm_phonemes("ampm") is None
    assert am_pm_phonemes("at") is None


# ---- fractions (ls_proc_is_frac / do_frac) ----


@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ("3/4", b"thr ' iy  f ' orths "),
        ("1/2", b"w ' ahn   hx' aef "),
        ("12/25", b"t w ' ehllv   t w ' ehn t iy  f ' ihf ths "),
    ],
    ids=["plural-ordinal-denom", "half", "month-day-looking"],
)
def test_fraction_forms(chunk: str, expected: bytes) -> None:
    """Ordinal denominators, halves, and the M/D-looking fraction."""
    result = numeric_chunk_phonemes(chunk)
    assert result is not None
    assert result.phonemes == expected


# ---- part-number ranges (ls_task_part_number) ----


def test_range_dash_is_spoken() -> None:
    """``10-20`` speaks the separator: "ten dash twenty"."""
    result = numeric_chunk_phonemes("10-20")
    assert result is not None
    assert result.phonemes == b"t ' ehn   d ' aesh  t w ' ehn t iy"


def test_part_number_short_alpha_run_spelled() -> None:
    """``B-52`` spells the short alpha run ("b dash fifty two")."""
    result = numeric_chunk_phonemes("B-52")
    assert result is not None
    assert result.phonemes == b"b ' iy  d ' aesh  f ' ihf t iy  t ' uw"


# ---- signed numbers / plurals / dates ----


def test_signed_integer_uses_sign_prefix() -> None:
    """``-5`` (sign stripped into leading punct) → "minus five"."""
    result = numeric_chunk_phonemes("5", sign_prefix="-")
    assert result is not None
    assert result.phonemes == b"m ' ayn axs   f ' ayv "


def test_digit_plural() -> None:
    """``60s`` → "sixties" via ls_util_pluralize."""
    result = numeric_chunk_phonemes("60s")
    assert result is not None
    assert result.phonemes == b"s ' ihk s t iyz "


def test_dd_mon_date() -> None:
    """``23-aug-84`` → "august twenty third, eighty four"."""
    result = numeric_chunk_phonemes("23-aug-84")
    assert result is not None
    assert result.phonemes == b"' aog axs t   t w ' ehn t iy  th' rrd , ' eyt iy  f ' or"


# ---- bare 4-digit year form (issue #335) ----


def test_bare_year_reads_as_do_4_digits() -> None:
    """``1984`` → the year form "nineteen eighty four" (ls_util_is_year)."""
    result = numeric_chunk_phonemes("1984")
    assert result is not None
    assert result.phonemes == b"n ' ayn * t ' iyn   ' eyt iy  f ' or"


def test_bare_year_tens_top_half() -> None:
    """``1066`` → "ten sixty six" (top half reads as tens, not a teen)."""
    result = numeric_chunk_phonemes("1066")
    assert result is not None
    assert result.phonemes == b"t ' ehn   s ' ihk s t iy  s ' ihk s "


def test_bare_year_xy00_hundred_form() -> None:
    """``1900`` → "nineteen hundred" (the XY00 do_4_digits branch)."""
    result = numeric_chunk_phonemes("1900")
    assert result is not None
    assert result.phonemes == b"n ' ayn * t ' iyn   hx' ahn d r axd "


def test_bare_year_leading_zero_second_pair_spells() -> None:
    """``1905`` → "nineteen zero five" — the ``05`` second pair SPELLS.

    Pins the ``ls_proc_do_4_digits_full`` fix: C calls the full
    ``ls_proc_do_2_digits`` on the second pair, which spells a leading
    zero; the list-based ``speak_4_digits`` used to drop it.
    """
    result = numeric_chunk_phonemes("1905")
    assert result is not None
    assert result.phonemes == b"n ' ayn * t ' iyn   z ' iyr ow  f ' ayv "


def test_signed_4digit_is_not_a_year() -> None:
    """A signed 4-digit token is cardinal (C sign-gates ``is_year``)."""
    result = numeric_chunk_phonemes("1984", sign_prefix="-")
    assert result is not None
    assert result.phonemes.startswith(b"m ' ayn axs")  # "minus ..."
    assert b"th' awz axn d" in result.phonemes  # "... thousand ..." (cardinal)


# ---- fall-through gates (legacy path must keep these) ----


@pytest.mark.parametrize(
    "chunk",
    [
        "5",  # pure digits — _digit_expand owns them
        "2000",  # round thousand — is_year excludes X000, stays cardinal
        "2001",  # X00Y — is_year excludes embedded "00", stays cardinal
        "5000",  # round thousand — cardinal
        "12345",  # 5 digits — not a year, cardinal
        "3.14",  # dotted decimal — legacy branch
        "1,000th",  # kernel splits digit-comma+suffix upstream
        "3/4%",  # '%' splits into its own word upstream
        "10%",  # ditto
        "555-1212",  # NANP phone shape (NWS-claimed in C)
        "800-555-1212",
        "1-800-555-1212",
        "10/20/30",  # M/D/Y — kernel.normalize claims it
        "12:45:30.5",  # fractional-second time (NWS-claimed in C)
        "hello",
        "forty-two",
        "state-of-the-art",
        "ABC-123",  # 3+ alpha run needs the C dictionary probe
        "$",
        "$x",
        "99\xa2",  # non-ASCII (cent sign) — encoding out of scope
    ],
)
def test_unclaimed_chunks_fall_through(chunk: str) -> None:
    """Out-of-scope shapes return None so the legacy path runs."""
    assert numeric_chunk_phonemes(chunk) is None
