"""Phoneme-code bit layout and inline-command font codes.

Translated from ``src/dapi/src/include/cmd.h``. Constants here describe
two things:

1. **Phoneme-code bit layout.** Each 16-bit phoneme code packs three
   fields: a 5-bit *font* (high byte, identifies the language /
   control namespace), an 8-bit *value* (low byte, the phoneme index
   within the font), and a 2-bit *extra word count*. The masks /
   shifts (``PFONT``, ``PVALUE``, ``PSFONT``, ``PSNEXTRA``) and the
   font codes (``PFASCII``, ``PFCONTROL``) are used everywhere in the
   pipeline.

2. **Inline ``[:cmd val]`` commands.** Constants like ``RATE``,
   ``CPAUSE``, ``NEW_PARAM`` are font-encoded phoneme codes that the
   command parser inserts into the phoneme stream. They are decoded by
   downstream modules (LTS, PH, VTM) which act on them rather than
   synthesising audio.

The ``SPD_*`` constants are voice-parameter indices for the
``NEW_PARAM`` command (``[:dv sm 100]`` etc.). They index into the
voice-definition tables in ``klvdef.c``.

Numeric values match the C ``#define``s exactly because per-module
parity tests compare Python-emitted command/phoneme streams against
the C oracle's bytes; per-code parity is verified at test time by
parsing the C header.
"""

from __future__ import annotations

from typing import Final

# -- Phoneme-code bit layout (16-bit fields) ---------------------------------

PUNUSED: Final[int] = 0x8000
"""Reserved high bit. Always zero in well-formed phoneme codes."""

PNEXTRA: Final[int] = 0x6000
"""Mask: number of extra parameter words following this phoneme (0-3)."""

PFONT: Final[int] = 0x1F00
"""Mask: 5-bit font code (high byte minus the PUNUSED + PNEXTRA bits)."""

PVALUE: Final[int] = 0x00FF
"""Mask: 8-bit value within the font (the actual phoneme index)."""

PSNEXTRA: Final[int] = 13
"""Right-shift to bring PNEXTRA to bits 0-1."""

PSFONT: Final[int] = 8
"""Right-shift to bring PFONT to bits 0-4 (== bring an 8-bit font to PFONT)."""


# -- Font codes -------------------------------------------------------------

PFASCII: Final[int] = 0x00
"""ASCII / Multinational text font (plain text passes through)."""

PFCONTROL: Final[int] = 0x1F
"""Control-command font (used for the [:cmd val] commands below)."""


# -- Inline control commands (font = PFCONTROL) ------------------------------
# Each is ``(PFCONTROL << PSFONT) + offset``. The offset matches the C source.


def _ctrl(offset: int) -> int:
    return (PFCONTROL << PSFONT) + offset


RATE: Final[int] = _ctrl(0)  # [:rate <wpm>] speech rate
CPAUSE: Final[int] = _ctrl(1)  # comma pause
PPAUSE: Final[int] = _ctrl(2)  # period pause
LAST_VOICE: Final[int] = _ctrl(3)  # revert to previous voice
LTS_SYNC: Final[int] = _ctrl(4)  # LTS pipeline sync barrier
NEW_SPEAKER: Final[int] = _ctrl(5)  # change speaker (Perfect Paul, etc.)
NEW_PARAM: Final[int] = _ctrl(6)  # set a single voice parameter
SAVE: Final[int] = _ctrl(7)  # save current voice state
INDEX: Final[int] = _ctrl(8)  # insert an index marker
INDEX_REPLY: Final[int] = _ctrl(9)  # callback when reached
SYNC: Final[int] = _ctrl(10)  # sync barrier
BREATH_BREAK: Final[int] = _ctrl(11)  # explicit breath pause
KILL_TASK: Final[int] = _ctrl(12)  # terminate worker
FLUSH_SYNC: Final[int] = _ctrl(13)  # flush+sync barrier
PITCH_CHANGE: Final[int] = _ctrl(14)
LATIN: Final[int] = _ctrl(15)  # switch to Latin-American Spanish
PAPAUSE: Final[int] = _ctrl(16)  # paragraph pause
CNTRLK: Final[int] = _ctrl(17)
RESET: Final[int] = _ctrl(18)
INDEX_BOOKMARK: Final[int] = _ctrl(19)
INDEX_WORDPOS: Final[int] = _ctrl(20)
INDEX_START: Final[int] = _ctrl(21)
INDEX_STOP: Final[int] = _ctrl(22)
WORD_CLASS: Final[int] = _ctrl(23)
INDEX_SENTENCE: Final[int] = _ctrl(24)
INDEX_VOLUME: Final[int] = _ctrl(25)
INDEX_NOISE: Final[int] = _ctrl(26)
PREAMBLE: Final[int] = _ctrl(27)


# -- LTS_MODE second-parameter values ---------------------------------------

LTS_MODE_SET: Final[int] = 0
LTS_MODE_CLEAR: Final[int] = 1
LTS_MODE_ABS: Final[int] = 2
LTS_DIC_ALTERNATE: Final[int] = 3
LTS_ACNA_NAME: Final[int] = 4
LTS_DIC_PRIMARY: Final[int] = 5
LTS_DIC_NOUN: Final[int] = 6
LTS_DIC_VERB: Final[int] = 7
LTS_DIC_ADJECTIVE: Final[int] = 8
LTS_DIC_FUNCTION: Final[int] = 9
LTS_DIC_INTERJECTION: Final[int] = 10


