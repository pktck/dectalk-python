"""``getbegtar`` -- beginning-of-phone target lookup from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1293 (~50 lines).

The C function returns the target value at the beginning of a phone.
For non-diphthong segments it just delegates to :func:`gettar`. For
diphthongised vowels (target ``< -1`` from gettar), it dereferences
``p_diph[-temp]`` (the first diph entry) and applies the language-
specific ``*_special_coartic`` adjustment when ``par_type ==
FORM_FREQ``.

.. code-block:: c

    short getbegtar(LPTTS_HANDLE_T phTTS, int nfone) {
        temp = gettar(phTTS, nfone);
        if (temp < -1) {
            temp = pDph_t->p_diph[-temp];
            if (pDphsettar->par_type IS_FORM_FREQ) {
                tmp = get_phone(pDph_t, nfone);  /* dead store */
                tmp = nfone & PFONT;
                if (tmp == PFUSA << PSFONT)
                    temp += us_special_coartic(pDph_t, nfone, 0);
                else if (tmp == PFGR << PSFONT)
                    temp += gr_special_coartic(pDph_t, nfone, 0);
                else if (tmp == PFLA << PSFONT)
                    temp += la_special_coartic(pDph_t, nfone, 0);
                else if (tmp == PFSP << PSFONT)
                    temp += sp_special_coartic(pDph_t, nfone, 0);
                /* PFFR branch is commented out in the C source. */
            }
        }
        return temp;
    }
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PFONT, PSFONT
from dectalk.include.phoneme_codes import PFGR, PFLA, PFSP, PFUSA
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.gettar import gettar
from dectalk.ph.gr_special_coartic import gr_special_coartic
from dectalk.ph.la_special_coartic import la_special_coartic
from dectalk.ph.sp_special_coartic import sp_special_coartic
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_special_coartic import us_special_coartic

_FONT_USA: int = PFUSA << PSFONT
_FONT_GR: int = PFGR << PSFONT
_FONT_LA: int = PFLA << PSFONT
_FONT_SP: int = PFSP << PSFONT

# par_type == 3 maps to IS_FORM_FREQ in ph_defs.h.
_PARTYPE_FORM_FREQ: int = 3


def getbegtar(phTTS: TtsHandle, nfone: int) -> int:  # noqa: N803
    """Return the target value at the beginning of phone ``nfone``.

    Args:
        phTTS: Two-pointer engine handle with populated DphT.
        nfone: Index into ``allophons[]`` naming the target phone.

    Returns:
        Either gettar's raw return (non-diphthong path) or the
        diph-resolved first value plus coarticulation delta.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    temp = gettar(phTTS, nfone)
    if temp < -1:
        # Diphthong sentinel: first diph entry is at p_diph[-temp].
        p_diph = cast(list[int], p_dph_t.p_diph)
        temp = p_diph[-temp]

        if p_dphsettar.par_type == _PARTYPE_FORM_FREQ:
            # The C source has a bug here: it computes `tmp =
            # get_phone(...)` and then immediately overwrites with
            # `tmp = nfone & PFONT`. We mirror the effective behaviour
            # (the get_phone call is dead, ignore it).
            tmp = nfone & PFONT
            if tmp == _FONT_USA:
                temp += us_special_coartic(p_dph_t, nfone, 0)
            elif tmp == _FONT_GR:
                temp += gr_special_coartic(p_dph_t, nfone, 0)
            elif tmp == _FONT_LA:
                temp += la_special_coartic(p_dph_t, nfone, 0)
            elif tmp == _FONT_SP:
                temp += sp_special_coartic(p_dph_t, nfone, 0)
            # PFFR branch is commented out in the C source; PFUK has
            # no branch at all. Both fall through as no-ops.

    return temp


__all__ = ["getbegtar"]
