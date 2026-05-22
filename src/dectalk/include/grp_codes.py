"""Font-encoded German phoneme codes from p_all_ph.h.

Translated from ``src/dapi/src/ph/p_all_ph.h`` (lines 195-255). Each
``GRP_*`` constant is the 16-bit phone code the PH module sees when it
reads a German phone from ``pDph_t->allophons[i]``. The upper 5 bits
encode the language font (``PFGR = 0x1C``); the lower 8 bits encode the
allophone code from ``src/dapi/src/include/l_all_ph.h`` (``GR_*``
constants).

This module is the German sibling of :mod:`dectalk.include.usp_codes`
(US English) and is needed by the per-language dispatch helpers in
``p_gr_st1.c`` (``gr_gettar``, ``gr_special_coartic``, etc.).

The numeric values match the C ``#define``s exactly; per-module parity
tests check that the Python-emitted phoneme streams agree with the C
oracle's bytes.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFGR

_FONT: Final[int] = PFGR << PSFONT


def _g(code: int) -> int:
    """Return ``(PFGR << 8) | code`` for a German allophone."""
    return _FONT | code


# -- Vowels -----------------------------------------------------------------

GRP_A: Final[int] = _g(1)  # "mAnn"
GRP_E: Final[int] = _g(2)  # "Englisch"
GRP_AE: Final[int] = _g(3)  # "cAt" (American)
GRP_EX: Final[int] = _g(4)  # "gabE"
GRP_I: Final[int] = _g(5)  # "mIt"
GRP_O: Final[int] = _g(6)  # "pOst"
GRP_OE: Final[int] = _g(7)  # "kOEnnen"
GRP_U: Final[int] = _g(8)  # "mUnd"
GRP_UE: Final[int] = _g(9)  # "lUEcke"
GRP_AH: Final[int] = _g(10)  # "sAgen"
GRP_EH: Final[int] = _g(11)  # "gEben"
GRP_AEH: Final[int] = _g(3)  # "wAEhlen" (aliases GR_AE in C)
GRP_IH: Final[int] = _g(13)  # "lIEb"
GRP_OH: Final[int] = _g(14)  # "mOnd"
GRP_OEH: Final[int] = _g(7)  # "mOEgen" (aliases GR_OE in C)
GRP_UH: Final[int] = _g(16)  # "hUt"
GRP_UEH: Final[int] = _g(9)  # "hUEten" (aliases GR_UE in C)

# -- Diphthongs -------------------------------------------------------------

GRP_EI: Final[int] = _g(18)  # "klEId"
GRP_AU: Final[int] = _g(19)  # "hAUs"
GRP_EU: Final[int] = _g(20)  # "hEUte"

# -- Nasalised vowels -------------------------------------------------------

GRP_AN: Final[int] = _g(21)  # "pENsion"
GRP_IM: Final[int] = _g(22)  # "tIMbre"
GRP_UM: Final[int] = _g(23)  # "parfUM"
GRP_ON: Final[int] = _g(24)  # "fONdue"

# -- Sonorants --------------------------------------------------------------

GRP_J: Final[int] = _g(25)  # "Ja"
GRP_L: Final[int] = _g(26)  # "Luft"
GRP_RR: Final[int] = _g(27)  # "Rund"
GRP_R: Final[int] = _g(28)  # "waR"
GRP_H: Final[int] = _g(29)  # "Hut"

# -- Nasals -----------------------------------------------------------------

GRP_M: Final[int] = _g(30)  # "Mut"
GRP_N: Final[int] = _g(31)  # "NeiN"
GRP_NG: Final[int] = _g(32)  # "riNG"
GRP_EL: Final[int] = _g(33)  # "nabEL"
GRP_EM: Final[int] = _g(34)  # "grossEM"
GRP_EN: Final[int] = _g(35)  # "badEN"

# -- Fricatives -------------------------------------------------------------

GRP_F: Final[int] = _g(36)  # "Fall"
GRP_V: Final[int] = _g(37)  # "Was"
GRP_S: Final[int] = _g(38)  # "meSSen"
GRP_Z: Final[int] = _g(39)  # "doSe"
GRP_SH: Final[int] = _g(40)  # "SCHule"
GRP_ZH: Final[int] = _g(41)  # "Genie"
GRP_CH: Final[int] = _g(42)  # "niCHt"
GRP_KH: Final[int] = _g(43)  # "noCH"

# -- Plosives ---------------------------------------------------------------

GRP_P: Final[int] = _g(44)  # "Park"
GRP_B: Final[int] = _g(45)  # "Ball"
GRP_T: Final[int] = _g(46)  # "Turm"
GRP_D: Final[int] = _g(47)  # "Dort"
GRP_K: Final[int] = _g(48)  # "Kalt"
GRP_G: Final[int] = _g(49)  # "Gast"
GRP_Q: Final[int] = _g(50)  # "beAmtet"
GRP_PF: Final[int] = _g(51)  # "PFerd"
GRP_TS: Final[int] = _g(52)  # "Zahl"
GRP_DJ: Final[int] = _g(53)  # "Gin"
GRP_TJ: Final[int] = _g(54)  # "maTSCH"
GRP_KSX: Final[int] = _g(55)  # "eXtra"

# -- Short vowels -----------------------------------------------------------

GRP_I1: Final[int] = _g(56)  # short I
GRP_E1: Final[int] = _g(57)  # short E
GRP_O1: Final[int] = _g(58)  # short O
GRP_U1: Final[int] = _g(59)  # short U
GRP_Y1: Final[int] = _g(60)  # short Y
GRP_ER: Final[int] = _g(61)  # "er" double phone

# -- Per-language allophone count ------------------------------------------

GR_TOT_ALLOPHONES: Final[int] = 62
"""Total number of German allophone codes (stride for per-parameter tables)."""


__all__ = [
    "GRP_A",
    "GRP_AE",
    "GRP_AEH",
    "GRP_AH",
    "GRP_AN",
    "GRP_AU",
    "GRP_B",
    "GRP_CH",
    "GRP_D",
    "GRP_DJ",
    "GRP_E",
    "GRP_E1",
    "GRP_EH",
    "GRP_EI",
    "GRP_EL",
    "GRP_EM",
    "GRP_EN",
    "GRP_ER",
    "GRP_EU",
    "GRP_EX",
    "GRP_F",
    "GRP_G",
    "GRP_H",
    "GRP_I",
    "GRP_I1",
    "GRP_IH",
    "GRP_IM",
    "GRP_J",
    "GRP_K",
    "GRP_KH",
    "GRP_KSX",
    "GRP_L",
    "GRP_M",
    "GRP_N",
    "GRP_NG",
    "GRP_O",
    "GRP_O1",
    "GRP_OE",
    "GRP_OEH",
    "GRP_OH",
    "GRP_ON",
    "GRP_P",
    "GRP_PF",
    "GRP_Q",
    "GRP_R",
    "GRP_RR",
    "GRP_S",
    "GRP_SH",
    "GRP_T",
    "GRP_TJ",
    "GRP_TS",
    "GRP_U",
    "GRP_U1",
    "GRP_UE",
    "GRP_UEH",
    "GRP_UH",
    "GRP_V",
    "GRP_Y1",
    "GRP_Z",
    "GRP_ZH",
    "GR_TOT_ALLOPHONES",
]
