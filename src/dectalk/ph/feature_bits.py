"""Sentence-structure feature bits from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h``. These bit-flags
get ORed together into ``pDph_t->sentstruc[i]``, one entry per
phoneme in the clause, encoding per-segment metadata the PH
intonation / timing / allophone modules read back:

- **Stress level** (low 2 bits — :data:`FSTRESS` mask):
  :data:`FNOSTRESS`, :data:`FSTRESS_1`, :data:`FSTRESS_2`,
  :data:`FEMPHASIS`.
- **Word context** (bits 2): :data:`FWINITC` (word-initial
  consonant) / :data:`FOPEN_SYL` (vowel in open syllable).
- **Syllable count** (mask :data:`FTYPESYL`, shift
  :data:`FSYL_SHIFT`): :data:`FMONOSYL` / :data:`FBISYL` /
  :data:`FTRISYL` / :data:`FMULTISYL`.
- **Syllable position**: :data:`FFIRSTSYL` / :data:`FMEDIALSYL`
  / :data:`FFINALSYL`.
- **Following boundary** (mask :data:`FBOUNDARY`):
  :data:`FNO_BOUNDARY`, :data:`FSYBNEXT`, :data:`FMBNEXT`,
  :data:`FWBNEXT`, :data:`FPPNEXT`, :data:`FVPNEXT`,
  :data:`FRELNEXT`, :data:`FCBNEXT`, :data:`FPERNEXT`,
  :data:`FQUENEXT`, :data:`FEXCLNEXT`.
- **Sentence-end flag**: :data:`FSENTENDS`.
- **Hat-rise bookkeeping**: :data:`FHAT_BEGINS`,
  :data:`FHAT_ENDS`.
- **Other flags**: :data:`FDUMMY_VOWEL`, :data:`FBLOCK`,
  :data:`FDOUBLECONS`, :data:`FSBOUND`, :data:`FCODA`,
  :data:`FISBOUND`, :data:`F_TIME_RISE`, :data:`FOTHER`,
  :data:`FOTHER_SHIFT`.

All values are extracted faithfully from the C source's
``#define`` lines (the C uses octal — ``03`` = 3, ``040`` = 32,
``0400`` = 256, etc.; the Python port uses hex for readability).
"""

from __future__ import annotations

from typing import Final

# -- Stress-level field (bits 0-1) -----------------------------------------

FSTRESS: Final[int] = 0o3
"""Mask for the stress level field (low 2 bits)."""

FNOSTRESS: Final[int] = 0
"""Stress = none (unstressed)."""

FSTRESS_1: Final[int] = 0o1
"""Stress = primary (the syllable marked with ``[1]``)."""

FSTRESS_2: Final[int] = 0o2
"""Stress = secondary."""

FEMPHASIS: Final[int] = 0o3
"""Stress = emphatic (overrides primary for marked words)."""

# -- Word context flag (bit 2) ---------------------------------------------

FWINITC: Final[int] = 0o4
"""Word-initial consonant."""

FOPEN_SYL: Final[int] = 0o4
"""Vowel in an open syllable (alias — same bit as :data:`FWINITC`,
the C source uses both names depending on whether the entry is for a
consonant or a vowel)."""

# -- Syllable count (bits 3-4, shift = FSYL_SHIFT) -------------------------

FSYL_SHIFT: Final[int] = 3

FMONOSYL: Final[int] = 0o0
"""Word has 1 syllable."""

FBISYL: Final[int] = 0o10
"""Word has 2 syllables."""

FTRISYL: Final[int] = 0o20
"""Word has 3 syllables."""

FMULTISYL: Final[int] = 0o30
"""Word has more than 3 syllables."""

# -- Syllable position (alias of count bits) -------------------------------

FFIRSTSYL: Final[int] = 0o10
"""Current syllable is the word's first syllable."""

FMEDIALSYL: Final[int] = 0o20
"""Current syllable is a medial (non-first / non-final) syllable."""

FFINALSYL: Final[int] = 0o30
"""Current syllable is the word's final syllable."""

FTYPESYL: Final[int] = 0o30
"""Mask for the syllable type / position field."""

# -- Following boundary (bits 5-8) -----------------------------------------

FBOUNDARY: Final[int] = 0o740
"""Mask for the following-boundary field."""

FNO_BOUNDARY: Final[int] = 0o0
"""No boundary follows this segment."""

FSYBNEXT: Final[int] = 0o40
"""Next boundary is a syllable boundary."""

