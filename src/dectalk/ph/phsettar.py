"""``phsettar`` -- top-level target-setting pipeline from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 561 (~700 lines).

The C function is the top-level driver of the PH target-setting
stage: it runs once per phone, initialises state via
:func:`init_variables`, then loops over every formant / amplitude
parameter (F1..TILT) calling :func:`gettar`, :func:`getbegtar`,
:func:`getendtar`, and :func:`make_dip` to populate the
``PDPHSETTAR_ST`` smoothing-rule state used by the synth-back-end:

.. code-block:: c

    void phsettar (LPTTS_HANDLE_T phTTS)
    {
        short tmp = 0;
        short inhdr_frames = 0;
        short pholas = 0;
        short fealas = 0, feacur = 0, feanex = 0;
        ...
        init_variables (phTTS, &inhdr_frames, &pDph_t->shrink, ...);

        // Turn off breathyness switch at end of a phrase
        if ((pDphsettar->phcur == GEN_SIL)) {
            pDph_t->breathysw = 0;
        }
        ...
        // Main loop: For each parameter, set target and transition specs
        // F1, F2, F3, FZ, B1, B2, B3, AV, AP, A2, A3, A4, A5, A6, AB, TILT
        for (pDphsettar->np = &PF1; pDphsettar->np <= &PTILT;
             pDphsettar->np++) {
            ...
            pDphsettar->np->tarnex = getbegtar(phTTS,
                                               (pDph_t->nphone + 1));
            ...
            pDphsettar->np->tarcur = gettar(phTTS, pDph_t->nphone);
            ...
            if (pDphsettar->np->tarcur < -1) {
                make_dip(pDph_t, ..., &ndips);
            }
            ...
        }
    }

This is a ~700-line orchestration function that depends on every
target/locus/coarticulation helper in the file plus the
``PDPHSETTAR_ST`` struct layout.

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

from dectalk.ph.tts_handle import TtsHandle


def phsettar(phTTS: TtsHandle) -> None:  # noqa: N803 -- mirror C arg name
    """Run the per-phone target-setting pipeline; routes through ``_capi``.

    Mirrors the C signature ``void phsettar(LPTTS_HANDLE_T phTTS)``.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        phTTS: Two-pointer engine handle (kernel-shared + PH-thread
            data). Ignored by the shim.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del phTTS  # Unused: the shim never inspects engine state.
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["phsettar"]
