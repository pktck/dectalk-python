"""DCS_* inline-command dispatch codes from esc.h.

Translated from ``src/dapi/src/include/esc.h`` lines 179-275 —
the numeric codes the inline-command parser
(``cm_cmd_parse``) dispatches against when matching ``[:cmd]``
strings. Each ``DCS_*`` constant is the ``esc_value`` field of a
``dtpc_command`` entry in :data:`dectalk.cmd.command_table.
DtpcCommand`.

Some codes are OR'd with :data:`SKIP_ESCAPE` (0x8000) — these
are voice-name shortcuts (``[:np]`` etc.) that the parser refuses
to re-encode as escape sequences on output. Everything else fits
in the low 15 bits :data:`ESCAPE_CODE`.
"""

from __future__ import annotations

from typing import Final

SKIP_ESCAPE: Final[int] = 0x8000
"""Bit set on codes the parser refuses to re-encode as ESC sequences."""

ESCAPE_CODE: Final[int] = 0x7FFF
"""Mask for the low-15-bit DCS code (everything below :data:`SKIP_ESCAPE`)."""

# -- Standalone command codes ----------------------------------------------

DCS_RIGHT_BRACKET: Final[int] = 0
"""Code for the closing ``]`` of an inline command (no-op)."""

DCS_RATE: Final[int] = 200
"""``[:rate <wpm>]`` — set speaking rate in words/min."""

DCS_NAME: Final[int] = 201
"""``[:name <voice>]`` — select voice by name string."""

DCS_COMMA: Final[int] = 202
"""``[:comma <ms>]`` / ``[:cp <ms>]`` — adjust comma pause."""

DCS_PERIOD: Final[int] = 203
"""``[:period <ms>]`` / ``[:pp <ms>]`` — adjust period pause."""

DCS_PUNCT: Final[int] = 204
"""``[:punctuation <mode>]`` — set punctuation handling."""

# -- Voice-name shortcuts (DCS_NAME_*) -------------------------------------

DCS_NAME_PAUL: Final[int] = SKIP_ESCAPE + 0
"""``[:np]`` — Perfect Paul shortcut."""

DCS_NAME_BETTY: Final[int] = SKIP_ESCAPE + 1
"""``[:nb]`` — Beautiful Betty shortcut."""

DCS_NAME_HARRY: Final[int] = SKIP_ESCAPE + 2
"""``[:nh]`` — Huge Harry shortcut."""

DCS_NAME_FRANK: Final[int] = SKIP_ESCAPE + 3
"""``[:nf]`` — Frail Frank shortcut."""

DCS_NAME_DENNIS: Final[int] = SKIP_ESCAPE + 4
"""``[:nd]`` — Doctor Dennis shortcut."""

DCS_NAME_THE_KID: Final[int] = SKIP_ESCAPE + 5
"""``[:nk]`` — Kit the Kid shortcut."""

DCS_NAME_URSULA: Final[int] = SKIP_ESCAPE + 6
"""``[:nu]`` — Uppity Ursula shortcut."""

DCS_NAME_RITA: Final[int] = SKIP_ESCAPE + 7
"""``[:nr]`` — Rough Rita shortcut."""

DCS_NAME_WILLY: Final[int] = SKIP_ESCAPE + 8
"""``[:nw]`` — Whispery Willy shortcut."""

DCS_NAME_CHRIS: Final[int] = SKIP_ESCAPE + 9
"""``[:nc]`` — Crafty Chris shortcut (HLSYN / post-V43 builds only)."""

DCS_NAME_VAL: Final[int] = SKIP_ESCAPE + 10
"""``[:nv]`` — Variable Val shortcut."""

DCS_LATIN: Final[int] = SKIP_ESCAPE + 11
"""``[:latin]`` — switch to Latin character set."""

# -- Volume control ---------------------------------------------------------

DCS_VOLUME_SET: Final[int] = 100
DCS_VOLUME_UP: Final[int] = 101
DCS_VOLUME_DOWN: Final[int] = 102

# Linux/Win volume LR-split (replaces VOLUME_TONE 103 from MSDOS).
DCS_VOLUME_LSET: Final[int] = 103
DCS_VOLUME_LUP: Final[int] = 104
DCS_VOLUME_LDOWN: Final[int] = 105
DCS_VOLUME_RSET: Final[int] = 106
DCS_VOLUME_RUP: Final[int] = 107
DCS_VOLUME_RDOWN: Final[int] = 108
DCS_VOLUME_SSET: Final[int] = 109
DCS_VOLUME_ATT: Final[int] = 110

VOLUME_SET: Final[int] = 0
VOLUME_UP: Final[int] = 1
VOLUME_DOWN: Final[int] = 2

# -- Index-marker codes (BATS#404 inline-command parser table) -------------

