"""Unit tests for alphanumeric-cluster token shapes (issue #323).

Oracle-free counterpart to ``tests/parity/test_stage_lts_parity.py``'s
``test_mixed_alnum_split_matches_c``: exercises the
:mod:`dectalk.lts.token_shapes` helpers and the end-to-end phoneme stream
through the fast (non-``c_oracle``) lane. The pinned phoneme strings are
byte-identical to ``TextToSpeechConvertToPhonemes`` (verified in the parity
family); pinning them here guards the pure-Python path in CI without a C
build.
"""

from __future__ import annotations

import pytest

import dectalk
from dectalk.lts.token_shapes import (
    is_mixed_alnum,
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
        "IV",  # pure letters
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
)


@pytest.mark.parametrize(("text", "phonemes"), _PINNED, ids=[t for t, _ in _PINNED])
def test_end_to_end_phonemes(text: str, phonemes: str) -> None:
    """The full pipeline emits the pinned (oracle-identical) phoneme stream."""
    assert dectalk.text_to_dectalk_phonemes(text) == phonemes.encode("latin-1")
