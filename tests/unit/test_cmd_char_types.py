"""Verify the CMD parser's char_types table matches cm_char.c.

Re-parses ``const unsigned char char_types[]`` from the C source
(resolving the MARK_* flag combinations from cm_defs.h) and asserts
every byte matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import char_types_table as ct

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/cmd/cm_char.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_FLAGS = {
    "MARK_null": ct.MARK_null,
    "MARK_vowel": ct.MARK_vowel,
    "MARK_upper": ct.MARK_upper,
    "MARK_cons": ct.MARK_cons,
    "MARK_digit": ct.MARK_digit,
    "MARK_non_alpha": ct.MARK_non_alpha,
    "MARK_punct": ct.MARK_punct,
    "MARK_clause": ct.MARK_clause,
    "MARK_space": ct.MARK_space,
}


def _parse_char_types() -> bytes:
    """Parse ``const unsigned char char_types[]`` into a bytes value."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+unsigned\s+char\s+char_types\[\]\s*=\s*\{(.+?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        v = 0
        for piece in re.split(r"\s*\+\s*", tok):
            p = piece.strip()
            if p == "0":
                continue
            if p in _FLAGS:
                v |= _FLAGS[p]
            else:
                raise ValueError(f"unknown token: {p!r}")
        out.append(v)
    return bytes(out)


def test_char_types_matches_c_source() -> None:
    """Every byte matches the C source initialiser."""
    expected = _parse_char_types()
    assert ct.char_types == expected


def test_char_types_has_258_entries() -> None:
    """C source: 256 byte values + 2 trailing safety-padding NULs."""
    expected = 258
    assert len(ct.char_types) == expected


@pytest.mark.parametrize("ch", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
def test_uppercase_letters_have_mark_upper(ch: str) -> None:
    """Each uppercase letter sets the MARK_upper bit."""
    assert ct.char_types[ord(ch)] & ct.MARK_upper


@pytest.mark.parametrize("ch", "aeiou")
def test_lowercase_vowels_have_mark_vowel(ch: str) -> None:
    """Lowercase ASCII vowels carry MARK_vowel."""
    assert ct.char_types[ord(ch)] & ct.MARK_vowel
    assert not (ct.char_types[ord(ch)] & ct.MARK_upper)


@pytest.mark.parametrize("ch", "AEIOU")
def test_uppercase_vowels_have_vowel_and_upper(ch: str) -> None:
    """Uppercase vowels carry both MARK_upper and MARK_vowel."""
    flags = ct.char_types[ord(ch)]
    assert flags & ct.MARK_upper
    assert flags & ct.MARK_vowel


@pytest.mark.parametrize("ch", "0123456789")
def test_digits_have_mark_digit(ch: str) -> None:
    assert ct.char_types[ord(ch)] & ct.MARK_digit


def test_whitespace_marker() -> None:
    """Space and LF carry MARK_space; tab is treated as a clause separator
    instead (the C source classifies HT as ``MARK_clause`` alone).
    """
    assert ct.char_types[ord(" ")] & ct.MARK_space
    assert ct.char_types[ord("\n")] & ct.MARK_space
    # Tab is MARK_clause, not MARK_space — matches the C source.
    assert ct.char_types[ord("\t")] == ct.MARK_clause


@pytest.mark.parametrize("ch", ".!?,;:")
def test_terminators_are_clause_punct(ch: str) -> None:
    """Sentence/clause delimiters carry both MARK_punct and MARK_clause."""
    flags = ct.char_types[ord(ch)]
    assert flags & ct.MARK_punct, f"{ch!r}: missing MARK_punct (got {flags:#04x})"
    assert flags & ct.MARK_clause, f"{ch!r}: missing MARK_clause"
