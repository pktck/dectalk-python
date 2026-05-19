"""``setloc`` -- static locus-computation helper from ph_sttr2.c.

Translated from ``src/dapi/src/ph/ph_sttr2.c`` line 69 (~260 lines).

The C ``static short`` helper computes formant-transition locus
frequencies at obstruent / sonorant boundaries. Used by the
per-language ``*_forw_smooth_rules`` / ``*_back_smooth_rules``
helpers that :func:`phsettar` invokes for each parameter.

Flow:

1. Read the three surrounding phones (obstruent, sonorant, far
   vowel) via :func:`get_phone`.
2. Decide whether to inspect the init or final part of the sonorant
   (``initfinso == 'i'`` or ``'f'``).
3. Filter: bail with 0 if the formant index is above F3, the
   obstruent isn't actually an obstruent, or the sonorant is one.
4. Pick a per-language locus table (``us_maleloc``/``us_femloc`` /
   ``uk_*`` / ``gr_*`` / ``la_*`` / ``sp_*`` / ``fr_*``) via the
   font byte and ``malfem`` toggle. The Python port currently only
   wires up the US path.
5. Read ``locus`` / ``prcnt`` / ``durtran`` triple from the locus
   table.
6. Apply F2-back / palatal-dental tweaks.
7. Compute ``bouval = locus + muldv(prcnt, curval - locus, 100)``.
8. If both sonorant and far vowel are vowels and the parameter is
   F2, call :func:`vv_coartic_across_c` and re-compute ``bouval``.

Returns 1 on success, 0 if the locus lookup found no entry or the
filter rejected the call.
"""

from __future__ import annotations

# ruff: noqa: SIM108 -- C-literal style kept
from typing import cast

