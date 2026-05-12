"""Verify ``ls_util_is_*`` predicates parity with ls_util.c."""

from __future__ import annotations

import pytest

from dectalk.include.cmd_codes import (
    INDEX,
    INDEX_BOOKMARK,
    INDEX_NOISE,
    INDEX_REPLY,
    INDEX_SENTENCE,
    INDEX_START,
    INDEX_STOP,
    INDEX_VOLUME,
    INDEX_WORDPOS,
    PFCONTROL,
    PSFONT,
)
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


# ---- ls_util_is_white ----


@pytest.mark.parametrize(
    "char",
    [
        " ",  # SPACE
        chr(0xA0),  # NBSP
        "\n",  # LF
        "\r",  # CR
        "\f",  # FF
    ],
)
def test_is_white_accepts_recognized_whitespace(char: str) -> None:
    """SPACE / NBSP / LF / CR / FF in the PFASCII font are whitespace."""
    assert uh.ls_util_is_white(ord(char)) is True


@pytest.mark.parametrize(
    "char",
    [
        "\t",  # HT — NOT whitespace per the C comment
        "\v",  # VT — NOT whitespace per the C comment
        "a",  # letter
        "0",  # digit
        ".",  # punctuation
        ",",  # comma
    ],
)
def test_is_white_rejects_other_chars(char: str) -> None:
    """HT/VT and printable characters are not whitespace."""
    assert uh.ls_util_is_white(ord(char)) is False


def test_is_white_rejects_non_ascii_font() -> None:
    """A space-value with a non-ASCII font is not whitespace."""
    # SPACE (0x20) with PFCONTROL font (0x1F00) — wrong font, not white.
    space_in_control_font = (PFCONTROL << PSFONT) | ord(" ")
    assert uh.ls_util_is_white(space_in_control_font) is False


# ---- ls_util_is_index ----


@pytest.mark.parametrize(
    "code",
    [
        INDEX,
        INDEX_REPLY,
        INDEX_BOOKMARK,
        INDEX_WORDPOS,
        INDEX_START,
        INDEX_STOP,
        INDEX_SENTENCE,
        INDEX_VOLUME,
        INDEX_NOISE,
    ],
)
def test_is_index_accepts_all_index_codes(code: int) -> None:
    """Each of the nine INDEX_* control codes is recognised."""
    assert uh.ls_util_is_index(code) is True


@pytest.mark.parametrize(
    "code",
    [
        0,  # nul
        ord("a"),  # plain ASCII
        ord(" "),  # space
        (PFCONTROL << PSFONT) | 0,  # control font, offset 0 = RATE
        (PFCONTROL << PSFONT) | 23,  # WORD_CLASS — not an index
    ],
)
def test_is_index_rejects_non_index_codes(code: int) -> None:
    """Non-index control codes and plain ASCII are not index markers."""
    assert uh.ls_util_is_index(code) is False


# ---- ls_util_is_dot ----


def test_is_dot_accepts_period_in_ascii() -> None:
    """A literal '.' in the PFASCII font is a dot."""
    assert uh.ls_util_is_dot(ord(".")) is True


@pytest.mark.parametrize(
    "code",
    [
        0,
        ord(","),
        ord("a"),
        ord(" "),
        (PFCONTROL << PSFONT) | ord("."),  # '.' but wrong font
    ],
)
def test_is_dot_rejects_other_codes(code: int) -> None:
    """Other characters / wrong fonts are not dots."""
    assert uh.ls_util_is_dot(code) is False


# ---- ls_util_is_clause ----


@pytest.mark.parametrize(
    # MARK_clause covers every character ls_task treats as a hard
    # clause break: ``! ' , - . : ; ?``. The C ``char_types`` array
    # is the source of truth.
    "char",
    ["!", "'", ",", "-", ".", ":", ";", "?"],
)
def test_is_clause_accepts_clause_punctuation(char: str) -> None:
    """Each MARK_clause character returns True."""
    assert uh.ls_util_is_clause(ord(char)) is True


@pytest.mark.parametrize(
    "char",
    ["a", "0", " ", "(", ")", '"'],
)
def test_is_clause_rejects_other_chars(char: str) -> None:
    """Letters, digits, space, brackets, double-quote are not clause."""
    assert uh.ls_util_is_clause(ord(char)) is False


# ---- ls_util_is_aword ----


