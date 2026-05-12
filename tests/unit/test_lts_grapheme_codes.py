"""Verify grapheme codes + ``is_vowel`` match the C source.

Re-parses every ``#define G* N`` directive from ls_defs.h and asserts
each Python constant matches. Also exercises ``is_vowel`` over the
6-vowel set and the 21-consonant set to confirm parity with
``ls_util_is_vowel`` from ls_util.c.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import grapheme_codes as gc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/ls_defs.h")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_grapheme_defines() -> dict[str, int]:
    """Parse the first occurrence of each ``#define G* N`` (G followed by uppercase letters)."""
    text = _C_FILE.read_text(encoding="latin-1")
    out: dict[str, int] = {}
    for m in re.finditer(r"^#define\s+(G[A-Z]+)\s+(\d+)\b", text, re.MULTILINE):
        name = m.group(1)
        if name not in out:  # take first occurrence only
            out[name] = int(m.group(2))
    return out


@pytest.mark.parametrize(
    "name",
    [
        "GEOS",
        "GA",
        "GB",
        "GC",
        "GD",
        "GE",
        "GF",
        "GG",
        "GH",
        "GI",
        "GJ",
        "GK",
        "GL",
        "GM",
        "GN",
        "GO",
        "GP",
        "GQ",
        "GR",
        "GS",
        "GT",
        "GU",
        "GV",
        "GW",
        "GX",
        "GY",
        "GZ",
        "GGU",
        "GQU",
    ],
)
def test_grapheme_code_matches_c(name: str) -> None:
    """Each G* constant matches the C source's #define."""
    defs = _parse_grapheme_defines()
    assert name in defs, f"missing #define {name}"
    assert getattr(gc, name) == defs[name]


def test_letters_are_1_to_26() -> None:
    """G followed by an uppercase letter L maps to L's position in the alphabet."""
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=1):
        assert getattr(gc, f"G{letter}") == i


def test_geos_is_zero() -> None:
    """End-mark code is 0."""
    assert gc.GEOS == 0


def test_digraph_codes() -> None:
    """The two pseudo-consonant digraph codes follow Z."""
    expected_ggu = 27
    expected_gqu = 28
    assert expected_ggu == gc.GGU
    assert expected_gqu == gc.GQU


@pytest.mark.parametrize("vowel", "AEIOUY")
def test_is_vowel_true_for_vowels(vowel: str) -> None:
    """A, E, I, O, U, Y are vowels in the English branch."""
    code = getattr(gc, f"G{vowel}")
    assert gc.is_vowel(code) is True


@pytest.mark.parametrize("consonant", "BCDFGHJKLMNPQRSTVWXZ")
def test_is_vowel_false_for_consonants(consonant: str) -> None:
    """All non-A/E/I/O/U/Y letters are non-vowels."""
    code = getattr(gc, f"G{consonant}")
    assert gc.is_vowel(code) is False


def test_is_vowel_geos_false() -> None:
    """The end-mark code is not a vowel."""
    assert gc.is_vowel(gc.GEOS) is False


def test_is_vowel_digraphs_false() -> None:
    """The GU/QU digraphs are pseudo-consonants — not vowels."""
    assert gc.is_vowel(gc.GGU) is False
    assert gc.is_vowel(gc.GQU) is False
