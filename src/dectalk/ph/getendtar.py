"""``getendtar`` -- end-of-phone target lookup from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1361 (~55 lines).

Symmetric counterpart to :func:`getbegtar`: returns the target at
the *end* of a phone. For non-diphthong segments it delegates to
:func:`gettar`. For diphthongised vowels (``temp < -1``), it walks
``p_diph`` forward to find the terminating ``-1`` sentinel and
returns the entry immediately before it (the last value of the
diph run), then applies the language-specific coarticulation
adjustment when ``par_type == FORM_FREQ``.

.. code-block:: c

    short getendtar(LPTTS_HANDLE_T phTTS, int nfone) {
        temp = gettar(phTTS, nfone);
        if (temp < -1) {
            temp = -temp;
            while (pDph_t->p_diph[temp] != -1) temp++;
            temp = pDph_t->p_diph[temp - 1];
            if (pDphsettar->par_type IS_FORM_FREQ) {
                tmp = get_phone(pDph_t, nfone);
                tmp = tmp & PFONT;
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
from dectalk.ph.get_phone import get_phone
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

_PARTYPE_FORM_FREQ: int = 3


def getendtar(phTTS: TtsHandle, nfone: int) -> int:  # noqa: N803
    """Return the target value at the end of phone ``nfone``.

    Args:
        phTTS: Two-pointer engine handle with populated DphT.
        nfone: Index into ``allophons[]`` naming the target phone.

    Returns:
        gettar's value for non-diphthong phones, or the last diph
        entry plus coarticulation delta for diphthongised vowels.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    temp = gettar(phTTS, nfone)
    if temp < -1:
        # Walk p_diph forward from -temp to find the -1 sentinel, then
        # return the last entry before it.
        p_diph = cast(list[int], p_dph_t.p_diph)
        walk = -temp
        while p_diph[walk] != -1:
            walk += 1
        temp = p_diph[walk - 1]

        if p_dphsettar.par_type == _PARTYPE_FORM_FREQ:
            # Unlike getbegtar (which has a dead `get_phone` call that
            # gets overwritten), getendtar uses get_phone's result.
            tmp = get_phone(p_dph_t, nfone) & PFONT
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


__all__ = ["getendtar"]
