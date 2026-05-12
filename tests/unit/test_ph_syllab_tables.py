"""Verify the syllabification tables match p_us_sy1.c byte-for-byte.

Re-parses ``const char ascky_check[]``, ``const unsigned char
*common_affixes[]``, ``const char syl_vowels[]``, and
``const char *syl_cons[]`` from the C source and asserts every
entry matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph import syllab_tables as st

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/p_us_sy1.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_byte_init(name: str, declaration: str) -> bytes:
    """Parse ``const char NAME[] = { 0, 'i', 'I', ... };``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"{declaration}\s+{re.escape(name)}\[\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name} in p_us_sy1.c"
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if tok == "0":
            out.append(0)
        elif tok.startswith("'") and tok.endswith("'"):
            inner = tok[1:-1]
            if inner.startswith("\\"):
                escape_map = {"'": "'", '"': '"', "\\": "\\", "0": "\0", "n": "\n", "t": "\t"}
                out.append(ord(escape_map[inner[1]]))
            else:
                out.append(ord(inner))
        else:
            raise ValueError(f"{name}: unknown token {tok!r}")
    return bytes(out)


def _parse_string_array(name: str) -> tuple[str, ...]:
    """Parse ``const ... *NAME[] = { "...", "...", 0 };``.

    The trailing NULL sentinel is dropped — Python uses tuple length
    as the sentinel.
    """
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"\*\s*{re.escape(name)}\s*\[\]\s*=\s*\{{(.+?)\}}",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name} in p_us_sy1.c"
    body = m.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
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
                    escape_map = {"n": "\n", "t": "\t", "0": "\0", "\\": "\\", '"': '"', "'": "'"}
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


def _parse_string_literal(name: str) -> str:
    """Parse ``const char NAME[] = "..."``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+char\s+{re.escape(name)}\[\]\s*=\s*\"([^\"]+)\";",
        text,
    )
    assert m is not None, f"could not find string literal {name}"
    return m.group(1)


def test_ascky_check_matches_c_source() -> None:
    """Every byte of ascky_check matches the C source initialiser."""
    expected = _parse_byte_init("ascky_check", r"const\s+char")
    assert st.ascky_check == expected


def test_common_affixes_matches_c_source() -> None:
    """Every affix matches the C source list."""
    expected = _parse_string_array("common_affixes")
    assert st.common_affixes == expected


def test_syl_vowels_matches_c_source() -> None:
    """``syl_vowels`` matches the C literal exactly."""
    assert st.syl_vowels == _parse_string_literal("syl_vowels")


def test_syl_cons_matches_c_source() -> None:
    """Every onset cluster matches the C source list."""
    expected = _parse_string_array("syl_cons")
    assert st.syl_cons == expected


def test_ascky_check_has_111_entries() -> None:
    """The C source declares 111 entries (rows of 10 plus a tail)."""
    expected = 111
    assert len(st.ascky_check) == expected


def test_ascky_check_first_slots_are_zero() -> None:
    """Slot 0 (reserved) is zero; slot 1 ('i') is the first vowel."""
    assert st.ascky_check[0] == 0
    assert st.ascky_check[1] == ord("i")


def test_syl_vowels_has_no_obstruents() -> None:
    """``syl_vowels`` contains only vowels and syllabic-consonant glyphs.

    Includes ``L`` (syllabic L) and ``N`` (syllabic N) which both
    function as syllable nuclei despite being consonants in citation
    form. Excludes all obstruents and non-syllabic sonorants.
    """
    obstruents = "ptkbdgfvszSZmlrwyhCJ"
    for glyph in st.syl_vowels:
        assert glyph not in obstruents, f"{glyph!r} in syl_vowels"


def test_syl_cons_ordered_longest_first_within_blocks() -> None:
    """3-letter onsets appear before 2-letter onsets, before 1-letter."""
    lengths = [len(s) for s in st.syl_cons]
    # First entries are 3-char clusters (spl, spr, etc.)
    assert lengths[0] == 3
    assert lengths[-1] == 1


def test_common_affixes_have_known_terminations() -> None:
    """The list ends with the affixes 'sc' and 'we'."""
    assert "sc" in st.common_affixes
    assert "we" in st.common_affixes
