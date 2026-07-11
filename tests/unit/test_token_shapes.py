"""Unit tests for alphanumeric-cluster + roman-numeral token shapes.

Oracle-free counterpart to ``tests/parity/test_stage_lts_parity.py``'s
``test_mixed_alnum_split_matches_c`` / ``test_roman_numeral_ordinal_matches_c``
(issues #323 / #324): exercises the :mod:`dectalk.lts.token_shapes` helpers
and the end-to-end phoneme stream through the fast (non-``c_oracle``) lane.
The pinned phoneme strings are byte-identical to
``TextToSpeechConvertToPhonemes`` (verified in the parity family); pinning
them here guards the pure-Python path in CI without a C build.
"""

from __future__ import annotations

import pytest

import dectalk
from dectalk.lts.token_shapes import (
    ROMAN_ORDINALS,
    is_clean_cap_word,
    is_mixed_alnum,
    roman_ordinal_text,
    spell_form,
    split_alnum_runs,
)

# -- Helper: split_alnum_runs ---------------------------------------------


@pytest.mark.parametrize(
    ("token", "runs"),
    [
        ("A1", ["A", "1"]),
        ("3M", ["3", "M"]),
        ("B2B", ["B", "2", "B"]),
        ("42kg", ["42", "kg"]),
        ("2x", ["2", "x"]),
        ("1E10", ["1", "E", "10"]),
        ("6.02e23", ["6.02", "e", "23"]),  # '.' binds to its digit run
        ("abc123", ["abc", "123"]),
        ("M1", ["M", "1"]),
    ],
)
def test_split_alnum_runs(token: str, runs: list[str]) -> None:
    """Maximal letter/digit runs; the decimal point stays with its digits."""
    assert split_alnum_runs(token) == runs


# -- Helper: is_mixed_alnum -----------------------------------------------


@pytest.mark.parametrize("token", ["A1", "42kg", "6.02e23", "B2B", "1E10"])
def test_is_mixed_alnum_true(token: str) -> None:
    """Letter+digit clusters are split candidates."""
    assert is_mixed_alnum(token)


@pytest.mark.parametrize(
    "token",
    [
        "abc",  # letters only
        "123",  # digits only
        "3.14",  # digits + '.' only
        "10-20",  # contains '-', owned by the part-number lane
        "$5",  # currency, numeric lane
        "café2",  # non-ASCII falls through
        "IV",  # pure letters (roman lane)
    ],
)
def test_is_mixed_alnum_false(token: str) -> None:
    """Pure-alpha, pure-numeric, punctuated, and non-ASCII chunks fall through."""
    assert not is_mixed_alnum(token)


# -- Helper: spell_form ---------------------------------------------------


@pytest.mark.parametrize(
    ("run", "form"),
    [
        ("kg", "KG"),  # unpronounceable cluster -> spell (upper-cased)
        ("km", "KM"),
        ("lb", "LB"),
        ("cat", "cat"),  # pronounceable -> unchanged (spoken)
        ("A", "A"),  # single letter -> unchanged
        ("42", "42"),  # digit run -> unchanged
        ("mmxxvi", "mmxxvi"),  # >4 letters -> spoken, unchanged
    ],
)
def test_spell_form(run: str, form: str) -> None:
    """Only say-it-spelled clusters are upper-cased into the all-caps path."""
    assert spell_form(run) == form


# -- Helper: roman_ordinal_text -------------------------------------------


@pytest.mark.parametrize(
    ("token", "text"),
    [
        ("II", "the 2nd"),
        ("III", "the 3rd"),
        ("IV", "the 4th"),
        ("VIII", "the 8th"),
        ("XI", "the 11th"),
        ("XIV", "the 14th"),
        ("XVI", "the 16th"),
        ("XX", "the 20th"),
    ],
)
def test_roman_ordinal_text_table(token: str, text: str) -> None:
    """Table hits map to their ``the Nth`` value form."""
    assert roman_ordinal_text(token) == text


@pytest.mark.parametrize(
    "token",
    [
        "I",  # single letters excluded (commented out in the C table)
        "V",
        "X",
        "MM",  # value 2000 -> out of the 2..20 table
        "XL",  # 40, out of table
        "XXX",  # 30, out of table
        "MIX",  # real word, not a numeral
        "DID",
        "iv",  # lowercase never matches (table is upper-case)
    ],
)
def test_roman_ordinal_text_miss(token: str) -> None:
    """Non-table strings (single letters, >20, real words, lowercase) miss."""
    assert roman_ordinal_text(token) is None