@pytest.mark.parametrize(
    "word",
    [
        "hello",
        "world",
        "a",  # 1 char vowel
        "cat",
        "Banana",
    ],
)
def test_is_aword_accepts_real_words(word: str) -> None:
    """Words with letters and at least one vowel are aword."""
    assert uh.ls_util_is_aword(word) is True


@pytest.mark.parametrize(
    "word",
    [
        "",  # empty
        "bcdfg",  # all consonants (no vowel — 'y' counts as vowel in this table)
        "hello!",  # punctuation
        "hello world",  # space
        "abc123",  # digit
    ],
)
def test_is_aword_rejects_non_words(word: str) -> None:
    """Empty / non-alpha / vowelless inputs are rejected."""
    assert uh.ls_util_is_aword(word) is False


def test_is_aword_y_counts_as_vowel() -> None:
    """``y`` carries the CFEAT_vowel bit, so ``xyz`` qualifies as an aword."""
    assert uh.ls_util_is_aword("xyz") is True


def test_is_aword_bytes_accepted() -> None:
    """Function accepts bytes input too."""
    assert uh.ls_util_is_aword(b"hello") is True
    assert uh.ls_util_is_aword(b"bcdfg") is False


# ---- ls_util_is_ordinal ----


@pytest.mark.parametrize(
    ("word", "integer_end"),
    [
        (b"1st", 1),
        (b"2nd", 1),
        (b"3rd", 1),
        (b"4th", 1),
        (b"5th", 1),
        (b"9th", 1),
        (b"21st", 2),
        (b"22nd", 2),
        (b"23rd", 2),
        (b"24th", 2),
        (b"100th", 3),
        (b"101st", 3),
    ],
)
def test_is_ordinal_accepts_canonical_suffix(word: bytes, integer_end: int) -> None:
    """Standard English ordinal suffixes are accepted."""
    assert uh.ls_util_is_ordinal(word, integer_end) is True


@pytest.mark.parametrize(
    ("word", "integer_end"),
    [
        # Teens: 11th, 12th, 13th, 14th, ..., 19th — all use 'th' (treat unit as 0).
        (b"11th", 2),
        (b"12th", 2),
        (b"13th", 2),
        (b"14th", 2),
        (b"19th", 2),
        (b"111th", 3),
        (b"112th", 3),
        (b"113th", 3),
        (b"1011th", 4),
        (b"1012th", 4),
        (b"1013th", 4),
    ],
)
def test_is_ordinal_teens_use_th(word: bytes, integer_end: int) -> None:
    """11th/12th/13th and the like all use ``th`` because the tens digit is 1."""
    assert uh.ls_util_is_ordinal(word, integer_end) is True


@pytest.mark.parametrize(
    ("word", "integer_end"),
    [
        # Wrong suffix for the unit digit.
        (b"1nd", 1),  # 1 wants st, not nd
        (b"2st", 1),  # 2 wants nd, not st
        (b"3st", 1),  # 3 wants rd, not st
        (b"4st", 1),  # 4 wants th, not st
        (b"11st", 2),  # teen — must use th, not st
        (b"12nd", 2),  # teen — must use th
        (b"13rd", 2),  # teen — must use th
    ],
)
def test_is_ordinal_rejects_wrong_suffix(word: bytes, integer_end: int) -> None:
    """Suffix must match the unit digit (with teens treated specially)."""
    assert uh.ls_util_is_ordinal(word, integer_end) is False


def test_is_ordinal_rejects_fraction_quarter() -> None:
    """A trailing ``¼`` (0xBC) is not an ordinal."""
    assert uh.ls_util_is_ordinal(b"1\xbcth", 2) is False


def test_is_ordinal_rejects_fraction_half() -> None:
    """A trailing ``½`` (0xBD) is not an ordinal."""
    assert uh.ls_util_is_ordinal(b"1\xbdth", 2) is False


def test_is_ordinal_rejects_short_suffix() -> None:
    """Suffix shorter than 2 chars is rejected (no ``-st``/``-nd``/etc.)."""
    assert uh.ls_util_is_ordinal(b"1s", 1) is False
    assert uh.ls_util_is_ordinal(b"1", 1) is False


def test_is_ordinal_rejects_zero_integer() -> None:
    """An empty integer prefix is rejected."""
    assert uh.ls_util_is_ordinal(b"st", 0) is False
