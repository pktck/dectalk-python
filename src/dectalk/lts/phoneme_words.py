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


# -- Unstressed digit names (up0..up9) ------------------------------------
# Used when reading digit-runs like serial numbers, phone numbers, etc.,
# where each digit is unstressed (no S1 marker). These are the
# pronunciations the C source picks via ``upunits[digit]``.

up0: Final[bytes] = bytes((42, _S1, 1, 26, 11, _SIL))  # "zero" (still stressed)
up1: Final[bytes] = bytes((24, 9, 32, _SIL))  # "one" unstressed
up2: Final[bytes] = bytes((47, 14, _SIL))  # "two"
up3: Final[bytes] = bytes((39, 26, 1, _SIL))  # "three"
up4: Final[bytes] = bytes((37, 22, _SIL))  # "four"
up5: Final[bytes] = bytes((37, 7, 38, _SIL))  # "five"
up6: Final[bytes] = bytes((41, 2, 49, 41, _SIL))  # "six"
up7: Final[bytes] = bytes((41, 4, 38, 17, 32, _SIL))  # "seven"
up8: Final[bytes] = bytes((3, 47, _SIL))  # "eight"
up9: Final[bytes] = bytes((32, 7, 32, _SIL))  # "nine"

upunits: Final[tuple[bytes, ...]] = (up0, up1, up2, up3, up4, up5, up6, up7, up8, up9)
"""C ``upunits[]`` — unstressed digit pronunciations indexed 0..9."""

punits: Final[tuple[bytes, ...]] = pnumber
"""C ``punits[]`` — alias of :data:`pnumber` (stressed digits)."""


# -- Teens (p10..p19) ------------------------------------------------------
# Each one is "X-teen" rendered as a multi-phoneme string. The byte 109
# is MBOUND (morpheme boundary, from l_com_ph.h) marking the "teen" suffix.

_MBOUND = 109

p10: Final[bytes] = bytes((47, _S1, 4, 32, _SIL))  # "ten"
p11: Final[bytes] = bytes((17, 27, _S1, 4, 38, 17, 32, _SIL))  # "eleven"
p12: Final[bytes] = bytes((47, 24, _S1, 4, 27, 38, _SIL))  # "twelve"
p13: Final[bytes] = bytes((39, _S1, 15, _MBOUND, 47, _S1, 1, 32, _SIL))  # "thir-teen"
p14: Final[bytes] = bytes((37, _S1, 22, _MBOUND, 47, _S1, 1, 32, _SIL))  # "four-teen"
p15: Final[bytes] = bytes((37, _S1, 2, 37, _MBOUND, 47, _S1, 1, 32, _SIL))  # "fif-teen"
p16: Final[bytes] = bytes((41, _S1, 2, 49, 41, _MBOUND, 47, _S1, 1, 32, _SIL))  # "six-teen"
p17: Final[bytes] = bytes((41, _S1, 4, 38, 17, 32, _MBOUND, 47, _S1, 1, 32, _SIL))  # "seven-teen"
p18: Final[bytes] = bytes((_S1, 3, _MBOUND, 47, _S1, 1, 32, _SIL))  # "eigh-teen"
p19: Final[bytes] = bytes((32, _S1, 7, 32, _MBOUND, 47, _S1, 1, 32, _SIL))  # "nine-teen"

pteens: Final[tuple[bytes, ...]] = (p10, p11, p12, p13, p14, p15, p16, p17, p18, p19)
"""C ``pteens[]`` — teen pronunciations indexed by ``number - 10``."""


# -- Tens (p20, p30, ..., p90) ---------------------------------------------
# These end in "-ty" — phonemes 47 (T) + 1 (IY).