def test_roman_table_is_two_to_twenty() -> None:
    """The table is exactly the 2..20 multi-letter numerals (I/V/X excluded)."""
    assert set(ROMAN_ORDINALS.values()) == set(range(2, 21)) - {5, 10}


# -- Helper: is_clean_cap_word --------------------------------------------


@pytest.mark.parametrize("chunk", ["Chapter", "Henry", "RED", "Hi", "(Chapter", "Book"])
def test_is_clean_cap_word_true(chunk: str) -> None:
    """A word whose first letter is upper-case, no trailing punctuation."""
    assert is_clean_cap_word(chunk)


@pytest.mark.parametrize(
    "chunk",
    [
        None,
        "chapter",  # lowercase first letter
        "Chapter,",  # trailing punctuation (whitespace no longer adjacent)
        "Chapter.",
        "A",  # single letter (U<1>A<+> needs >= 2 chars)
        "5",  # not a word
        "café",  # non-ASCII
    ],
)
def test_is_clean_cap_word_false(chunk: str | None) -> None:
    """Lowercase, punctuated, single-letter, and non-ASCII prefixes fail."""
    assert not is_clean_cap_word(chunk)


# -- End-to-end phoneme stream (byte-identical to the C oracle) -----------

# Pinned outputs are byte-for-byte what ``TextToSpeechConvertToPhonemes``
# emits (asserted in the parity family); pinning here exercises the
# pure-Python chunk-loop wiring without a C build.
_PINNED: tuple[tuple[str, str], ...] = (
    ("A1", "^ ax  w ' ahn "),
    ("3M", "thr ' iy  ' ehm "),
    ("B2B", "b ' iy  t ' uw  b ' iy"),
    ("42kg", "f ' ort iy  t ' uw  k ' ey  jh' iy"),
    ("2x", "t ' uw  ' ehk s "),
    ("1E10", "w ' ahn   ' iy  t ' ehn "),
    ("Chapter IV", "ch' aep t rr  dhax  f ' orth"),
    ("Henry VIII", "hx' ehn r iy  dhax  ' eyth"),
    ("Book XIV", "b ' uhk   dhax  f ' or* t ' iyn th"),
    ("Apple II", "' aep el  dhax  s ' ehk axn d "),
)


@pytest.mark.parametrize(("text", "phonemes"), _PINNED, ids=[t for t, _ in _PINNED])
def test_end_to_end_phonemes(text: str, phonemes: str) -> None:
    """The full pipeline emits the pinned (oracle-identical) phoneme stream."""
    assert dectalk.text_to_dectalk_phonemes(text) == phonemes.encode("latin-1")


# -- Roman numerals are NOT wordized without a capitalised prefix ---------

# "the fourth" ordinal tail produced by the triggered ``Chapter IV`` — its
# absence proves a context was left un-wordized (the numeral read as a word).
_FOURTH_ORDINAL = b"f ' orth"


@pytest.mark.parametrize(
    "text",
    [
        "IV",  # bare
        "IV dogs",  # clause-initial, following word
        "the IV",  # lowercase preceding word
        "a IV bag",
        "chapter IV",  # lowercase carrier (both must be capitalised)
        "Chapter, IV",  # comma, not whitespace, before the numeral
        "Chapter. IV",
        "(IV)",  # leading punctuation on the numeral
    ],
)
def test_roman_not_wordized_without_cap_prefix(text: str) -> None:
    """Bare / lowercase / punctuation-separated numerals stay ordinary words.

    The load-bearing #324 guard: only a clean capitalised-word prefix
    triggers the ordinal rewrite, so none of these contexts may produce the
    "the fourth" ordinal.
    """
    assert _FOURTH_ORDINAL not in dectalk.text_to_dectalk_phonemes(text)


@pytest.mark.parametrize(
    "text",
    ["Chapter IV", "Hi IV", "Cat IV dog", "RED IV", "Mix IV things"],
)
def test_roman_wordized_with_cap_prefix(text: str) -> None:
    """A capitalised-word prefix does trigger the ordinal rewrite."""
    assert _FOURTH_ORDINAL in dectalk.text_to_dectalk_phonemes(text)


@pytest.mark.parametrize(
    "text",
    ["mix", "did", "civil", "mill", "Big MIX", "The DID", "Windows XP"],
)
def test_roman_lookalike_words_not_misparsed(text: str) -> None:
    """Real words that look roman-ish are never rewritten to an ordinal."""
    out = dectalk.text_to_dectalk_phonemes(text)
    # None of these carry a "the <ordinal>" rewrite; assert the numeral
    # table's ordinal markers are absent.
    assert b"dhax  f ' orth" not in out
    assert b"dhax  s ' ehk axn d" not in out  # "the second" (II)
