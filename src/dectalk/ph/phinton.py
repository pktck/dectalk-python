"""``phinton`` -- intonation-engine entry point from ph_inton2.c.

Translated from ``src/dapi/src/ph/ph_inton2.c`` line 216 (~2080 lines).

The C function is the main per-clause intonation engine: it walks
the clause's phone / boundary stream, computes per-phone F0 rise /
fall / hat targets, and emits the F0 command stream that
:func:`make_f0_command` and :func:`f0_intonation` consume:

.. code-block:: c

    void phinton (LPTTS_HANDLE_T phTTS)
    {
        PKSD_T  pKsd_t = phTTS->pKernelShareData;
        PDPH_T  pDph_t = phTTS->pPHThreadData;
        int     temp;
        PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;

        short F0_CBOUND_PULSE;
        short SCHWA1;
        short SCHWA2;
        short F0_QGesture1;
        short F0_QGesture2;
        short F0_CGesture1;
        short F0_CGesture2;
        short GEST_SHIFT;
        short MAX_NRISES;
        short F0_FINAL_FALL;
        short F0_NON_FINAL_FALL;
        short F0_QSYLL_FALL;
        short F0_GLOTTALIZE;
        short Reduce_last;
        short F0_COMMA_FALL;

        /* Per-language F0 rise / phrase-position tables                    */
        /* (gr_f0_mphrase_position, gr_f0_fphrase_position,                 */
        /*  gr_f0_mstress_level, ...).                                      */
        ...
        /* hat-state machine over rises / falls,                            */
        /* declarative vs. question vs. comma cadences,                     */
        /* stress-level driven F0 deltas (EMPH_FALL / DELTARISE / ...).     */
        ...
    }

This is a ~2080-line engine that subsumes every F0 helper in
``ph_inton2.c`` (peak / declination / glottalisation / hat / question
behaviours) plus the per-language stress-level and phrase-position
tables.

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


def phinton(phTTS: TtsHandle) -> None:  # noqa: N803 -- mirror C arg name
    """Run the per-clause intonation engine; routes through ``_capi``.

    Mirrors the C signature ``void phinton(LPTTS_HANDLE_T phTTS)``.

    The Python pipeline currently delegates the PH intonation stage
    to ``dectalk._capi.CAPI`` for byte-identical output against the
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


__all__ = ["phinton"]