DCS_INDEX: Final[int] = 20
DCS_INDEX_REPLY: Final[int] = 21
DCS_INDEX_QUERY: Final[int] = 22
DCS_INDEX_PAUSE: Final[int] = 23
"""Placeholder slot — not actually used."""
DCS_INDEX_BOOKMARK: Final[int] = 24
DCS_INDEX_WORDPOS: Final[int] = 25
DCS_INDEX_START: Final[int] = 26
DCS_INDEX_STOP: Final[int] = 27
DCS_INDEX_SENTENCE: Final[int] = 28
DCS_INDEX_VOLUME: Final[int] = 29
"""Hack: piggybacked on the index pipe to change volume mid-clause."""
DCS_INDEX_NOISE: Final[int] = 30
"""Hack: piggybacked on the index pipe to toggle noise on/off."""

# -- Engine-control codes ---------------------------------------------------

DCS_ERROR: Final[int] = 300
DCS_MODE: Final[int] = 80
DCS_LOG: Final[int] = 81
DCS_SAY: Final[int] = 82
DCS_PHONEME: Final[int] = 600
DCS_PAUSE: Final[int] = 12
DCS_RESUME: Final[int] = 13
DCS_SYNC: Final[int] = 11
DCS_FLUSH: Final[int] = 10
DCS_ENABLE: Final[int] = 14

# -- Tone / phone-line codes ------------------------------------------------

DCS_DIAL: Final[int] = 400
DCS_TONE: Final[int] = 401
DCS_TIMEOUT: Final[int] = 402

# -- High-level commands ----------------------------------------------------

DCS_DEFINE: Final[int] = 500
DCS_PRONOUNCE: Final[int] = 700
DCS_DIGITIZED: Final[int] = 800
DCS_LANGUAGE: Final[int] = 900
DCS_REMOVE: Final[int] = 1000
DCS_TYPE: Final[int] = 1100
DCS_STRESS: Final[int] = 1200
DCS_BREAK: Final[int] = 1300
DCS_CPU_RATE: Final[int] = 1400
DCS_CODE_PAGE: Final[int] = 1500

# -- "Special" codes that all map to 0 (handled inline) --------------------

DCS_DEBUG: Final[int] = 0
DCS_SKIP: Final[int] = 0
DCS_GENDER: Final[int] = 0
DCS_DBGV: Final[int] = 0

# -- Output type codes ------------------------------------------------------

TEXT_OUTPUT: Final[int] = 0
ESCAPE_OUTPUT: Final[int] = 1
SPC_INDEX_PAUSE: Final[int] = 2


__all__ = [
    "DCS_BREAK",
    "DCS_CODE_PAGE",
    "DCS_COMMA",
    "DCS_CPU_RATE",
    "DCS_DBGV",
    "DCS_DEBUG",
    "DCS_DEFINE",
    "DCS_DIAL",
    "DCS_DIGITIZED",
    "DCS_ENABLE",
    "DCS_ERROR",
    "DCS_FLUSH",
    "DCS_GENDER",
    "DCS_INDEX",
    "DCS_INDEX_BOOKMARK",
    "DCS_INDEX_NOISE",
    "DCS_INDEX_PAUSE",
    "DCS_INDEX_QUERY",
    "DCS_INDEX_REPLY",
    "DCS_INDEX_SENTENCE",
    "DCS_INDEX_START",
    "DCS_INDEX_STOP",
    "DCS_INDEX_VOLUME",
    "DCS_INDEX_WORDPOS",
    "DCS_LANGUAGE",
    "DCS_LATIN",
    "DCS_LOG",
    "DCS_MODE",
    "DCS_NAME",
    "DCS_NAME_BETTY",
    "DCS_NAME_CHRIS",
    "DCS_NAME_DENNIS",
    "DCS_NAME_FRANK",
    "DCS_NAME_HARRY",
    "DCS_NAME_PAUL",
    "DCS_NAME_RITA",
    "DCS_NAME_THE_KID",
    "DCS_NAME_URSULA",
    "DCS_NAME_VAL",
    "DCS_NAME_WILLY",
    "DCS_PAUSE",
    "DCS_PERIOD",
    "DCS_PHONEME",
    "DCS_PRONOUNCE",
    "DCS_PUNCT",
    "DCS_RATE",
    "DCS_REMOVE",
    "DCS_RESUME",
    "DCS_RIGHT_BRACKET",
    "DCS_SAY",
    "DCS_SKIP",
    "DCS_STRESS",
    "DCS_SYNC",
    "DCS_TIMEOUT",
    "DCS_TONE",
    "DCS_TYPE",
    "DCS_VOLUME_ATT",
    "DCS_VOLUME_DOWN",
    "DCS_VOLUME_LDOWN",
    "DCS_VOLUME_LSET",
    "DCS_VOLUME_LUP",
    "DCS_VOLUME_RDOWN",
    "DCS_VOLUME_RSET",
    "DCS_VOLUME_RUP",
    "DCS_VOLUME_SET",
    "DCS_VOLUME_SSET",
    "DCS_VOLUME_UP",
    "ESCAPE_CODE",
    "ESCAPE_OUTPUT",
    "SKIP_ESCAPE",
    "SPC_INDEX_PAUSE",
    "TEXT_OUTPUT",
    "VOLUME_DOWN",
    "VOLUME_SET",
    "VOLUME_UP",
]
