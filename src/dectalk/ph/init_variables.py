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

This module is an **architectural shim**: the Python ``dectalk.speak``
and ``dectalk.to_wav`` paths route the PH stage through
``dectalk._capi.CAPI`` for byte-identical audio, so the actual
algorithm lives in the C library; this file documents the C-source
location and signature so the inventory enumerator sees a Python
symbol and the deferred reason stays accurate.

See Phase E in
``/root/.claude/plans/create-a-python-port-smooth-hoare.md`` for the
roadmap to a fully Python implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from dectalk.ph.tts_handle import TtsHandle


@dataclass(slots=True)
class InitVariablesOut:
    """Aggregate of the fourteen out-parameters of :func:`init_variables`.

    The C signature passes fourteen ``short *`` pointers (and one
    ``short **``) so the function can write its initialised state
    back to the caller. The Python port collects them into a single
    mutable struct; once the body is implemented, fields land here.

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

    Mirrors the C signature ``static void init_variables(
    LPTTS_HANDLE_T, short *psInhdr_frames, short *psShrink,
    short *psShrif, short *psShrib, short *psPholas, short *psFealas,
    short *psFeacur, short *psFeanex, short *psStruclm2,
    short *psStruclas, short *psStruccur, short *psStrucnex,
    short **ppsNdips, short *psPhonp2)`` -- the fourteen out-pointers
    are collapsed into a single :class:`InitVariablesOut`.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        phTTS: Two-pointer engine handle.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del phTTS
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["InitVariablesOut", "init_variables"]
