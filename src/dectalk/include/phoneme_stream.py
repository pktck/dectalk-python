"""Parser for the C library's phoneme-stream output format.

``TextToSpeechConvertToPhonemes`` (exposed on Linux by the
``0001-expose-convert-to-phonemes-on-linux`` C-source patch) writes a
sequence of fixed-width 2-byte ASCII slots into the caller's buffer.
Each slot maps to a single phoneme code from ``l_all_ph.h`` (US
allophones 0-70) or ``l_com_ph.h`` (stress + boundary control codes
100-122). Codes 57-70 (unused extension slots) and 100 (BLOCK_RULES)
are filtered out before output by ``lts/ls_util.c:1666`` — they should
never appear in a real stream.

The 2-byte ASCII mappings come from ``src/dapi/src/include/usa_phon.tab``
(``const unsigned char usa_arpa[]``). The mapping is translated once
into Python; the test in ``tests/unit/test_phoneme_stream_parser.py``
parses the C table at test time and asserts every entry matches.

Output format (verified by reading ``lts/ls_util.c``):

- Slot ``"hx"`` → :data:`USPhoneme.HX` (allophone)
- Slot ``"w "`` (letter + space) → :data:`USPhoneme.W` (1-char allophone)
- Slot ``"' "`` → ``S1`` primary stress
- Slot ``"  "`` (two spaces) → ``WBOUND`` word boundary
- Slot ``", "`` → ``COMMA`` end of clause

A complete render of ``"hello world"`` therefore comes back as 11
slots — 9 allophones (HX AX LL OW W RR LL D) plus two stress markers
and one word boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.include.phoneme_codes import (
    COMMA,
    DOUBLCONS,
    EXCLAIM,
    HAT_FALL,
    HAT_RF,
    HAT_RISE,
    HYPHEN,
    LINKRWORD,
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
    SPECIALWORD,
    VPSTART,
    WBOUND,
    USPhoneme,
)

# 2-byte ASCII slot -> phoneme code. Derived from `usa_arpa[]` in
# src/dapi/src/include/usa_phon.tab; see the test for a byte-level
# parity check.
SLOT_TO_CODE: Final[dict[bytes, int]] = {
    # US allophones 0..56 (codes 57-70 are filtered before output).
    b"_ ": USPhoneme.SIL,
    b"iy": USPhoneme.IY,
    b"ih": USPhoneme.IH,
    b"ey": USPhoneme.EY,
    b"eh": USPhoneme.EH,
    b"ae": USPhoneme.AE,
    b"aa": USPhoneme.AA,
    b"ay": USPhoneme.AY,
    b"aw": USPhoneme.AW,
    b"ah": USPhoneme.AH,
    b"ao": USPhoneme.AO,
    b"ow": USPhoneme.OW,
    b"oy": USPhoneme.OY,
    b"uh": USPhoneme.UH,
    b"uw": USPhoneme.UW,
    b"rr": USPhoneme.RR,
    b"yu": USPhoneme.YU,
    b"ax": USPhoneme.AX,
    b"ix": USPhoneme.IX,
    b"ir": USPhoneme.IR,
    b"er": USPhoneme.ER,
    b"ar": USPhoneme.AR,
    b"or": USPhoneme.OR_,
    b"ur": USPhoneme.UR,
    b"w ": USPhoneme.W,
    b"yx": USPhoneme.Y,  # NB: US_Y is encoded as "yx", not "y "
    b"r ": USPhoneme.R,
    b"ll": USPhoneme.LL,
    b"hx": USPhoneme.HX,
    b"rx": USPhoneme.RX,
    b"lx": USPhoneme.LX,
    b"m ": USPhoneme.M,
    b"n ": USPhoneme.N,
    b"nx": USPhoneme.NX,
    b"el": USPhoneme.EL,
    b"dz": USPhoneme.DZ,
    b"en": USPhoneme.EN,
    b"f ": USPhoneme.F,
    b"v ": USPhoneme.V,
    b"th": USPhoneme.TH,
    b"dh": USPhoneme.DH,
    b"s ": USPhoneme.S,
    b"z ": USPhoneme.Z,
    b"sh": USPhoneme.SH,
    b"zh": USPhoneme.ZH,
    b"p ": USPhoneme.P,
    b"b ": USPhoneme.B,
    b"t ": USPhoneme.T,
    b"d ": USPhoneme.D,
    b"k ": USPhoneme.K,
    b"g ": USPhoneme.G,
    b"dx": USPhoneme.DX,
    b"tx": USPhoneme.TX,
    b"q ": USPhoneme.Q,
    b"ch": USPhoneme.CH,
    b"jh": USPhoneme.JH,
    b"df": USPhoneme.DF,
    # Stress and prosody control codes 101..122 from l_com_ph.h.
    b"= ": S3,
    b"` ": S2,
    b"' ": S1,
    b'" ': SEMPH,
    b"/ ": HAT_RISE,
    b"\\ ": HAT_FALL,
    b"/\\": HAT_RF,
    b"- ": SBOUND,
    b"* ": MBOUND,
    b"# ": HYPHEN,
    b"  ": WBOUND,  # two spaces
    b"( ": PPSTART,
    b") ": VPSTART,
    b"; ": RELSTART,
    b", ": COMMA,
    b". ": PERIOD,
    b"? ": QUEST,
    b"! ": EXCLAIM,
    b"+ ": NEW_PARAGRAPH,
    b"^ ": SPECIALWORD,
    b"& ": LINKRWORD,
    b"> ": DOUBLCONS,
}
"""2-byte ASCII slot from the C output → numeric phoneme code (0..122)."""


# Friendly names for stress/boundary codes (allophones use ``USPhoneme.name``).
_CONTROL_NAMES: Final[dict[int, str]] = {
    S3: "S3", S2: "S2", S1: "S1", SEMPH: "SEMPH",
    HAT_RISE: "HAT_RISE", HAT_FALL: "HAT_FALL", HAT_RF: "HAT_RF",
    SBOUND: "SBOUND", MBOUND: "MBOUND", HYPHEN: "HYPHEN",
    WBOUND: "WBOUND", PPSTART: "PPSTART", VPSTART: "VPSTART",
    RELSTART: "RELSTART", COMMA: "COMMA", PERIOD: "PERIOD",
    QUEST: "QUEST", EXCLAIM: "EXCLAIM", NEW_PARAGRAPH: "NEW_PARAGRAPH",
    SPECIALWORD: "SPECIALWORD", LINKRWORD: "LINKRWORD",
    DOUBLCONS: "DOUBLCONS",
}  # fmt: skip


_SLOT_WIDTH: Final[int] = 2


class PhonemeStreamParseError(ValueError):
    """Raised when the C output contains an unrecognised 2-byte slot."""


@dataclass(frozen=True, slots=True)
class PhonemeToken:
    """One parsed phoneme or control code from the C library's output.

    Attributes:
        code: Numeric phoneme code, matching the C #defines exactly.
            Values 0..56 are US allophones (see :class:`USPhoneme`);
            values 101..122 are stress/boundary control codes from
            ``l_com_ph.h``.
        name: Human-readable symbol (``"AX"``, ``"S1"``, ``"WBOUND"``).
    """

    code: int
    name: str


def parse_phoneme_stream(raw: bytes) -> list[PhonemeToken]:
    """Parse the C library's phoneme buffer into a list of tokens.

    ``raw`` is the bytes returned by ``CAPI.convert_to_phonemes``
    (already stripped of the NUL terminator).

    Raises :class:`PhonemeStreamParseError` if the length is odd or any
    2-byte slot is not in the mapping table.
    """
    if len(raw) % _SLOT_WIDTH != 0:
        raise PhonemeStreamParseError(
            f"phoneme stream length {len(raw)} is not a multiple of the slot width {_SLOT_WIDTH}"
        )
    tokens: list[PhonemeToken] = []
    for i in range(0, len(raw), _SLOT_WIDTH):
        slot = raw[i : i + _SLOT_WIDTH]
        if slot not in SLOT_TO_CODE:
            raise PhonemeStreamParseError(
                f"unrecognised 2-byte slot {slot!r} at offset {i} in stream {raw!r}"
            )
        code = SLOT_TO_CODE[slot]
        name = _CONTROL_NAMES[code] if code in _CONTROL_NAMES else USPhoneme(code).name
        tokens.append(PhonemeToken(code=int(code), name=name))
    return tokens


def format_phoneme_tokens(tokens: list[PhonemeToken]) -> str:
    """Render parsed tokens as a space-separated human-readable string."""
    return " ".join(t.name for t in tokens)


__all__ = [
    "PhonemeStreamParseError",
    "PhonemeToken",
    "format_phoneme_tokens",
    "parse_phoneme_stream",
]
