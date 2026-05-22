"""Font-encoded Spanish (Castilian) phoneme codes from p_all_ph.h.

Translated from ``src/dapi/src/ph/p_all_ph.h``. Each ``SPP_*``
constant is the 16-bit phone code the PH module sees when it reads
``pDph_t->phonemes[i]`` -- the upper 5 bits encode the language font
(``PFSP = 0x1B``) and the lower 8 bits encode the allophone code from
:class:`~dectalk.include.phoneme_codes.SPPhoneme`.

The bare codes (``SP_A = 1`` etc.) come from ``l_all_ph.h``; this
module wires them together with the font byte so per-phoneme lookups
in ``p_sp_st1.c`` (``phone_temp == SPP_M``, ``phlas_temp == SPP_F``,
...) translate one-to-one.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFSP


class SPPhoneme(IntEnum):
    """Spanish allophone codes from ``l_all_ph.h`` (offsets 0..38)."""

    SIL = 0
    A = 1  # 'palabra'
    E = 2  # 'leo'
    I = 3  # 'hilo'  # noqa: E741 -- mirrors C name
    O = 4  # 'hola'  # noqa: E741 -- mirrors C name
    U = 5  # 'lunes'
    WX = 6  # rounded diphthong semi-vowel
    YX = 7  # unrounded diphthong semi-vowel
    RR = 8  # 'rama'
    L = 9  # 'luna'
    LL = 10  # 'calle'
    M = 11  # 'mama'
    N = 12  # 'nana'
    NH = 13  # 'munoz'
    F = 14  # 'feo'
    S = 15  # 'casa'
    J = 16  # 'caja'
    TH = 17  # 'caza'
    BH = 18  # 'haba'
    DH = 19  # 'hada'
    GH = 20  # 'haga'
    YH = 21  # 'yate' affricate
    P = 22  # 'papa'
    B = 23  # 'barco'
    T = 24  # 'tela'
    D = 25  # 'dama'
    K = 26  # 'casa'
    G = 27  # 'gasa'
    CH = 28  # 'charco'
    Y = 29  # 'haya' fricative
    R = 30  # 'sara'
    Q = 31  # offglide
    Z = 32  # 'desde'
    W = 33  # 'hueso'
    NX = 34  # 'mango'
    V = 35  # 'afgano'
    IX = 36  # offglide
    MX = 37  # 'infierno' (nf)
    PH = 38  # 'observar'


_FONT: Final[int] = PFSP << PSFONT


def _s(code: SPPhoneme) -> int:
    """Return ``(PFSP << 8) | code`` for a Spanish allophone."""
    return _FONT | int(code)


# -- Vowels and semivowels --------------------------------------------------

SPP_A: Final[int] = _s(SPPhoneme.A)
SPP_E: Final[int] = _s(SPPhoneme.E)
SPP_I: Final[int] = _s(SPPhoneme.I)
SPP_O: Final[int] = _s(SPPhoneme.O)
SPP_U: Final[int] = _s(SPPhoneme.U)
SPP_WX: Final[int] = _s(SPPhoneme.WX)
SPP_YX: Final[int] = _s(SPPhoneme.YX)
SPP_IX: Final[int] = _s(SPPhoneme.IX)

# -- Sonorants and trills ---------------------------------------------------

SPP_R: Final[int] = _s(SPPhoneme.R)
SPP_RR: Final[int] = _s(SPPhoneme.RR)
SPP_L: Final[int] = _s(SPPhoneme.L)
SPP_LL: Final[int] = _s(SPPhoneme.LL)
SPP_W: Final[int] = _s(SPPhoneme.W)
SPP_Y: Final[int] = _s(SPPhoneme.Y)

# -- Nasals -----------------------------------------------------------------

SPP_M: Final[int] = _s(SPPhoneme.M)
SPP_N: Final[int] = _s(SPPhoneme.N)
SPP_NH: Final[int] = _s(SPPhoneme.NH)
SPP_NX: Final[int] = _s(SPPhoneme.NX)
SPP_MX: Final[int] = _s(SPPhoneme.MX)

# -- Fricatives and approximants -------------------------------------------

SPP_F: Final[int] = _s(SPPhoneme.F)
SPP_S: Final[int] = _s(SPPhoneme.S)
SPP_J: Final[int] = _s(SPPhoneme.J)
SPP_TH: Final[int] = _s(SPPhoneme.TH)
SPP_Z: Final[int] = _s(SPPhoneme.Z)
SPP_V: Final[int] = _s(SPPhoneme.V)
SPP_BH: Final[int] = _s(SPPhoneme.BH)
SPP_DH: Final[int] = _s(SPPhoneme.DH)
SPP_GH: Final[int] = _s(SPPhoneme.GH)
SPP_YH: Final[int] = _s(SPPhoneme.YH)

# -- Plosives and affricates -----------------------------------------------

SPP_P: Final[int] = _s(SPPhoneme.P)
SPP_B: Final[int] = _s(SPPhoneme.B)
SPP_T: Final[int] = _s(SPPhoneme.T)
SPP_D: Final[int] = _s(SPPhoneme.D)
SPP_K: Final[int] = _s(SPPhoneme.K)
SPP_G: Final[int] = _s(SPPhoneme.G)
SPP_CH: Final[int] = _s(SPPhoneme.CH)
SPP_Q: Final[int] = _s(SPPhoneme.Q)
SPP_PH: Final[int] = _s(SPPhoneme.PH)


SP_TOT_ALLOPHONES: Final[int] = 39
"""Number of Spanish allophones (matches ``SP_TOT_ALLOPHONES`` in ``l_all_ph.h``)."""


__all__ = [
    "SPP_A",
    "SPP_B",
    "SPP_BH",
    "SPP_CH",
    "SPP_D",
    "SPP_DH",
    "SPP_E",
    "SPP_F",
    "SPP_G",
    "SPP_GH",
    "SPP_I",
    "SPP_IX",
    "SPP_J",
    "SPP_K",
    "SPP_L",
    "SPP_LL",
    "SPP_M",
    "SPP_MX",
    "SPP_N",
    "SPP_NH",
    "SPP_NX",
    "SPP_O",
    "SPP_P",
    "SPP_PH",
    "SPP_Q",
    "SPP_R",
    "SPP_RR",
    "SPP_S",
    "SPP_T",
    "SPP_TH",
    "SPP_U",
    "SPP_V",
    "SPP_W",
    "SPP_WX",
    "SPP_Y",
    "SPP_YH",
    "SPP_YX",
    "SPP_Z",
    "SP_TOT_ALLOPHONES",
    "SPPhoneme",
]
