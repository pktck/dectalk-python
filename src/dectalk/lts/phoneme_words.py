"""Canned phoneme strings for common words used by the LTS rules.

Translated from ``src/dapi/src/lts/l_us_con.c``. These are
pre-computed phoneme sequences for words that the number/date/title
rules need to insert directly — digits 0-9 ("zero" through "nine"),
their ordinal forms ("zeroth" through "ninth"), the month
abbreviations and full names, and assorted high-frequency words
("the", "of", "doctor", "saint", "street", "drive", "plus", "minus",
"half", "halves", "degree", and the spelled-out "oh" used for digit
runs like phone numbers).

Each entry is a :class:`bytes` of US phoneme codes (one byte per
phoneme), terminated by ``SIL`` (= 0). The codes are the same
numeric values defined in :class:`dectalk.include.phoneme_codes.USPhoneme`
plus the stress markers from ``l_com_ph.h`` — see the inline comment
on each entry for the decoded phoneme sequence.

The parity test in :mod:`tests.unit.test_lts_phoneme_words` re-parses
``l_us_con.c`` at test time and asserts every byte matches.
"""

from __future__ import annotations

from typing import Final

# Stress markers and SIL terminator (numeric values from l_com_ph.h).
_S1 = 103
_S2 = 102
_SIL = 0


# -- Common word phoneme strings -------------------------------------------

pdegree: Final[bytes] = bytes((48, 18, 50, 26, _S1, 1, _SIL))
"""``D IX G R (S1) IY SIL`` — "degree"."""

pminus: Final[bytes] = bytes((31, _S1, 7, 32, 17, 41, _SIL))
"""``M (S1) AY N AX S SIL`` — "minus"."""

pplus: Final[bytes] = bytes((45, 27, _S1, 9, 41, _SIL))
"""``P LL (S1) AH S SIL`` — "plus"."""

pstreet: Final[bytes] = bytes((41, 47, 26, _S2, 1, 47, _SIL))
"""``S T R (S2) IY T SIL`` — "street" (secondary stress)."""

psaint: Final[bytes] = bytes((41, 3, 32, 47, _SIL))
"""``S EY N T SIL`` — "saint"."""

pdoctor: Final[bytes] = bytes((48, 6, 49, 47, 15, _SIL))
"""``D AA K T RR SIL`` — "doctor"."""

pdrive: Final[bytes] = bytes((48, 26, _S1, 7, 38, _SIL))
"""``D R (S1) AY V SIL`` — "drive"."""

pOH: Final[bytes] = bytes((_S1, 11, _SIL))  # noqa: N816
"""``(S1) OW SIL`` — "oh" (used for digit runs like phone numbers).

The name preserves the C source's exact identifier; ``oh`` lowercase
would be misleading because ``pOH`` is meant to evoke the letter O."""


# -- Digit names: zero..nine -----------------------------------------------

p0: Final[bytes] = bytes((42, _S1, 1, 26, 11, _SIL))
"""``Z (S1) IY R OW SIL`` — "zero"."""

p1: Final[bytes] = bytes((24, _S1, 9, 32, _SIL))
"""``W (S1) AH N SIL`` — "one"."""

p2: Final[bytes] = bytes((47, _S1, 14, _SIL))
"""``T (S1) UW SIL`` — "two"."""

p3: Final[bytes] = bytes((39, 26, _S1, 1, _SIL))
"""``TH R (S1) IY SIL`` — "three"."""

p4: Final[bytes] = bytes((37, _S1, 22, _SIL))
"""``F (S1) OR SIL`` — "four"."""

p5: Final[bytes] = bytes((37, _S1, 7, 38, _SIL))
"""``F (S1) AY V SIL`` — "five"."""

p6: Final[bytes] = bytes((41, _S1, 2, 49, 41, _SIL))
"""``S (S1) IH K S SIL`` — "six"."""

p7: Final[bytes] = bytes((41, _S1, 4, 38, 17, 32, _SIL))
"""``S (S1) EH V AX N SIL`` — "seven"."""

p8: Final[bytes] = bytes((_S1, 3, 47, _SIL))
"""``(S1) EY T SIL`` — "eight"."""

p9: Final[bytes] = bytes((32, _S1, 7, 32, _SIL))
"""``N (S1) AY N SIL`` — "nine"."""


# -- Ordinals: zeroth..ninth -----------------------------------------------

p0th: Final[bytes] = bytes((42, _S1, 1, 26, 11, 39, _SIL))
"""``Z (S1) IY R OW TH SIL`` — "zeroth"."""

