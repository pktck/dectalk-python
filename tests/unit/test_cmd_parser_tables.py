"""Verify the parser tables match par_char.c byte-for-byte.

Re-parses ``parser_char_types`` and ``par_illegal_cluster`` from
``src/dapi/src/cmd/par_char.c`` (resolving the TYPE_* flag
combinations from par_def.h) and asserts every entry matches.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import parser_tables as pt

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/cmd/par_char.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_FLAGS = {
    "TYPE_null": pt.TYPE_null,
    "TYPE_digit": pt.TYPE_digit,
    "TYPE_upper": pt.TYPE_upper,
    "TYPE_lower": pt.TYPE_lower,
    "TYPE_alpha": pt.TYPE_alpha,
    "TYPE_any_char": pt.TYPE_any_char,
    "TYPE_white": pt.TYPE_white,
    "TYPE_punct": pt.TYPE_punct,
    "TYPE_non_alpha": pt.TYPE_non_alpha,
    "TYPE_vowel": pt.TYPE_vowel,
    "TYPE_consonant": pt.TYPE_consonant,
    "TYPE_number": pt.TYPE_number,
    "TYPE_clause": pt.TYPE_clause,
    "TYPE_alpha_num": pt.TYPE_alpha_num,
    "TYPE_vowel_non_y": pt.TYPE_vowel_non_y,
    "TYPE_punct_some": pt.TYPE_punct_some,
    "TYPE_quot": pt.TYPE_quot,
}


def _parse_parser_char_types() -> tuple[int, ...]:
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+unsigned\s+short\s+parser_char_types\[\]\s*=\s*\{(.+?)\};",
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
        for piece in re.split(r"\s*\|\s*", tok):
            p = piece.strip()
            if p == "0":
                continue
            v |= _FLAGS[p]
        out.append(v)
    return tuple(out)


def _parse_illegal_cluster() -> tuple[str, ...]:
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"\*\s*par_illegal_cluster\s*\[\]\s*=\s*\{(.+?)\}",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == '"':
            j = i + 1
            parts: list[str] = []
            while j < len(body) and body[j] != '"':
                if body[j] == "\\" and j + 1 < len(body):
                    escape_map = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                    parts.append(escape_map.get(body[j + 1], body[j + 1]))
                    j += 2
                else:
                    parts.append(body[j])
                    j += 1
            out.append("".join(parts))
            i = j + 1
        else:
            i += 1
    return tuple(out)


def test_parser_char_types_matches_c() -> None:
    """Every entry of parser_char_types matches the C source."""
    expected = _parse_parser_char_types()
    assert pt.parser_char_types == expected


def test_parser_char_types_has_257_entries() -> None:
    """256 bytes + 1 trailing 0 sentinel."""
    expected = 257
    assert len(pt.parser_char_types) == expected


def test_par_illegal_cluster_matches_c() -> None:
    """``par_illegal_cluster`` matches the C list."""
    expected = _parse_illegal_cluster()
    assert pt.par_illegal_cluster == expected


def test_parser_char_types_entries_fit_in_u16() -> None:
    """No entry exceeds 16 bits — matches the C ``unsigned short``."""
    max_u16 = 0xFFFF
    for i, v in enumerate(pt.parser_char_types):
        assert 0 <= v <= max_u16, f"index {i}: {v:#x}"


@pytest.mark.parametrize("ch", "0123456789")
def test_digits_have_type_digit(ch: str) -> None:
    assert pt.parser_char_types[ord(ch)] & pt.TYPE_digit


@pytest.mark.parametrize("ch", "abcdefghijklmnopqrstuvwxyz")
def test_lowercase_letters_have_type_lower(ch: str) -> None:
    assert pt.parser_char_types[ord(ch)] & pt.TYPE_lower


@pytest.mark.parametrize("ch", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
def test_uppercase_letters_have_type_upper(ch: str) -> None:
    assert pt.parser_char_types[ord(ch)] & pt.TYPE_upper


@pytest.mark.parametrize("ch", "AEIOU")
def test_uppercase_vowels_have_type_vowel(ch: str) -> None:
    assert pt.parser_char_types[ord(ch)] & pt.TYPE_vowel
    assert pt.parser_char_types[ord(ch)] & pt.TYPE_vowel_non_y


def test_lowercase_y_is_vowel_but_not_vowel_non_y() -> None:
    """The Y vowel quirk: 'y' tags TYPE_vowel but not TYPE_vowel_non_y."""
    flags = pt.parser_char_types[ord("y")]
    assert flags & pt.TYPE_vowel
    assert not (flags & pt.TYPE_vowel_non_y)


def test_par_illegal_cluster_count() -> None:
    """The C source declares 14 illegal-cluster patterns."""
    expected = 14
    assert len(pt.par_illegal_cluster) == expected


def test_par_illegal_cluster_known_pairs() -> None:
    """Spot-check: the well-known onset clusters appear."""
    for pair in ("bn", "bt", "db", "mb", "mc"):
        assert pair in pt.par_illegal_cluster
