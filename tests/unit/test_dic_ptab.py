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
from dectalk.include import phoneme_codes as pc
from dectalk.include.phoneme_codes import USPhoneme

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/dic/dic.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_ptab_us() -> dict[str, int]:
    """Parse the ``#ifdef ENGLISH_US`` block plus the language-common tail.

    The C ``PTAB ptab[]`` initialiser has a language-specific block
    (wrapped in ``#ifdef ENGLISH_US``) followed by 12 punctuation
    glyphs that map to control codes (COMMA, WBOUND, S1, …) and apply
    to every language.
    """
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(r"PTAB\s+ptab\[\]\s*=\s*\{(.+?)\};", text, re.DOTALL)
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    # Slice US block + the trailing language-common entries (the last
    # `#endif` before the closing brace is followed by the common tail).
    us_match = re.search(r"#ifdef\s+ENGLISH_US\s*\n(.+?)\n\s*#endif", body, re.DOTALL)
    assert us_match is not None
    us_block = us_match.group(1)
    # Find everything after the FINAL `#endif` — that's the common tail.
    tail_start = body.rfind("#endif")
    common_tail = body[tail_start + len("#endif") :]
    combined_block = us_block + "\n" + common_tail
    us_names = {f"US_{enum_member.name}": int(enum_member) for enum_member in USPhoneme}
    us_names["US_OR"] = int(USPhoneme.OR_)
    # Control / boundary names.
    code_names: dict[str, int] = {
        **us_names,
        "COMMA": pc.COMMA,
        "WBOUND": pc.WBOUND,
        "S1": pc.S1,
        "S2": pc.S2,
        "SEMPH": pc.SEMPH,
        "HYPHEN": pc.HYPHEN,
        "PPSTART": pc.PPSTART,
        "VPSTART": pc.VPSTART,
        "MBOUND": pc.MBOUND,
        "BLOCK_RULES": pc.BLOCK_RULES,
        "SBOUND": pc.SBOUND,
    }
    out: dict[str, int] = {}
    char_re = r"\\.|[^'\\]"
    for rec in re.finditer(
        rf"\{{\s*(?:'(?P<glyph>{char_re})'|(?P<hex>0x[0-9a-fA-F]+))\s*,\s*(?P<name>\w+)\s*\}}",
        combined_block,
    ):
        if rec.group("glyph") is not None:
            glyph_raw = rec.group("glyph")
            if glyph_raw.startswith("\\"):
                escape_map = {"\\\\": "\\", "\\'": "'", '\\"': '"', "\\t": "\t", "\\n": "\n"}
                glyph = escape_map.get(glyph_raw, glyph_raw[1])
            else:
                glyph = glyph_raw
        else:
            # Hex char literal — Latin-1 byte.
            glyph = chr(int(rec.group("hex"), 16))
        name = rec.group("name")
        if name not in code_names:
            continue  # Skip language-other entries that leak through.
        out[glyph] = code_names[name]
    return out


def test_ptab_us_matches_c_source() -> None:
    """Every (glyph, code) pair matches the C source initialiser."""
    expected = _parse_ptab_us()
    assert pt.ptab_us == expected


def test_ptab_us_has_65_entries() -> None:
    """53 ENGLISH_US glyphs + 12 language-common punctuation glyphs."""
    expected = 65
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
