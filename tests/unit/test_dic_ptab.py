"""Verify the ptab glyph→allophone mapping matches dic.c.

Re-parses the ``ENGLISH_US`` block of the ``PTAB ptab[]`` array from
``src/dapi/src/dic/dic.c`` and asserts every (glyph, code) pair
matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.dic import ptab as pt
from dectalk.include.phoneme_codes import USPhoneme

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/dic/dic.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_ptab_us() -> dict[str, int]:
    """Parse the ``#ifdef ENGLISH_US`` block of ``PTAB ptab[]``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(r"PTAB\s+ptab\[\]\s*=\s*\{(.+?)\};", text, re.DOTALL)
    assert m is not None
    body = m.group(1)
    us_match = re.search(r"#ifdef\s+ENGLISH_US\s*\n(.+?)\n\s*#endif", body, re.DOTALL)
    assert us_match is not None
    block = re.sub(r"/\*.*?\*/", "", us_match.group(1), flags=re.DOTALL)
    block = re.sub(r"//.*", "", block)
    us_names = {f"US_{m.name}": int(m) for m in USPhoneme}
    us_names["US_OR"] = int(USPhoneme.OR_)
    out: dict[str, int] = {}
    for rec in re.finditer(r"\{\s*'(\\?.|.)'\s*,\s*(US_\w+)\s*\}", block):
        glyph_raw = rec.group(1)
        if glyph_raw.startswith("\\"):
            escape_map = {"\\\\": "\\", "\\'": "'", '\\"': '"'}
            glyph = escape_map.get(glyph_raw, glyph_raw[1])
        else:
            glyph = glyph_raw
        out[glyph] = us_names[rec.group(2)]
    return out


def test_ptab_us_matches_c_source() -> None:
    """Every (glyph, code) pair matches the C source initialiser."""
    expected = _parse_ptab_us()
    assert pt.ptab_us == expected


def test_ptab_us_has_53_entries() -> None:
    """C source has 53 entries in the ENGLISH_US block."""
    expected = 53
    assert len(pt.ptab_us) == expected


def test_ptab_us_covers_all_vowel_glyphs() -> None:
    """The 18 vowel + r-coloured vowel glyphs are present."""
    vowel_glyphs = "eaiEAIOou^WYRc@U|x"  # 18 codes
    for g in vowel_glyphs:
        assert g in pt.ptab_us, f"missing vowel glyph {g!r}"


def test_ptab_us_covers_all_stops_fricatives() -> None:
    """The voiceless stops + fricatives are present."""
    consonant_glyphs = "ptkfTsSC"
    for g in consonant_glyphs:
        assert g in pt.ptab_us, f"missing glyph {g!r}"


def test_ptab_us_specific_mappings() -> None:
    """Spot-check a few specific glyph→code mappings."""
    assert pt.ptab_us["e"] == int(USPhoneme.EY)
    assert pt.ptab_us["@"] == int(USPhoneme.AE)
    assert pt.ptab_us["^"] == int(USPhoneme.AH)
    assert pt.ptab_us["x"] == int(USPhoneme.AX)
    assert pt.ptab_us["S"] == int(USPhoneme.SH)
    assert pt.ptab_us["Z"] == int(USPhoneme.ZH)
    assert pt.ptab_us["J"] == int(USPhoneme.JH)
    assert pt.ptab_us["G"] == int(USPhoneme.NX)
    assert pt.ptab_us["F"] == int(USPhoneme.DF)


def test_ptab_us_r_coloured_block() -> None:
    """The 5 r-coloured vowel glyphs are mapped."""
    r_coloured = {
        "B": USPhoneme.IR,
        "K": USPhoneme.ER,
        "P": USPhoneme.AR,
        "M": USPhoneme.OR_,
        "j": USPhoneme.UR,
    }
    for glyph, code in r_coloured.items():
        assert pt.ptab_us[glyph] == int(code)
