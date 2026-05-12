"""Font-encoded US phoneme codes from p_all_ph.h.

Translated from ``src/dapi/src/ph/p_all_ph.h``. Each ``USP_*``
constant is the 16-bit phone code the PH module sees when it reads
``pDph_t->phonemes[i]`` — the upper 5 bits encode the language font
(``PFUSA = 0x1E``) and the lower 8 bits encode the allophone code
from :class:`~dectalk.include.phoneme_codes.USPhoneme`.

The bare codes (``US_IY = 1``, etc.) are in
:mod:`dectalk.include.phoneme_codes`; this module wires them
together with the font byte so the per-phoneme lookups in
``ph_setar.c`` / ``p_us_st1.c`` (``foncur == USP_P``,
``fonnex == USP_LL``, …) translate one-to-one.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA, USPhoneme

_FONT: Final[int] = PFUSA << PSFONT


def _u(code: USPhoneme) -> int:
    """Return ``(PFUSA << 8) | code`` for a US allophone."""
    return _FONT | int(code)


# -- Vowels and semivowels --------------------------------------------------

USP_IY: Final[int] = _u(USPhoneme.IY)
USP_IH: Final[int] = _u(USPhoneme.IH)
USP_EY: Final[int] = _u(USPhoneme.EY)
USP_EH: Final[int] = _u(USPhoneme.EH)
USP_AE: Final[int] = _u(USPhoneme.AE)
USP_AA: Final[int] = _u(USPhoneme.AA)
USP_AY: Final[int] = _u(USPhoneme.AY)
USP_AW: Final[int] = _u(USPhoneme.AW)
USP_AH: Final[int] = _u(USPhoneme.AH)
USP_AO: Final[int] = _u(USPhoneme.AO)
USP_OW: Final[int] = _u(USPhoneme.OW)
USP_OY: Final[int] = _u(USPhoneme.OY)
USP_UH: Final[int] = _u(USPhoneme.UH)
USP_UW: Final[int] = _u(USPhoneme.UW)
USP_RR: Final[int] = _u(USPhoneme.RR)
USP_YU: Final[int] = _u(USPhoneme.YU)
USP_AX: Final[int] = _u(USPhoneme.AX)
USP_IX: Final[int] = _u(USPhoneme.IX)
USP_IR: Final[int] = _u(USPhoneme.IR)
USP_ER: Final[int] = _u(USPhoneme.ER)
USP_AR: Final[int] = _u(USPhoneme.AR)
USP_OR: Final[int] = _u(USPhoneme.OR_)
USP_UR: Final[int] = _u(USPhoneme.UR)

# -- Sonorants --------------------------------------------------------------

USP_W: Final[int] = _u(USPhoneme.W)
USP_YX: Final[int] = _u(USPhoneme.Y)  # C uses USP_YX for the consonantal Y
USP_R: Final[int] = _u(USPhoneme.R)
USP_LL: Final[int] = _u(USPhoneme.LL)
USP_HX: Final[int] = _u(USPhoneme.HX)
USP_RX: Final[int] = _u(USPhoneme.RX)
USP_LX: Final[int] = _u(USPhoneme.LX)

# -- Nasals -----------------------------------------------------------------

USP_M: Final[int] = _u(USPhoneme.M)
USP_N: Final[int] = _u(USPhoneme.N)
USP_NX: Final[int] = _u(USPhoneme.NX)
USP_EL: Final[int] = _u(USPhoneme.EL)
USP_DZ: Final[int] = _u(USPhoneme.DZ)
USP_EN: Final[int] = _u(USPhoneme.EN)

# -- Fricatives -------------------------------------------------------------

USP_F: Final[int] = _u(USPhoneme.F)
USP_V: Final[int] = _u(USPhoneme.V)
USP_TH: Final[int] = _u(USPhoneme.TH)
USP_DH: Final[int] = _u(USPhoneme.DH)
USP_S: Final[int] = _u(USPhoneme.S)
USP_Z: Final[int] = _u(USPhoneme.Z)
USP_SH: Final[int] = _u(USPhoneme.SH)
USP_ZH: Final[int] = _u(USPhoneme.ZH)

# -- Plosives and affricates ------------------------------------------------

USP_P: Final[int] = _u(USPhoneme.P)
USP_B: Final[int] = _u(USPhoneme.B)
USP_T: Final[int] = _u(USPhoneme.T)
USP_D: Final[int] = _u(USPhoneme.D)
USP_K: Final[int] = _u(USPhoneme.K)
USP_G: Final[int] = _u(USPhoneme.G)
USP_DX: Final[int] = _u(USPhoneme.DX)
USP_TX: Final[int] = _u(USPhoneme.TX)
USP_Q: Final[int] = _u(USPhoneme.Q)
USP_CH: Final[int] = _u(USPhoneme.CH)
USP_JH: Final[int] = _u(USPhoneme.JH)
USP_DF: Final[int] = _u(USPhoneme.DF)

# -- Extension allophones (reserved) ----------------------------------------

USP_TZ: Final[int] = _u(USPhoneme.TZ)
USP_CZ: Final[int] = _u(USPhoneme.CZ)
USP_LY: Final[int] = _u(USPhoneme.LY)
USP_RE: Final[int] = _u(USPhoneme.RE)
USP_X1: Final[int] = _u(USPhoneme.X1)
USP_X2: Final[int] = _u(USPhoneme.X2)
USP_X3: Final[int] = _u(USPhoneme.X3)
USP_X4: Final[int] = _u(USPhoneme.X4)
USP_X5: Final[int] = _u(USPhoneme.X5)
USP_X6: Final[int] = _u(USPhoneme.X6)
USP_X7: Final[int] = _u(USPhoneme.X7)
USP_X8: Final[int] = _u(USPhoneme.X8)
USP_X9: Final[int] = _u(USPhoneme.X9)
USP_Z1: Final[int] = _u(USPhoneme.Z1)


__all__ = [
    "USP_AA",
    "USP_AE",
    "USP_AH",
    "USP_AO",
    "USP_AR",
    "USP_AW",
    "USP_AX",
    "USP_AY",
    "USP_B",
    "USP_CH",
    "USP_CZ",
    "USP_D",
    "USP_DF",
    "USP_DH",
    "USP_DX",
    "USP_DZ",
    "USP_EH",
    "USP_EL",
    "USP_EN",
    "USP_ER",
    "USP_EY",
    "USP_F",
    "USP_G",
    "USP_HX",
    "USP_IH",
    "USP_IR",
    "USP_IX",
    "USP_IY",
    "USP_JH",
    "USP_K",
    "USP_LL",
    "USP_LX",
    "USP_LY",
    "USP_M",
    "USP_N",
    "USP_NX",
    "USP_OR",
    "USP_OW",
    "USP_OY",
    "USP_P",
    "USP_Q",
    "USP_R",
    "USP_RE",
    "USP_RR",
    "USP_RX",
    "USP_S",
    "USP_SH",
    "USP_T",
    "USP_TH",
    "USP_TX",
    "USP_TZ",
    "USP_UH",
    "USP_UR",
    "USP_UW",
    "USP_V",
    "USP_W",
    "USP_X1",
    "USP_X2",
    "USP_X3",
    "USP_X4",
    "USP_X5",
    "USP_X6",
    "USP_X7",
    "USP_X8",
    "USP_X9",
    "USP_YU",
    "USP_YX",
    "USP_Z",
    "USP_Z1",
    "USP_ZH",
]
