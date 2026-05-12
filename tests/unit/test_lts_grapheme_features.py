"""Verify ``feats[]`` and ``pfeat[]`` match l_us_con.c byte-for-byte.

Re-parses the C ``const U16 feats[]`` and ``const U16 pfeat[]``
initialisers from ``l_us_con.c`` (resolving the symbolic F* / P* flag
combinations from ``ls_defs.h``) and asserts every value matches our
Python literals.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import grapheme_features as gf

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_FLAGS = {
    "FSEG": gf.FSEG, "FVOC": gf.FVOC, "FCONS": gf.FCONS, "FHIGH": gf.FHIGH,
    "FVOICE": gf.FVOICE, "FLIQ": gf.FLIQ, "FSIB": gf.FSIB,
    "FLTSVELAR": gf.FLTSVELAR, "FNAS": gf.FNAS, "FCOR": gf.FCOR,
    "FC": gf.FC, "FL": gf.FL, "FX": gf.FX, "FR": gf.FR, "FSYL": gf.FSYL,
    "PCONS": gf.PCONS, "PVOC": gf.PVOC, "PBOTH": gf.PBOTH,
    "PVOICE": gf.PVOICE, "PSIB": gf.PSIB, "POBS": gf.POBS, "PTD": gf.PTD,
    "PBACK": gf.PBACK,
}  # fmt: skip


def _parse_u16_table(name: str) -> tuple[int, ...]:
    """Parse ``const U16 NAME[] = { ... };`` from l_us_con.c."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(rf"const\s+U16\s+{re.escape(name)}\[\]\s*=\s*\{{(.*?)\}};", text, re.DOTALL)
    assert m is not None, f"could not find {name} in l_us_con.c"
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    values: list[int] = []
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
            elif re.fullmatch(r"\d+", p):
                v |= int(p)
            elif re.fullmatch(r"0x[0-9a-fA-F]+", p):
                v |= int(p, 16)
            else:
                raise ValueError(f"{name}: unknown token {p!r}")
        values.append(v)
    return tuple(values)


def test_feats_matches_c_source() -> None:
    """``feats`` matches the C ``const U16 feats[]`` declaration."""
    assert gf.feats == _parse_u16_table("feats")


def test_pfeat_matches_c_source() -> None:
    """``pfeat`` matches the C ``const U16 pfeat[]`` declaration."""
    assert gf.pfeat == _parse_u16_table("pfeat")


def test_feats_has_31_entries() -> None:
    """31 entries: end-mark + A-Z + GU + QU + apostrophe + plus."""
    expected = 31
    assert len(gf.feats) == expected


def test_pfeat_has_120_entries() -> None:
    """120 entries cover the US allophone + control-code range."""
    expected = 120
    assert len(gf.pfeat) == expected


def test_feats_letter_a_is_vocalic_syllabic() -> None:
    """Letter A (index 1) carries FSEG + FVOC + FSYL."""
    a = gf.feats[1]
    assert a & gf.FSEG
    assert a & gf.FVOC
    assert a & gf.FSYL


def test_feats_letter_b_is_voiced_consonant() -> None:
    """Letter B (index 2) carries FSEG + FCONS + FVOICE."""
    b = gf.feats[2]
    assert b & gf.FCONS
    assert b & gf.FVOICE
    assert not (b & gf.FVOC)


def test_feats_letter_y_is_segment_only() -> None:
    """Letter Y (index 25) is FSEG alone — dual vowel/consonant gets set
    dynamically by ``ls_rule_add_graph``."""
    y = gf.feats[25]
    assert y == gf.FSEG


def test_pfeat_silence_is_zero() -> None:
    """Index 0 (SIL) has no features."""
    assert gf.pfeat[0] == 0


def test_pfeat_vowels_are_pvoc_pvoice() -> None:
    """Pure vowels carry PVOC + PVOICE.

    Index 15 is RR (rhotic), tagged PBOTH+PVOICE — a "semi-vowel" that
    behaves like both a vowel and a consonant. Codes 19..23
    (IR/ER/AR/OR/UR) are untranslated allophones (zero features).
    """
    pvoc_pvoice = gf.PVOC | gf.PVOICE
    pure_vowel_indices = list(range(1, 15)) + list(range(16, 19))
    for i in pure_vowel_indices:
        assert gf.pfeat[i] == pvoc_pvoice, f"phoneme {i}"
    # RR (15) is "both" not pure vowel.
    assert gf.pfeat[15] == gf.PBOTH | gf.PVOICE


def test_pfeat_obstruents_have_pobs() -> None:
    """Stops and fricatives carry the POBS bit."""
    # F, V, TH, DH, S, Z, SH, ZH at indices 37-44
    for i in range(37, 45):
        assert gf.pfeat[i] & gf.POBS


def test_fgem_and_plong() -> None:
    """``FGEM`` (geminate flag) and ``PLONG`` (long vowel) match ls_defs.h."""
    assert gf.FGEM == 0x0200
    assert gf.PLONG == 0x0100


def test_symbol_table_sizes() -> None:
    """``NFSYM`` (16) and ``NPSYM`` (9) — sizes of the F/P symbol tables."""
    assert gf.NFSYM == 16
    assert gf.NPSYM == 9