p20: Final[bytes] = bytes((47, 24, _S1, 4, 32, 47, 1, _SIL))  # "twenty"
p30: Final[bytes] = bytes((39, _S1, 15, 47, 1, _SIL))  # "thirty"
p40: Final[bytes] = bytes((37, _S1, 22, 47, 1, _SIL))  # "forty"
p50: Final[bytes] = bytes((37, _S1, 2, 37, 47, 1, _SIL))  # "fifty"
p60: Final[bytes] = bytes((41, _S1, 2, 49, 41, 47, 1, _SIL))  # "sixty"
p70: Final[bytes] = bytes((41, _S1, 4, 38, 17, 32, 47, 1, _SIL))  # "seventy"
p80: Final[bytes] = bytes((_S1, 3, 47, 1, _SIL))  # "eighty"
p90: Final[bytes] = bytes((32, _S1, 7, 32, 47, 1, _SIL))  # "ninety"

ptens: Final[tuple[bytes, ...]] = (p20, p30, p40, p50, p60, p70, p80, p90)
"""C ``ptens[]`` — tens pronunciations indexed ``(number // 10) - 2``."""


# -- Number magnitudes -----------------------------------------------------

phundred: Final[bytes] = bytes((28, _S1, 9, 32, 48, 26, 17, 48, _SIL))
"""``HX (S1) AH N D R AX D SIL`` — "hundred"."""

pthousand: Final[bytes] = bytes((39, _S1, 8, 42, 17, 32, 48, _SIL))
"""``TH (S1) AW Z AX N D SIL`` — "thousand"."""

pmillion: Final[bytes] = bytes((31, _S1, 2, 27, 25, 17, 32, _SIL))
"""``M (S1) IH LL Y AX N SIL`` — "million"."""

pbillion: Final[bytes] = bytes((46, _S1, 2, 27, 25, 17, 32, _SIL))
"""``B (S1) IH LL Y AX N SIL`` — "billion"."""

ptrillion: Final[bytes] = bytes((47, 26, _S1, 2, 27, 25, 17, 32, _SIL))
"""``T R (S1) IH LL Y AX N SIL`` — "trillion"."""

pquadrillion: Final[bytes] = bytes((49, 24, 10, 48, 26, _S1, 2, 27, 25, 17, 32, _SIL))
"""``K W AO D R (S1) IH LL Y AX N SIL`` — "quadrillion"."""


# -- Spoken month names (full pronunciations) ------------------------------
# Compare with the 3-letter m_* abbreviations (above): these are how
# DECtalk *says* each month when given a calendar date.

pjan: Final[bytes] = bytes((55, _S1, 5, 32, 16, 4, 26, 1, _SIL))
"""``JH (S1) AE N YU EH R IY SIL`` — "January"."""

pfeb: Final[bytes] = bytes((37, _S1, 4, 46, 26, 14, 4, 26, 1, _SIL))
"""``F (S1) EH B R UW EH R IY SIL`` — "February"."""

pmar: Final[bytes] = bytes((31, _S1, 6, 26, 54, _SIL))
"""``M (S1) AA R CH SIL`` — "March"."""

papr: Final[bytes] = bytes((_S1, 3, 45, 26, 34, _SIL))
"""``(S1) EY P R EL SIL`` — "April"."""

pmay: Final[bytes] = bytes((31, _S1, 3, _SIL))
"""``M (S1) EY SIL`` — "May"."""

pjun: Final[bytes] = bytes((55, _S1, 14, 32, _SIL))
"""``JH (S1) UW N SIL`` — "June"."""

pjul: Final[bytes] = bytes((55, 18, 27, _S1, 7, _SIL))
"""``JH IX LL (S1) AY SIL`` — "July"."""

paug: Final[bytes] = bytes((_S1, 10, 50, 17, 41, 47, _SIL))
"""``(S1) AO G AX S T SIL`` — "August"."""

psep: Final[bytes] = bytes((41, 4, 45, 47, _S1, 4, 31, 46, 15, _SIL))
"""``S EH P T (S1) EH M B RR SIL`` — "September"."""

poct: Final[bytes] = bytes((6, 49, 47, _S1, 11, 46, 15, _SIL))
"""``AA K T (S1) OW B RR SIL`` — "October"."""

pnov: Final[bytes] = bytes((32, 11, 38, _S1, 4, 31, 46, 15, _SIL))
"""``N OW V (S1) EH M B RR SIL`` — "November"."""

