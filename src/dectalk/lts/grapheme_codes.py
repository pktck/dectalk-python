"""LTS grapheme-code constants and helpers.

Translated from:

- ``src/dapi/src/lts/ls_defs.h`` — the G* grapheme code numbering
  (0 = end-mark, 1..26 = A..Z, 27 = GU digraph, 28 = QU digraph).
- ``src/dapi/src/lts/ls_util.c`` — ``ls_util_is_vowel()``.

The LTS rule engine works with grapheme codes (G* values) rather
than raw ASCII bytes: the kernel maps each input letter through
``ls_lower`` and then to its G-code before rule processing.
"""

from __future__ import annotations

from typing import Final

# Grapheme codes from ls_defs.h.

GEOS: Final[int] = 0  # End mark
GA: Final[int] = 1
GB: Final[int] = 2
GC: Final[int] = 3
GD: Final[int] = 4
GE: Final[int] = 5
GF: Final[int] = 6
GG: Final[int] = 7
GH: Final[int] = 8
GI: Final[int] = 9
GJ: Final[int] = 10
GK: Final[int] = 11
GL: Final[int] = 12
GM: Final[int] = 13
GN: Final[int] = 14
GO: Final[int] = 15
GP: Final[int] = 16
GQ: Final[int] = 17
GR: Final[int] = 18
GS: Final[int] = 19
GT: Final[int] = 20
GU: Final[int] = 21
GV: Final[int] = 22
GW: Final[int] = 23
GX: Final[int] = 24
GY: Final[int] = 25
GZ: Final[int] = 26
GGU: Final[int] = 27  # GU pseudo-consonant
GQU: Final[int] = 28  # QU pseudo-consonant
GQUOTE: Final[int] = 29  # "'", as in contractions
GMBOUND: Final[int] = 30  # "+", the morpheme boundary

# -- Lookup-table sizes / rule-LHS class codes ------------------------------

NGRAPH: Final[int] = 31
"""Number of grapheme codes in a rule-lookup table (= :data:`GMBOUND` + 1)."""

GRANGE: Final[int] = 31
"""Range marker — same numeric value as :data:`NGRAPH`."""

GDISJ: Final[int] = 32
"""Rule-LHS disjunction class code."""

GFEAT: Final[int] = 33
"""Rule-LHS feature class code."""

GWBOUND: Final[int] = 34
"""Rule-LHS word-boundary class code."""


def is_vowel(g: int) -> bool:
    """Return True if grapheme code ``g`` is an English vowel.

    Faithful translation of ``ls_util_is_vowel`` from
    ``src/dapi/src/lts/ls_util.c`` (ENGLISH branch). Vowels are
    A, E, I, O, U, and Y. The C function returns ``TRUE/FALSE``;
    Python returns ``True/False``.
    """
    return g in (GA, GE, GI, GO, GU, GY)


__all__ = [
    "GA",
    "GB",
    "GC",
    "GD",
    "GDISJ",
    "GE",
    "GEOS",
    "GF",
    "GFEAT",
    "GG",
    "GGU",
    "GH",
    "GI",
    "GJ",
    "GK",
    "GL",
    "GM",
    "GMBOUND",
    "GN",
    "GO",
    "GP",
    "GQ",
    "GQU",
    "GQUOTE",
    "GR",
    "GRANGE",
    "GS",
    "GT",
    "GU",
    "GV",
    "GW",
    "GWBOUND",
    "GX",
    "GY",
    "GZ",
    "NGRAPH",
    "is_vowel",
]
