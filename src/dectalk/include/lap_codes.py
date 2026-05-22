"""Font-encoded Latin American Spanish phoneme codes from p_all_ph.h.

Translated from ``src/dapi/src/ph/p_all_ph.h``. Each ``LAP_*``
constant is the 16-bit phone code the PH module sees when it reads
``pDph_t->phonemes[i]`` for the Latin American Spanish voice — the
upper 5 bits encode the language font (``PFLA = 0x1A``) and the
lower 8 bits encode the LA allophone code defined in
``src/dapi/src/include/l_all_ph.h``.

The bare codes (``LA_A = 1``, etc.) are kept inline here to avoid
adding another :class:`IntEnum` to
:mod:`dectalk.include.phoneme_codes`; the comment column gives the
``l_all_ph.h`` numeric value. The font-encoded constants below let
the per-phoneme lookups in ``p_la_st1.c`` (``phone_temp == LAP_M``,
``phone_temp == LAP_R``, ...) translate one-to-one.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFLA

_FONT: Final[int] = PFLA << PSFONT


def _l(code: int) -> int:
    """Return ``(PFLA << 8) | code`` for a LA allophone."""
    return _FONT | code


# Numeric codes mirror ``LA_*`` defines in ``l_all_ph.h`` lines 255-292.
LA_TOT_ALLOPHONES: Final[int] = 39
"""Number of LA Spanish allophones (matches ``LA_TOT_ALLOPHONES`` in ``l_la_ph.h``)."""

# -- Vowels and semivowels --------------------------------------------------

LAP_A: Final[int] = _l(1)  # 'Palabra'
LAP_E: Final[int] = _l(2)  # 'Leo'
LAP_I: Final[int] = _l(3)  # 'Hilo'
LAP_O: Final[int] = _l(4)  # 'Hola'
LAP_U: Final[int] = _l(5)  # 'Lunes'
LAP_WX: Final[int] = _l(6)  # rounded diphthong semivowel
LAP_YX: Final[int] = _l(7)  # unround diphthong semivowel

# -- Sonorants --------------------------------------------------------------

LAP_RR: Final[int] = _l(8)  # 'Rama' (trill)
LAP_L: Final[int] = _l(9)  # 'Luna'
LAP_LL: Final[int] = _l(10)  # 'Calle'
LAP_R: Final[int] = _l(30)  # 'Sara' (tap)
LAP_W: Final[int] = _l(33)  # 'Hueso'
LAP_Y: Final[int] = _l(29)  # 'Haya' fricative

# -- Nasals -----------------------------------------------------------------

LAP_M: Final[int] = _l(11)  # 'Mama'
LAP_N: Final[int] = _l(12)  # 'Nana'
LAP_NH: Final[int] = _l(13)  # 'Munoz' (palatal n)
LAP_NX: Final[int] = _l(34)  # 'Mango' (velar n)
LAP_MX: Final[int] = _l(37)  # 'Infierno' (assimilated)

# -- Fricatives -------------------------------------------------------------

LAP_F: Final[int] = _l(14)  # 'Feo'
LAP_S: Final[int] = _l(15)  # 'Casa'
LAP_J: Final[int] = _l(16)  # 'Caja' (velar fricative)
LAP_TH: Final[int] = _l(17)  # 'Caza' (theta)
LAP_BH: Final[int] = _l(18)  # 'Haba' (voiced bilabial fricative)
LAP_DH: Final[int] = _l(19)  # 'Hada' (voiced dental fricative)
LAP_GH: Final[int] = _l(20)  # 'Haga' (voiced velar fricative)
LAP_YH: Final[int] = _l(21)  # 'Yate' affricate
LAP_Z: Final[int] = _l(32)  # 'Desde'
LAP_V: Final[int] = _l(35)  # 'Afgano'

# -- Plosives and affricates ------------------------------------------------

LAP_P: Final[int] = _l(22)  # 'Papa'
LAP_B: Final[int] = _l(23)  # 'Barco'
LAP_T: Final[int] = _l(24)  # 'Tela'
LAP_D: Final[int] = _l(25)  # 'Dama'
LAP_K: Final[int] = _l(26)  # 'Casa'
LAP_G: Final[int] = _l(27)  # 'Gasa'
LAP_CH: Final[int] = _l(28)  # 'Charco'
LAP_Q: Final[int] = _l(31)  # 'nh' offglide

# -- Off-glides / liaison ---------------------------------------------------

LAP_IX: Final[int] = _l(36)  # 'nh' offglide
LAP_PH: Final[int] = _l(38)  # 'Observar'


__all__ = [
    "LAP_A",
    "LAP_B",
    "LAP_BH",
    "LAP_CH",
    "LAP_D",
    "LAP_DH",
    "LAP_E",
    "LAP_F",
    "LAP_G",
    "LAP_GH",
    "LAP_I",
    "LAP_IX",
    "LAP_J",
    "LAP_K",
    "LAP_L",
    "LAP_LL",
    "LAP_M",
    "LAP_MX",
    "LAP_N",
    "LAP_NH",
    "LAP_NX",
    "LAP_O",
    "LAP_P",
    "LAP_PH",
    "LAP_Q",
    "LAP_R",
    "LAP_RR",
    "LAP_S",
    "LAP_T",
    "LAP_TH",
    "LAP_U",
    "LAP_V",
    "LAP_W",
    "LAP_WX",
    "LAP_Y",
    "LAP_YH",
    "LAP_YX",
    "LAP_Z",
    "LA_TOT_ALLOPHONES",
]