pdec: Final[bytes] = bytes((48, 18, 41, _S1, 4, 31, 46, 15, _SIL))
"""``D IX S (S1) EH M B RR SIL`` — "December"."""

pmonths: Final[tuple[bytes, ...]] = (
    pjan, pfeb, pmar, papr, pmay, pjun,
    pjul, paug, psep, poct, pnov, pdec,
)  # fmt: skip
"""C ``pmonths[]`` — spoken month names indexed Jan=0..Dec=11."""


# -- Currency, percent, and misc words -------------------------------------
# Several of these prefix with ``WBOUND`` (111) which forces a word
# boundary before the spoken token.

_WBOUND = 111
_VPSTART = 113

pdollar: Final[bytes] = bytes((_WBOUND, 48, _S1, 6, 27, 15, _SIL))
"""``(WBOUND) D (S1) AA LL RR SIL`` — "dollar"."""

pcent: Final[bytes] = bytes((41, _S1, 4, 32, 47, _SIL))
"""``S (S1) EH N T SIL`` — "cent"."""

peuro: Final[bytes] = bytes((_WBOUND, 25, _S1, 14, 26, 11, _SIL))
"""``(WBOUND) Y (S1) UW R OW SIL`` — "euro"."""

ppound: Final[bytes] = bytes((_WBOUND, 45, _S1, 8, 32, 48, _SIL))
"""``(WBOUND) P (S1) AW N D SIL`` — "pound"."""

ppence: Final[bytes] = bytes((45, _S1, 4, 32, 41, _SIL))
"""``P (S1) EH N S SIL`` — "pence"."""

ppercent: Final[bytes] = bytes((_WBOUND, 45, 15, 41, _S1, 4, 32, 47, _SIL))
"""``(WBOUND) P RR S (S1) EH N T SIL`` — "percent"."""

ppoint: Final[bytes] = bytes((45, _S1, 12, 32, 47, _SIL))
"""``P (S1) OY N T SIL`` — "point" (decimal)."""

pand: Final[bytes] = bytes((_WBOUND, _VPSTART, 4, 32, 48, _WBOUND, _SIL))
"""``(WBOUND) (VPSTART) EH N D (WBOUND) SIL`` — "and" (with phrase markers)."""

pnone: Final[bytes] = bytes((_SIL,))
"""Empty pronunciation — used as a placeholder when no word should be spoken."""

ptt2tp: Final[bytes] = bytes((
    _WBOUND, 47, _S2, 7, 31, 42, _WBOUND, 47, _S1, 4, 32, _WBOUND,
    47, 13, _WBOUND, 40, 17, _WBOUND, 45, _S1, 8, 15, _WBOUND, _SIL,
))  # fmt: skip
"""Pronunciation of "time-to-2-text-of-the-power" or similar — used by
the number rules; exact word is best inferred from the call site."""


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
    "p10",
    "p11",
    "p12",
    "p13",
    "p14",
    "p15",
    "p16",
    "p17",
    "p18",
    "p19",
    "p20",
    "p30",
    "p40",
    "p50",
    "p60",
    "p70",
    "p80",
    "p90",
    "pOH",
    "pand",
    "papr",
    "paug",
    "pbillion",
    "pcent",
    "pdec",
    "pdegree",
    "pdoctor",
    "pdollar",
    "pdrive",
    "peuro",
    "pfeb",
    "phalf",
    "phalves",
    "phundred",
    "pjan",
    "pjul",
    "pjun",
    "pmar",
    "pmay",
    "pmillion",
    "pminus",
    "pmonths",
    "pnone",
    "pnov",
    "pnumber",
    "poct",
    "pof",
    "pordin",
    "ppence",
    "ppercent",
    "pplus",
    "ppoint",
    "ppound",
    "pquadrillion",
    "psaint",
    "psep",
    "pstreet",
    "pteens",
    "ptens",
    "pthe",
    "pthousand",
    "ptrillion",
    "ptt2tp",
    "punits",
    "up0",
    "up1",
    "up2",
    "up3",
    "up4",
    "up5",
    "up6",
    "up7",
    "up8",
    "up9",
    "upunits",
]