FMBNEXT: Final[int] = 0o100
"""Next boundary is a morpheme boundary."""

FWBNEXT: Final[int] = 0o140
"""Next boundary is a word boundary."""

FPPNEXT: Final[int] = 0o200
"""Next boundary is a prepositional-phrase boundary."""

FVPNEXT: Final[int] = 0o240
"""Next boundary is a verb-phrase boundary."""

FRELNEXT: Final[int] = 0o300
"""Next boundary is a relative-clause boundary."""

FCBNEXT: Final[int] = 0o340
"""Next boundary is a comma (clause break)."""

FPERNEXT: Final[int] = 0o400
"""Next boundary is a period."""

FQUENEXT: Final[int] = 0o440
"""Next boundary is a question mark."""

FEXCLNEXT: Final[int] = 0o500
"""Next boundary is an exclamation mark."""

# -- Sentence-end flag -----------------------------------------------------

FSENTENDS: Final[int] = 0o400
"""Next boundary is a sentence end (same value as :data:`FPERNEXT`;
distinguished only by context)."""

# -- Hat-rise / hat-fall markers -------------------------------------------

FHAT_BEGINS: Final[int] = 0o1000
"""Hat rise starts on this segment."""

FHAT_ENDS: Final[int] = 0o2000
"""Hat fall ends on this segment."""

# -- Other flags -----------------------------------------------------------

FDUMMY_VOWEL: Final[int] = 0o4000
"""Dummy vowel — don't count its plosive release gesture."""

FBLOCK: Final[int] = 0o20000
"""Block allophone substitutions on this segment."""

FDOUBLECONS: Final[int] = 0x40000
"""Doubled-consonant marker (German build)."""

FHYPHENATED: Final[int] = 0o10000
"""Hyphenated word marker (from viphdefs.h)."""

# -- Hat-roof position codes (used by intonation engine) --------------------

AT_BOTTOM_OF_HAT: Final[int] = 1
"""Current syllable is at the start of the hat (declination floor)."""

AT_TOP_OF_HAT: Final[int] = 2
"""Current syllable is at the peak of the hat (declination ceiling)."""

# -- Feature-count cap ------------------------------------------------------

PHO_FEA_MAX: Final[int] = 14
"""Maximum number of features in the per-phoneme struc[] structure."""

# -- Sound class flags -----------------------------------------------------

FSBOUND: Final[int] = 0o1000000
"""Segment is at a syllable boundary."""

FCODA: Final[int] = 0o2000000
"""Segment is in the syllable coda."""

FISBOUND: Final[int] = 0o3000000
"""Mask covering both :data:`FSBOUND` and :data:`FCODA`."""

F_TIME_RISE: Final[int] = 0o1000000
"""Special-cased timing rise marker (same value as :data:`FSBOUND`,
distinguished by context)."""

# -- Composite OTHER mask --------------------------------------------------

FOTHER: Final[int] = FSBOUND | FCODA | FBLOCK | FWINITC
"""Composite mask covering the four "other" flags (used in shifts)."""

FOTHER_SHIFT: Final[int] = 12
"""Shift used to pack the FOTHER bits into a smaller field."""

__all__ = [
    "AT_BOTTOM_OF_HAT",
    "AT_TOP_OF_HAT",
    "FBISYL",
    "FBLOCK",
    "FBOUNDARY",
    "FCBNEXT",
    "FCODA",
    "FDOUBLECONS",
    "FDUMMY_VOWEL",
    "FEMPHASIS",
    "FEXCLNEXT",
    "FFINALSYL",
    "FFIRSTSYL",
    "FHAT_BEGINS",
    "FHAT_ENDS",
    "FHYPHENATED",
    "FISBOUND",
    "FMBNEXT",
    "FMEDIALSYL",
    "FMONOSYL",
    "FMULTISYL",
    "FNOSTRESS",
    "FNO_BOUNDARY",
    "FOPEN_SYL",
    "FOTHER",
    "FOTHER_SHIFT",
    "FPERNEXT",
    "FPPNEXT",
    "FQUENEXT",
    "FRELNEXT",
    "FSBOUND",
    "FSENTENDS",
    "FSTRESS",
    "FSTRESS_1",
    "FSTRESS_2",
    "FSYBNEXT",
    "FSYL_SHIFT",
    "FTRISYL",
    "FTYPESYL",
    "FVPNEXT",
    "FWBNEXT",
    "FWINITC",
    "F_TIME_RISE",
    "PHO_FEA_MAX",
]