# -- Flush state ------------------------------------------------------------

CMD_FLUSH_TOSS: Final[int] = 1
CMD_FLUSH_SYNC: Final[int] = 2
CMD_FLUSH_DONE: Final[int] = 3
CMD_SYNC_CHAR: Final[int] = 0xFF
CMD_SYNC_OUT: Final[int] = 0xFE


# -- Voice parameter indices (SPD_*) ----------------------------------------
# Used as the first extra word of a NEW_PARAM phoneme. The names map onto
# DECtalk's ``[:dv NAME val]`` settings: SPD_AP = average pitch, SPD_PR =
# pitch range, SPD_HS = head size, etc.

SPD_SEX: Final[int] = 0
SPD_SM: Final[int] = 1  # smoothness
SPD_AS: Final[int] = 2  # assertiveness
SPD_AP: Final[int] = 3  # average pitch
SPD_PR: Final[int] = 4  # pitch range
SPD_BR: Final[int] = 5  # breathiness
SPD_RI: Final[int] = 6  # richness
SPD_NF: Final[int] = 7  # nformants
SPD_LA: Final[int] = 8  # laryngalisation
SPD_HS: Final[int] = 9  # head size
SPD_F4: Final[int] = 10
SPD_B4: Final[int] = 11
SPD_F5: Final[int] = 12
SPD_B5: Final[int] = 13
SPD_P4: Final[int] = 14
SPD_P5: Final[int] = 15
SPD_GF: Final[int] = 16
SPD_GH: Final[int] = 17
SPD_GV: Final[int] = 18
SPD_GN: Final[int] = 19
SPD_G1: Final[int] = 20
SPD_G2: Final[int] = 21
SPD_G3: Final[int] = 22
SPD_G4: Final[int] = 23
SPD_LO: Final[int] = 24
SPD_FT: Final[int] = 25  # f0 flutter (was "FL")
SPD_FL: Final[int] = 25  # alias of SPD_FT
SPD_BF: Final[int] = 26
SPD_LX: Final[int] = 27  # was SPD_EF
SPD_QU: Final[int] = 28
SPD_HR: Final[int] = 29
SPD_SR: Final[int] = 30
SPD_AGO: Final[int] = 31  # avg glottal opening
SPD_AGVO: Final[int] = 32  # voiced obstruent
SPD_AGUO: Final[int] = 33  # unvoiced obstruent
SPD_UNVOW: Final[int] = 34
SPD_CHINK: Final[int] = 35
SPD_OQ: Final[int] = 36
SPD_OS: Final[int] = 37
SPD_NM: Final[int] = 38
SPDEF: Final[int] = 39  # total number of voice params


__all__ = [
    "BREATH_BREAK",
    "CMD_FLUSH_DONE",
    "CMD_FLUSH_SYNC",
    "CMD_FLUSH_TOSS",
    "CMD_SYNC_CHAR",
    "CMD_SYNC_OUT",
    "CNTRLK",
    "CPAUSE",
    "FLUSH_SYNC",
    "INDEX",
    "INDEX_BOOKMARK",
    "INDEX_NOISE",
    "INDEX_REPLY",
    "INDEX_SENTENCE",
    "INDEX_START",
    "INDEX_STOP",
    "INDEX_VOLUME",
    "INDEX_WORDPOS",
    "KILL_TASK",
    "LAST_VOICE",
    "LATIN",
    "LTS_ACNA_NAME",
    "LTS_DIC_ADJECTIVE",
    "LTS_DIC_ALTERNATE",
    "LTS_DIC_FUNCTION",
    "LTS_DIC_INTERJECTION",
    "LTS_DIC_NOUN",
    "LTS_DIC_PRIMARY",
    "LTS_DIC_VERB",
    "LTS_MODE_ABS",
    "LTS_MODE_CLEAR",
    "LTS_MODE_SET",
    "LTS_SYNC",
    "NEW_PARAM",
    "NEW_SPEAKER",
    "PAPAUSE",
    "PFASCII",
    "PFCONTROL",
    "PFONT",
    "PITCH_CHANGE",
    "PNEXTRA",
    "PPAUSE",
    "PREAMBLE",
    "PSFONT",
    "PSNEXTRA",
    "PUNUSED",
    "PVALUE",
    "RATE",
    "RESET",
    "SAVE",
    "SPDEF",
    "SPD_AGO",
    "SPD_AGUO",
    "SPD_AGVO",
    "SPD_AP",
    "SPD_AS",
    "SPD_B4",
    "SPD_B5",
    "SPD_BF",
    "SPD_BR",
    "SPD_CHINK",
    "SPD_F4",
    "SPD_F5",
    "SPD_FL",
    "SPD_FT",
    "SPD_G1",
    "SPD_G2",
    "SPD_G3",
    "SPD_G4",
    "SPD_GF",
    "SPD_GH",
    "SPD_GN",
    "SPD_GV",
    "SPD_HR",
    "SPD_HS",
    "SPD_LA",
    "SPD_LO",
    "SPD_LX",
    "SPD_NF",
    "SPD_NM",
    "SPD_OQ",
    "SPD_OS",
    "SPD_P4",
    "SPD_P5",
    "SPD_PR",
    "SPD_QU",
    "SPD_RI",
    "SPD_SEX",
    "SPD_SM",
    "SPD_SR",
    "SPD_UNVOW",
    "SYNC",
    "WORD_CLASS",
]
