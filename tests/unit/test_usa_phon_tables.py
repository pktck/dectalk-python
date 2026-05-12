"""Verify ``usa_ascky_rev`` matches the C source byte-for-byte.

Re-parses the ``const unsigned int usa_ascky_rev[]`` initialiser
from ``src/dapi/src/include/usa_phon.tab`` (resolving PUSA() macros
and the PITCH_CHANGE / NULL_ASCKY constants) and asserts every
entry matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include import usa_phon_tables as upt
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
    S3,
    SBOUND,
    SEMPH,
    VPSTART,
    WBOUND,
    USPhoneme,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/include/usa_phon.tab"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)

# Constants needed to evaluate the C initialiser.
_PFUSA = 0x1E
_PFCONTROL = 0x1F
_PSFONT = 8
_PITCH_CHANGE = (_PFCONTROL << _PSFONT) + 14
_NULL_ASCKY = 0xFFFF


_NAMES: dict[str, int] = {
    "BLOCK_RULES": BLOCK_RULES,
    "COMMA": COMMA,
    "EXCLAIM": EXCLAIM,
    "HAT_FALL": HAT_FALL,
    "HAT_RF": HAT_RF,
    "HAT_RISE": HAT_RISE,
    "HYPHEN": HYPHEN,
    "MBOUND": MBOUND,
    "NEW_PARAGRAPH": NEW_PARAGRAPH,
    "PERIOD": PERIOD,
    "PPSTART": PPSTART,
    "QUEST": QUEST,
    "RELSTART": RELSTART,
    "S1": S1,
    "S2": S2,
    "S3": S3,
    "SBOUND": SBOUND,
    "SEMPH": SEMPH,
    "SIL": 0,
    "VPSTART": VPSTART,
    "WBOUND": WBOUND,
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
}


def _parse_usa_ascky_rev() -> tuple[int, ...]:
    """Parse ``const unsigned int usa_ascky_rev[] = { ... };``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+unsigned\s+int\s+usa_ascky_rev\[\]\s*=\s*\{(.+?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)

    def repl_pusa(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if inner not in _NAMES:
            raise ValueError(f"PUSA arg unknown: {inner}")
        return str((_PFUSA << _PSFONT) | _NAMES[inner])

    body = re.sub(r"PUSA\s*\(\s*([\w_]+)\s*\)", repl_pusa, body)
    out: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if re.fullmatch(r"\d+", tok):
            out.append(int(tok))
        elif tok == "NULL_ASCKY":
            out.append(_NULL_ASCKY)
        elif tok == "PITCH_CHANGE":
            out.append(_PITCH_CHANGE)
        elif tok in _NAMES:
            out.append(_NAMES[tok])
        else:
            raise ValueError(f"unknown token: {tok!r}")
    return tuple(out)


def test_usa_ascky_rev_matches_c() -> None:
    """Every entry matches the C source initialiser."""
    expected = _parse_usa_ascky_rev()
    assert upt.usa_ascky_rev == expected


def test_usa_ascky_rev_has_128_entries() -> None:
    """Covers ASCII bytes 0..127."""
    expected = 128
    assert len(upt.usa_ascky_rev) == expected


def test_null_ascky_constant() -> None:
    """``NULL_ASCKY`` matches the C macro."""
    assert upt.NULL_ASCKY == _NULL_ASCKY


def test_lowercase_letters_map_to_us_phonemes() -> None:
    """Letters 'a'..'z' that are phonemes (font 0x1E) yield font-encoded codes."""
    font_mask = 0x1F00
    pfusa_shifted = _PFUSA << _PSFONT
    # 'a' = US_AE, 'b' = US_B, etc. — spot-check a few.
    for byte in (ord("a"), ord("e"), ord("i"), ord("o")):
        v = upt.usa_ascky_rev[byte]
        assert v != upt.NULL_ASCKY
        assert v & font_mask == pfusa_shifted


def test_space_maps_to_wbound() -> None:
    """SPACE (0x20) → PUSA(WBOUND)."""
    expected = (_PFUSA << _PSFONT) | WBOUND
    assert upt.usa_ascky_rev[0x20] == expected


def test_tab_maps_to_wbound() -> None:
    """TAB (0x09) → PUSA(WBOUND)."""
    expected = (_PFUSA << _PSFONT) | WBOUND
    assert upt.usa_ascky_rev[0x09] == expected


def test_apostrophe_maps_to_s1() -> None:
    """Apostrophe (0x27) → PUSA(S1) (primary stress)."""
    expected = (_PFUSA << _PSFONT) | S1
    assert upt.usa_ascky_rev[0x27] == expected
