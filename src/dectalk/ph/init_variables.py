"""``init_variables`` -- static phsettar initialiser from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1764 (~120 lines).

The C function initialises every transient variable that
:func:`phsettar` consumes during its main per-parameter loop. It
loads the ``allophons`` / ``allofeats`` triple for the previous /
current / next phone, computes inherent-duration frame counts via
:func:`inh_timing`, derives the ``shrink`` / ``shrif`` / ``shrib``
coefficients that drive sonorant duration shaping, and zeroes the
``tspesh`` "special override" slot for every parameter:

.. code-block:: c

    static void init_variables (LPTTS_HANDLE_T phTTS,
                    short *psInhdr_frames, short *psShrink,
                    short *psShrif, short *psShrib,
                    short *psPholas, short *psFealas,
                    short *psFeacur, short *psFeanex,
                    short *psStruclm2, short *psStruclas,
                    short *psStruccur, short *psStrucnex,
                    short **ppsNdips, short *psPhonp2)
    {
        ...
        if (pDph_t->nphone == 0)            // First position
        {
            *psStruclm2 = 0;
            *psPholas = GEN_SIL;
            if (pDphsettar->initsw == 0) {
                pDphsettar->initsw++;
                for (pDphsettar->np = &PF1; pDphsettar->np <= &PTILT;
                     pDphsettar->np++) {
                    pDphsettar->np->tarend = getbegtar(phTTS, 0);
                }
            }
        } else {
            ...
        }
        ...
        *psFealas = phone_feature(pDph_t, *psPholas);
        *psFeacur = phone_feature(pDph_t, pDphsettar->phcur);
        *psFeanex = phone_feature(pDph_t, pDphsettar->phonex);

        *psInhdr_frames = mstofr(inh_timing(phTTS,
                                            pDphsettar->phcur));

        // Transition durs are shorter if phone dur is short
        if (((*psFeacur & FOBST) IS_MINUS)
            && (pDphsettar->phcur != GEN_SIL))
        {
            ...
            *psShrink = muldv(FRAC_ONE, pDph_t->durfon, *psInhdr_frames);
            *psShrif = (*psShrink >> 1) + FRAC_HALF;
            *psShrib = *psShrif - 1600;
        }
        ...
        PAV.tspesh = 0;
        ...
        PTILT.tspesh = 0;
    }

The fourteen short-pointer ``out`` arguments are how the static
function returns its computed state to the caller (:func:`phsettar`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.math_helpers import muldv
from dectalk.ph.numeric_constants import (
    A2,
    A3,
    A4,
    A5,
    A6,
    AB,
    AP,
    AV,
    B1,
    B2,
    B3,
    F1,
    FRAC_HALF,
    FRAC_ONE,
    TILT,
)
from dectalk.ph.phoneme_features import FOBST
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import inh_timing, phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL


@dataclass(slots=True)
class InitVariablesOut:
    """Aggregate of the fourteen out-parameters of :func:`init_variables`.

    The C signature passes fourteen ``short *`` pointers (and one
    ``short **``) so the function can write its initialised state
    back to the caller. The Python port collects them into a single
    mutable struct so :func:`phsettar` can destructure the result.

    Attributes:
        inhdr_frames: Inherent duration of the current phone in frames.
        shrink: ``FRAC_ONE``-scaled shrinkage factor for sonorants.
        shrif: Forward-transition shrink coefficient.
        shrib: Backward-transition shrink coefficient.
        pholas: Previous phone (``GEN_SIL`` if at the start).
        fealas: Feature bitmask of the previous phone.
        feacur: Feature bitmask of the current phone.
        feanex: Feature bitmask of the next phone.
        struclm2: Allofeats of the phone two positions back.
        struclas: Allofeats of the previous phone.
        struccur: Allofeats of the current phone.
        strucnex: Allofeats of the next phone.
        ndips_offset: Offset into ``dipspec[]`` where new diph info
            should be written (the C ``**ppsNdips`` argument).
        phonp2: Phone two positions ahead (``GEN_SIL`` near the end).
    """

    inhdr_frames: int = 0
    shrink: int = 0
    shrif: int = 0
    shrib: int = 0
    pholas: int = 0
    fealas: int = 0
    feacur: int = 0
    feanex: int = 0
    struclm2: int = 0
    struclas: int = 0
    struccur: int = 0
    strucnex: int = 0
    ndips_offset: int = 0
    phonp2: int = 0


def init_variables(phTTS: TtsHandle) -> InitVariablesOut:  # noqa: N803
    """Initialise per-phone transient state for :func:`phsettar`.

    Faithful translation of the static C helper. The fourteen C
    out-pointers are collapsed into a single :class:`InitVariablesOut`
    instance.

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must be
            a populated :class:`~dectalk.ph.dph_t.DphT` with
            ``pSTphsettar`` pointing at a
            :class:`~dectalk.ph.dph_settar_st.DphSettarSt`.

    Returns:
        Fresh :class:`InitVariablesOut` carrying the fourteen values
        the C source would have written through out-pointers.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    out = InitVariablesOut()

    if p_dph_t.nphone == 0:
        # First position of the clause: previous phone is silence,
        # struclm2 is zero by definition (no phone two positions back).
        out.struclm2 = 0
        out.pholas = GEN_SIL
        if p_dphsettar.initsw == 0:
            # Very first init since engine startup: seed every parameter's
            # tarend with the beginning target of phone 0. The C loop
            # variable IS ``pDphsettar->np`` (``for (pDphsettar->np =
            # &PF1; ...)``), and ``us_gettar`` derives ``npar`` /
            # ``par_type`` from it -- so np MUST track the seeded
            # parameter or every iteration resolves the same stale
            # slot. (Previously np was left stale here, seeding all
            # tarend cells with 0 and giving the first clause a
            # spurious onset ramp -- issue #269, the frame-3 formant
            # divergence of #268.)
            p_dphsettar.initsw += 1
            for idx in range(F1, TILT + 1):
                p_dphsettar.np = idx
                p_dph_t.param[idx].tarend = getbegtar(phTTS, 0)
    else:
        if p_dph_t.nphone > 1:
            out.struclm2 = p_dph_t.allofeats[p_dph_t.nphone - 2]
        out.pholas = p_dphsettar.phcur
        out.struclas = p_dph_t.allofeats[p_dph_t.nphone - 1]

    # Normal initialization of the per-phoneme transient state.
    p_dphsettar.phcur = p_dph_t.allophons[p_dph_t.nphone]
    out.struccur = p_dph_t.allofeats[p_dph_t.nphone]

    if p_dph_t.nphone < (p_dph_t.nallotot - 2):
        p_dphsettar.phonex = p_dph_t.allophons[p_dph_t.nphone + 1]
        out.strucnex = p_dph_t.allofeats[p_dph_t.nphone + 1]
    else:
        p_dphsettar.phonex = GEN_SIL
        out.strucnex = 0

    # The C source seeds the dipspec write pointer at &dipspec[1]; the
    # Python port uses an integer offset rather than a raw pointer.
    out.ndips_offset = 1

    # Pre-compute often-used phone feature lookups.
    out.fealas = phone_feature(out.pholas)
    out.feacur = phone_feature(p_dphsettar.phcur)
    out.feanex = phone_feature(p_dphsettar.phonex)

    out.inhdr_frames = mstofr(inh_timing(p_dphsettar.phcur))

    # Sonorant shrink coefficients. Only meaningful when the current
    # phone is not an obstruent and not silence. (The FRENCH branch of
    # the C uses FPLOSV / TFricative gating; this port is US-build.)
    if (out.feacur & FOBST) == 0 and p_dphsettar.phcur != GEN_SIL:
        if p_dph_t.durfon < (out.inhdr_frames << 1):
            out.shrink = muldv(FRAC_ONE, p_dph_t.durfon, out.inhdr_frames)
        else:
            out.shrink = FRAC_ONE + (FRAC_ONE - 1)
        out.shrif = (out.shrink >> 1) + FRAC_HALF
        out.shrib = out.shrif - 1600

    # Zero the per-parameter "special override" slots. The C source
    # writes PAV.tspesh through PTILT.tspesh by name; in Python the
    # parameters live in the param[] array.
    for idx in (AV, AP, B1, B2, B3, A2, A3, A4, A5, A6, AB, TILT):
        p_dph_t.param[idx].tspesh = 0

    # PAREAL.tspesh and PAREAB.tspesh are zeroed by phsettar's
    # prologue (before init_variables), not here. The C source does
    # zero PF1.tspesh inside init_variables, so we do too.
    p_dph_t.param[F1].tspesh = 0

    return out


__all__ = ["InitVariablesOut", "init_variables"]