p1st: Final[bytes] = bytes((37, _S1, 15, 41, 47, _SIL))
"""``F (S1) RR S T SIL`` — "first"."""

p2nd: Final[bytes] = bytes((41, _S1, 4, 49, 17, 32, 48, _SIL))
"""``S (S1) EH K AX N D SIL`` — "second"."""

p3rd: Final[bytes] = bytes((39, _S1, 15, 48, _SIL))
"""``TH (S1) RR D SIL`` — "third"."""

p4th: Final[bytes] = bytes((37, _S1, 22, 39, _SIL))
"""``F (S1) OR TH SIL`` — "fourth"."""

p5th: Final[bytes] = bytes((37, _S1, 2, 37, 39, _SIL))
"""``F (S1) IH F TH SIL`` — "fifth"."""

p6th: Final[bytes] = bytes((41, _S1, 2, 49, 41, 39, _SIL))
"""``S (S1) IH K S TH SIL`` — "sixth"."""

p7th: Final[bytes] = bytes((41, _S1, 4, 38, 17, 32, 39, _SIL))
"""``S (S1) EH V AX N TH SIL`` — "seventh"."""

p8th: Final[bytes] = bytes((_S1, 3, 39, _SIL))
"""``(S1) EY TH SIL`` — "eighth"."""

p9th: Final[bytes] = bytes((32, _S1, 7, 32, 39, _SIL))
"""``N (S1) AY N TH SIL`` — "ninth"."""


# -- Halves, articles, prepositions ----------------------------------------

phalf: Final[bytes] = bytes((28, _S1, 5, 37, _SIL))
"""``HX (S1) AE F SIL`` — "half"."""

phalves: Final[bytes] = bytes((28, _S1, 5, 38, 42, _SIL))
"""``HX (S1) AE V Z SIL`` — "halves"."""

pthe: Final[bytes] = bytes((40, _S1, 17, _SIL))
"""``DH (S1) AX SIL`` — "the"."""

pof: Final[bytes] = bytes((_S1, 17, 38, _SIL))
"""``(S1) AX V SIL`` — "of"."""


# -- Lookup arrays ---------------------------------------------------------

pnumber: Final[tuple[bytes, ...]] = (p0, p1, p2, p3, p4, p5, p6, p7, p8, p9)
"""C ``pnumber[]`` table (implicit in usage; not declared as such in the
source but the digit-pronouncing loop indexes by ``digit - '0'``)."""

pordin: Final[tuple[bytes, ...]] = (p0th, p1st, p2nd, p3rd, p4th, p5th, p6th, p7th, p8th, p9th)
"""C ``pordin[]`` table — ordinal pronunciations indexed by units digit."""


# -- Month abbreviations (as ASCII strings) --------------------------------

m_jan: Final[bytes] = b"jan"
m_feb: Final[bytes] = b"feb"
m_mar: Final[bytes] = b"mar"
m_apr: Final[bytes] = b"apr"
m_may: Final[bytes] = b"may"
m_jun: Final[bytes] = b"jun"
m_jul: Final[bytes] = b"jul"
m_aug: Final[bytes] = b"aug"
m_sep: Final[bytes] = b"sep"
m_oct: Final[bytes] = b"oct"
m_nov: Final[bytes] = b"nov"
m_dec: Final[bytes] = b"dec"

months: Final[tuple[bytes, ...]] = (
    m_jan,
    m_feb,
    m_mar,
    m_apr,
    m_may,
    m_jun,
    m_jul,
    m_aug,
    m_sep,
    m_oct,
    m_nov,
    m_dec,
)
"""C ``months[]`` — month abbreviations indexed by ``month_number - 1``."""


__all__ = [
    "m_apr",
    "m_aug",
    "m_dec",
    "m_feb",
    "m_jan",
    "m_jul",
    "m_jun",
    "m_mar",
    "m_may",
    "m_nov",
    "m_oct",
    "m_sep",
    "months",
    "p0",
    "p0th",
    "p1",
    "p1st",
    "p2",
    "p2nd",
    "p3",
    "p3rd",
    "p4",
    "p4th",
    "p5",
    "p5th",
    "p6",
    "p6th",
    "p7",
    "p7th",
    "p8",
    "p8th",
    "p9",
    "p9th",
    "pOH",
    "pdegree",
    "pdoctor",
    "pdrive",
    "phalf",
    "phalves",
    "pminus",
    "pnumber",
    "pof",
    "pordin",
    "pplus",
    "psaint",
    "pstreet",
    "pthe",
]
