"""Japanese phoneme codes from jap_phon.h.

Translated from ``src/dapi/src/include/jap_phon.h``. The 41 base
Japanese allophones plus 13 control / boundary codes.

The codes are language-local — names like ``A``, ``SH``, ``N`` etc.
shadow the US English allophone names in
:mod:`dectalk.include.phoneme_codes`, but the numeric values are
**different**. Use the qualified form
``dectalk.include.jap_phon.JapPhoneme.A`` to disambiguate.

The Japanese language path is unused in the modern Linux build
(LANG_japanese = 4 is reserved but no library is shipped); this
port is for symbol parity only.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class JapPhoneme(IntEnum):
    """The 41 Japanese allophone codes (0..40)."""

    SIL = 0
    I = 1  # noqa: E741
    E = 2
    A = 3
    O = 4  # noqa: E741
    U = 5
    YE = 6
    YA = 7
    YO = 8
    YU = 9
    WI = 10
    WE = 11
    WA = 12
    WO = 13
    H = 14
    M = 15
    N = 16
    NX = 17
    EM = 18
    EN = 19
    NV = 20
    BH = 21
    F = 22
    DH = 23
    S = 24
    Z = 25
    CX = 26
    SH = 27
    ZH = 28
    GH = 29
    R = 30
    P = 31
    B = 32
    T = 33
    D = 34
    K = 35
    G = 36
    TS = 37
    DZ = 38
    CH = 39
    JH = 40


JAP_TOT_ALLOPHONES: Final[int] = 41
"""Number of Japanese allophones (matches ``TOT_ALLOPHONES`` in jap_phon.h)."""

# -- Japanese-specific control codes (41..53) ------------------------------
#
# These shadow the English ones (BLOCK_RULES, NEW_PARAGRAPH, WBOUND, …) but
# carry different numeric values; see :mod:`dectalk.include.phoneme_codes`
# for the English-side definitions.

JAP_BLOCK_RULES: Final[int] = 41
"""Block allophone substitutions in Japanese rules."""

JAP_ACCENT_RISE: Final[int] = 42
"""Japanese accent-rise symbol ``'``."""

JAP_STRONG_RISE: Final[int] = 43
"""Japanese strong-accent-rise symbol ``/``."""

JAP_ACCENT_FALL: Final[int] = 44
"""Japanese accent-fall symbol `` ` ``."""

JAP_STRONG_FALL: Final[int] = 45
"""Japanese strong-accent-fall symbol ``\\``."""

JAP_LONG_PHONE: Final[int] = 46
"""Long-phoneme marker (extends preceding mora)."""

JAP_NEW_PARAGRAPH: Final[int] = 47
"""Begin a new paragraph."""

# -- Japanese boundary markers (48..53; mutually exclusive within a span) --

JAP_ABOUND: Final[int] = 48
"""Affix boundary."""

JAP_WBOUND: Final[int] = 49
"""Word boundary."""

JAP_PBOUND: Final[int] = 50
"""Phrase boundary."""

JAP_CBOUND: Final[int] = 51
"""Clause boundary."""

JAP_SBOUND: Final[int] = 52
"""Sentence boundary (statement)."""

JAP_QBOUND: Final[int] = 53
"""Sentence boundary (question)."""

JAP_PHO_SYM_TOT: Final[int] = 54
"""Total Japanese phone-symbol count (allophones + control codes)."""


__all__ = [
    "JAP_ABOUND",
    "JAP_ACCENT_FALL",
    "JAP_ACCENT_RISE",
    "JAP_BLOCK_RULES",
    "JAP_CBOUND",
    "JAP_LONG_PHONE",
    "JAP_NEW_PARAGRAPH",
    "JAP_PBOUND",
    "JAP_PHO_SYM_TOT",
    "JAP_QBOUND",
    "JAP_SBOUND",
    "JAP_STRONG_FALL",
    "JAP_STRONG_RISE",
    "JAP_TOT_ALLOPHONES",
    "JAP_WBOUND",
    "JapPhoneme",
]
