"""Verify each phoneme-word array in ``phoneme_words.py`` matches l_us_con.c.

For each named array we expose in :mod:`dectalk.lts.phoneme_words`,
re-parse the matching ``const unsigned char ...[] = { ... };`` from
``l_us_con.c`` at test time (resolving the symbolic ``US_*`` /
``S1`` / ``SIL`` constants to numbers) and assert the bytes match
exactly.

Skips when the C source is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    EXCLAIM,
    HAT_FALL,
    HAT_RF,
    HAT_RISE,
    HYPHEN,
    MBOUND,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    S1,
    S2,
    SBOUND,
    SEMPH,
    SPECIALWORD,
    VPSTART,
    WBOUND,
    USPhoneme,
)
from dectalk.lts import phoneme_words as pw

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# Symbolic-name resolution table: every name that can appear inside the
# byte-array initialisers we want to test.
_NAMES: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "S1": S1,
    "S2": S2,
    "SEMPH": SEMPH,
    "SIL": 0,
    "EOS": 0,
    "BLOCK_RULES": BLOCK_RULES,
    "HAT_RISE": HAT_RISE,
    "HAT_FALL": HAT_FALL,
    "HAT_RF": HAT_RF,
    "SBOUND": SBOUND,
    "MBOUND": MBOUND,
    "HYPHEN": HYPHEN,
    "WBOUND": WBOUND,
    "PPSTART": PPSTART,
    "VPSTART": VPSTART,
    "RELSTART": RELSTART,
    "COMMA": COMMA,
    "PERIOD": PERIOD,
    "QUEST": QUEST,
    "EXCLAIM": EXCLAIM,
    "NEW_PARAGRAPH": NEW_PARAGRAPH,
    "SPECIALWORD": SPECIALWORD,
}


def _parse_byte_array(name: str) -> bytes | None:
    """Parse ``const unsigned char NAME[] = { ... };`` from l_us_con.c."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+unsigned\s+char\s+{re.escape(name)}\s*\[\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    if not m:
        return None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if tok in _NAMES:
            out.append(_NAMES[tok])
        elif re.fullmatch(r"\d+", tok):
            out.append(int(tok))
        else:
            raise ValueError(f"{name}: unrecognised token {tok!r}")
    return bytes(out)


def _parse_string_array(name: str) -> bytes | None:
    """Parse ``const unsigned char NAME[] = "string";`` (no braces)."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+unsigned\s+char\s+{re.escape(name)}\s*\[\]\s*=\s*\"([^\"]*)\";",
        text,
    )
    return m.group(1).encode("latin-1") if m else None


# Every C-source name we translated as a small byte-array.
_BYTE_ARRAY_NAMES: tuple[str, ...] = (
    "pdegree", "pminus", "pplus", "pstreet", "psaint", "pdoctor",
    "pdrive", "pOH",
    # Digits and ordinals.
    "p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9",
    "p0th", "p1st", "p2nd", "p3rd", "p4th", "p5th", "p6th",
    "p7th", "p8th", "p9th",
    "up0", "up1", "up2", "up3", "up4", "up5", "up6", "up7", "up8", "up9",
    # Halves, articles, prepositions.
    "phalf", "phalves", "pthe", "pof",
    # Teens.
    "p10", "p11", "p12", "p13", "p14", "p15", "p16", "p17", "p18", "p19",
    # Tens.
    "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90",
    # Magnitudes.
    "phundred", "pthousand", "pmillion", "pbillion",
    "ptrillion", "pquadrillion",
    # Spoken month names.
    "pjan", "pfeb", "pmar", "papr", "pmay", "pjun",
    "pjul", "paug", "psep", "poct", "pnov", "pdec",
    # Currency and misc words.
    "pdollar", "pcent", "peuro", "ppound", "ppence",
    "ppercent", "ppoint", "pand", "pnone", "ptt2tp",
)  # fmt: skip


@pytest.mark.parametrize("name", _BYTE_ARRAY_NAMES)
def test_phoneme_array_matches_c(name: str) -> None:
    """Each named array's bytes match the C source initialiser."""
    c_bytes = _parse_byte_array(name)
    assert c_bytes is not None, f"could not find {name} in l_us_con.c"
    py_bytes = getattr(pw, name)
    assert py_bytes == c_bytes, f"{name}: Python={py_bytes!r}  C={c_bytes!r}"