from dectalk.include.all_phon_counts import (
    GR_TOT_ALLOPHONES,
    LA_TOT_ALLOPHONES,
    SP_TOT_ALLOPHONES,
    UK_TOT_ALLOPHONES,
)
from dectalk.include.cmd_codes import PFONT, PSFONT
from dectalk.include.phoneme_codes import (
    PFFR,
    PFGR,
    PFLA,
    PFSP,
    PFUK,
    PFUSA,
    US_TOT_ALLOPHONES,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.getendtar import getendtar
from dectalk.ph.math_helpers import muldv
from dectalk.ph.numeric_constants import F1, F2, F3, MALE
from dectalk.ph.phoneme_features import F2BACKF, F2BACKI, FDENTAL, FPALATL, FVOWEL
from dectalk.ph.rom_tables import us_femloc, us_maleloc
from dectalk.ph.sonor_classes import (
    BACK_ROUNDED_VOWEL,
    OBSTRUENT,
    ROUNDED_SONOR_CONS,
)
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import begtyp, endtyp, phone_feature, place, plocu
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.vv_coartic_across_c import vv_coartic_across_c

_FONT_USA: int = PFUSA << PSFONT
_FONT_UK: int = PFUK << PSFONT
_FONT_GR: int = PFGR << PSFONT
_FONT_LA: int = PFLA << PSFONT
_FONT_SP: int = PFSP << PSFONT
_FONT_FR: int = PFFR << PSFONT

# C: "Sontyx now equals 1, 2, 3, or 4" -- low-vowel maps back to 2.
_LOW_VOWEL_SONTYX: int = 6


def setloc(  # noqa: PLR0912, PLR0915 -- faithful translation of 260-line C function
    phTTS: TtsHandle,  # noqa: N803
    nfonobst: int,
    nfonsonor: int,
    initfinso: str,
    nfonvowel: int,
    feanex: int,
) -> int:
    """Compute formant-transition locus for an obstruent/sonorant boundary.

    Args:
        phTTS: Two-pointer engine handle with populated DphT.
        nfonobst: Phone index of the segment thought to be an obstruent.
        nfonsonor: Phone index of the segment thought to be a sonorant.
        initfinso: ``'i'`` to use the init part of the sonorant, ``'f'``
            for the end. The C source uses a ``char`` argument.
        nfonvowel: Phone index of the (likely-vowel) segment on the
            other side of the obstruent.
        feanex: Feature bitmask of the next phone (kept for parity
            with the C signature; not consumed in this branch).

    Returns:
        ``1`` on success (``bouval`` / ``durtran`` written), ``0``
        if the filter rejected the inputs or no locus entry exists.
    """
    del feanex  # Kept for C-signature parity; unused in this path.
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    fonobst = get_phone(p_dph_t, nfonobst)
    fonsonor = get_phone(p_dph_t, nfonsonor)
    fonvowel = get_phone(p_dph_t, nfonvowel)

    # Pick init vs final endpoints of the sonorant.
    if initfinso == "i":
        typob = endtyp(fonobst)
        typso = begtyp(fonsonor)
    else:
        typob = begtyp(fonobst)
        typso = endtyp(fonsonor)

    # Filter: only obstruent->sonorant transitions, F1-F3 only.
    if p_dphsettar.np > F3 or typob != OBSTRUENT or typso == OBSTRUENT:
        return 0

    # Read the sonorant target value at the chosen endpoint.
    if initfinso == "i":
        f2backaffil = place(fonsonor) & F2BACKI
        curval = getbegtar(phTTS, nfonsonor)
    else:
        f2backaffil = place(fonsonor) & F2BACKF
        curval = getendtar(phTTS, nfonsonor)

    sontyx = typso
    if typso == ROUNDED_SONOR_CONS:
        # Rounded sonorant conson uses the back-rounded-vowel locus.
        sontyx = BACK_ROUNDED_VOWEL
    if typso == _LOW_VOWEL_SONTYX:
        # Low vowel maps to back-unrounded.
        sontyx = 2

    # Per-language locus-table dispatch.
    tmp = fonobst & PFONT
    ploc = 0
    if tmp == _FONT_USA:
        ploc = plocu(fonobst + (US_TOT_ALLOPHONES * (sontyx - 1)))
        if p_dph_t.malfem == MALE:
            p_dph_t.p_locus = list(us_maleloc)
        else:
            p_dph_t.p_locus = list(us_femloc)
    elif tmp == _FONT_UK:
        # Kept for parity with the C source; pending uk_*loc tables.
        _ = UK_TOT_ALLOPHONES
        raise NotImplementedError(
            "setloc: UK locus tables (uk_maleloc / uk_femloc) not yet ported."
        )
    elif tmp == _FONT_GR:
        _ = GR_TOT_ALLOPHONES
        raise NotImplementedError(
            "setloc: German locus tables (gr_maleloc / gr_femloc) not yet ported."
        )
    elif tmp == _FONT_LA:
        _ = LA_TOT_ALLOPHONES
        raise NotImplementedError("setloc: Latin-American Spanish locus tables not yet ported.")
    elif tmp == _FONT_SP:
        _ = SP_TOT_ALLOPHONES
        raise NotImplementedError("setloc: Castilian Spanish locus tables not yet ported.")
    elif tmp == _FONT_FR:
        raise NotImplementedError(
            "setloc: French locus tables not yet ported (C uses literal 40 here)."
        )

    if ploc == 0:
        # No locus entry; caller falls back to the default smooth calc.
        return 0

    # Locus table has 3 entries per formant.
    ploc = ploc + 3 * (p_dphsettar.np - F1)
    p_locus = cast(list[int], p_dph_t.p_locus)
    locus = p_locus[ploc]
    prcnt = p_locus[ploc + 1]
    p_dphsettar.durtran = mstofr(p_locus[ploc + 2])

    # Reduce F2/F3 trans in a rounded sonorant conson next to a non-
    # palatal, non-dental obstruent.
    if (
        typso == ROUNDED_SONOR_CONS
        and p_dphsettar.np > F1
        and (place(fonobst) & (FPALATL | FDENTAL)) == 0
    ):
        prcnt = (prcnt >> 1) + 50

    # F2 back-cavity vowel/sonor: reduce trans extent by 1/4.
    if f2backaffil != 0 and p_dphsettar.np == F2:
        prcnt += 25 - (prcnt >> 2)
        p_dphsettar.durtran = (p_dphsettar.durtran >> 1) + 2

    # bouval = locus + ((prcnt * (curval - locus)) / 100).
    # Note: the UK-specific `prcnt+40` tweak for fonobst==54 is gated
    # by #ifdef ENGLISH_UK in the C and is not active in the Linux US
    # build; omit it here.
    delta_freq = muldv(prcnt, curval - locus, 100)
    p_dphsettar.bouval = locus + delta_freq

    # V-V coarticulation across an obstruent consonant.
    if (
        (phone_feature(fonsonor) & FVOWEL) != 0
        and (phone_feature(fonvowel) & FVOWEL) != 0
        and p_dphsettar.np == F2
    ):
        if initfinso == "i":
            tarvowel = getendtar(phTTS, nfonvowel)
        else:
            tarvowel = getbegtar(phTTS, nfonvowel)

        vv_coartic_across_c(
            p_dph_t,
            fonvowel,
            tarvowel,
            fonsonor,
            curval,
            fonobst,
            p_dph_t.allodurs[nfonobst],
        )
        curval += p_dphsettar.vvbouval
        delta_freq = muldv(prcnt, curval - locus, 100)
        p_dphsettar.bouval = locus + delta_freq
        # vvbouval is added back in PH_DRAW.C; subtract it here.
        p_dphsettar.bouval -= p_dphsettar.vvbouval

    return 1


__all__ = ["setloc"]
