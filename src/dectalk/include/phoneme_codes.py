"""Numeric phoneme and prosody codes used by the DECtalk C front end.

Translated from:

- ``src/dapi/src/include/l_com_ph.h`` — the language-independent control
  codes (stress markers, boundaries, sentence punctuation).
- ``src/dapi/src/include/l_all_ph.h`` — the per-language phoneme code
  tables. We translate only the US (``US_*``) block; UK/SP/LA/GR/FR
  follow when their language libraries are wired up.

The numeric values match the C ``#define``s exactly because per-module
parity tests compare Python-emitted phoneme streams against the C
oracle's bytes. Constants here are the source of truth for the Python
translations of KERNEL, CMD, LTS, dic, PH, and VTM; do not change them.

These do **not** replace the approximate-path :mod:`dectalk.include.
phonemes` (which uses CMU ARPABET). Both files coexist until the
approximate front end is fully replaced.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final

# -- l_com_ph.h --------------------------------------------------------------

BLOCK_RULES: Final[int] = 100  # block allophone substitutions
S3: Final[int] = 100 + 1  # tertiary stress
S2: Final[int] = 100 + 2  # secondary stress
S1: Final[int] = 100 + 3  # primary stress
SEMPH: Final[int] = 100 + 4  # emphatic stress
HAT_RISE: Final[int] = 100 + 5
HAT_FALL: Final[int] = 100 + 6
HAT_RF: Final[int] = 100 + 7  # rise-fall
SBOUND: Final[int] = 100 + 8  # syllable boundary
MBOUND: Final[int] = 100 + 9  # morpheme boundary
HYPHEN: Final[int] = 100 + 10  # noun-compound hyphen
WBOUND: Final[int] = 100 + 11  # word boundary
PPSTART: Final[int] = 100 + 12  # prepositional-phrase start
VPSTART: Final[int] = 100 + 13  # verb-phrase start
RELSTART: Final[int] = 100 + 14  # intro to a sentence or clause
COMMA: Final[int] = 100 + 15  # end of clause
PERIOD: Final[int] = 100 + 16  # end of sentence
QUEST: Final[int] = 100 + 17  # end of question
EXCLAIM: Final[int] = 100 + 18  # end of exclamatory sentence
NEW_PARAGRAPH: Final[int] = 100 + 19
SPECIALWORD: Final[int] = 100 + 20  # citation-mode special word
LINKRWORD: Final[int] = 100 + 21  # UK English linked-R
DOUBLCONS: Final[int] = 100 + 22  # German double-consonant marker

MAXI_PHONES: Final[int] = 57  # max phoneme code used in cm_copt
PHO_SYM_TOT: Final[int] = 100 + 22


# -- l_all_ph.h font codes --------------------------------------------------
# The phoneme codes below are offsets within a per-language font. The full
# code is `(font << PSFONT) + offset` where PSFONT shifts the font into the
# high byte; see phonlist.h / phdefs.h. For US-only work we just need the
# offsets — the font is implied.

PFUSA: Final[int] = 0x1E  # American English phoneme font


# -- l_all_ph.h US allophones (71 codes, 0..70) ------------------------------
class USPhoneme(IntEnum):
    """The 71 US English allophone codes used by the DECtalk C front end.

    Values match ``US_*`` constants in ``l_all_ph.h``. ``SIL`` must be zero
    (the code relies on a zero-valued silence/sentinel in several places).
    """

    SIL = 0
    IY = 1  # 'see'
    IH = 2  # 'bit'
    EY = 3  # 'bay'
    EH = 4  # 'bet'
    AE = 5  # 'cat'
    AA = 6  # 'father'
    AY = 7  # 'buy'
    AW = 8  # 'cow'
    AH = 9  # 'but'
    AO = 10  # 'bought'
    OW = 11  # 'boat'
    OY = 12  # 'boy'
    UH = 13  # 'book'
    UW = 14  # 'boot'
    RR = 15  # syllabic R
    YU = 16  # 'cute'
    AX = 17  # schwa
    IX = 18  # unstressed bit
    IR = 19  # 'near'
    ER = 20  # 'bird'
    AR = 21  # 'car'
    OR_ = 22  # 'or' (named with trailing underscore: OR is a Python keyword)
    UR = 23  # 'cure'
    W = 24
    Y = 25
    R = 26
    LL = 27  # light L
    HX = 28  # /h/ allophone
    RX = 29  # retroflex r-allophone
    LX = 30  # dark L
    M = 31
    N = 32
    NX = 33  # 'sing'
    EL = 34  # syllabic L
    DZ = 35  # voiced dental flap
    EN = 36  # syllabic N
    F = 37
    V = 38
    TH = 39  # 'thin'
    DH = 40  # 'this'
    S = 41
    Z = 42
    SH = 43  # 'ship'
    ZH = 44  # 'measure'
    P = 45
    B = 46
    T = 47
    D = 48
    K = 49
    G = 50
    DX = 51  # flap T (writer/rider)
    TX = 52  # released T allophone
    Q = 53  # glottal stop
    CH = 54
    JH = 55
    DF = 56  # voiced dental fricative allophone
    TZ = 57  # released T+Z (cats)
    CZ = 58  # released K+S
    LY = 59  # palatalised L
    RE = 60  # released R
    X1 = 61  # extension slots reserved for future allophones
    X2 = 62
    X3 = 63
    X4 = 64
    X5 = 65
    X6 = 66
    X7 = 67
    X8 = 68
    X9 = 69
    Z1 = 70  # final extension


US_TOT_ALLOPHONES: Final[int] = 71
"""Number of US allophones (matches ``US_TOT_ALLOPHONES`` in ``l_us_ph.h``)."""


__all__ = [
    "BLOCK_RULES",
    "COMMA",
    "DOUBLCONS",
    "EXCLAIM",
    "HAT_FALL",
    "HAT_RF",
    "HAT_RISE",
    "HYPHEN",
    "LINKRWORD",
    "MAXI_PHONES",
    "MBOUND",
    "NEW_PARAGRAPH",
    "PERIOD",
    "PFUSA",
    "PHO_SYM_TOT",
    "PPSTART",
    "QUEST",
    "RELSTART",
    "S1",
    "S2",
    "S3",
    "SBOUND",
    "SEMPH",
    "SPECIALWORD",
    "US_TOT_ALLOPHONES",
    "VPSTART",
    "WBOUND",
    "USPhoneme",
]