# Month abbreviations are string literals (no braces).
_MONTH_NAMES: tuple[str, ...] = (
    "m_jan", "m_feb", "m_mar", "m_apr", "m_may", "m_jun",
    "m_jul", "m_aug", "m_sep", "m_oct", "m_nov", "m_dec",
)  # fmt: skip


@pytest.mark.parametrize("name", _MONTH_NAMES)
def test_month_abbreviation_matches_c(name: str) -> None:
    """Each ``m_*`` 3-letter month abbreviation matches the C source."""
    c_bytes = _parse_string_array(name)
    assert c_bytes is not None, f"could not find {name} in l_us_con.c"
    assert getattr(pw, name) == c_bytes


def test_months_array_order() -> None:
    """``months[]`` aligns with calendar order Jan..Dec."""
    expected = (pw.m_jan, pw.m_feb, pw.m_mar, pw.m_apr, pw.m_may, pw.m_jun,
                pw.m_jul, pw.m_aug, pw.m_sep, pw.m_oct, pw.m_nov, pw.m_dec)  # fmt: skip
    assert pw.months == expected


def test_pordin_aligns_with_digit_index() -> None:
    """``pordin[i]`` is the ordinal for digit ``i``."""
    assert pw.pordin[0] == pw.p0th
    assert pw.pordin[1] == pw.p1st
    assert pw.pordin[5] == pw.p5th
    assert pw.pordin[9] == pw.p9th


def test_pnumber_aligns_with_digit_index() -> None:
    """``pnumber[i]`` is the spoken word for digit ``i``."""
    digits = (pw.p0, pw.p1, pw.p2, pw.p3, pw.p4, pw.p5, pw.p6, pw.p7, pw.p8, pw.p9)
    for i, want in enumerate(digits):
        assert pw.pnumber[i] == want


def test_upunits_aligns_with_digit_index() -> None:
    """``upunits[i]`` is the unstressed pronunciation for digit ``i``."""
    digits = (pw.up0, pw.up1, pw.up2, pw.up3, pw.up4,
              pw.up5, pw.up6, pw.up7, pw.up8, pw.up9)  # fmt: skip
    for i, want in enumerate(digits):
        assert pw.upunits[i] == want


def test_pteens_aligns_with_teen_index() -> None:
    """``pteens[i]`` is the spoken word for the number ``10 + i``."""
    teens = (pw.p10, pw.p11, pw.p12, pw.p13, pw.p14,
             pw.p15, pw.p16, pw.p17, pw.p18, pw.p19)  # fmt: skip
    for i, want in enumerate(teens):
        assert pw.pteens[i] == want


def test_ptens_aligns_with_tens_index() -> None:
    """``ptens[i]`` is the spoken word for ``(i + 2) * 10`` (twenty..ninety)."""
    tens = (pw.p20, pw.p30, pw.p40, pw.p50, pw.p60, pw.p70, pw.p80, pw.p90)
    for i, want in enumerate(tens):
        assert pw.ptens[i] == want


def test_pmonths_aligns_with_month_index() -> None:
    """``pmonths[i]`` is the spoken word for month ``i + 1`` (Jan=0..Dec=11)."""
    spoken = (pw.pjan, pw.pfeb, pw.pmar, pw.papr, pw.pmay, pw.pjun,
              pw.pjul, pw.paug, pw.psep, pw.poct, pw.pnov, pw.pdec)  # fmt: skip
    for i, want in enumerate(spoken):
        assert pw.pmonths[i] == want


def test_punits_is_alias_of_pnumber() -> None:
    """``punits`` and ``pnumber`` are two C names for the same array."""
    assert pw.punits is pw.pnumber


def test_all_end_with_sil() -> None:
    """Every phoneme-word array ends with the SIL byte (0)."""
    for name in _BYTE_ARRAY_NAMES:
        arr = getattr(pw, name)
        assert arr[-1] == 0, f"{name} doesn't end with SIL"
