"""``all_phsort`` -- multi-language PH-sort engine from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` line 428 (~1284 lines).

The C function is the default per-language entry into the PH-sort
pipeline for every language except French; French has its own
:func:`fr_phsort` engine. The dispatcher :func:`phsort` selects
between them based on ``pKsd_t->lang_curr``:

.. code-block:: c

    int all_phsort (LPTTS_HANDLE_T phTTS)
    {
        PKSD_T        pKsd_t = phTTS->pKernelShareData;
        PDPH_T        pDph_t = phTTS->pPHThreadData;
        PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
        ...
        /* Main loop 1: Clean up input string re mis-orderings & */
        /*              extra boundaries                          */
        pDph_t->nphonetot = 0;
        ...
        /* Per-language branches: GERMAN, SPANISH, ENGLISH_US,    */
        /* ENGLISH_UK, LATIN, ...                                 */
    }

This is a 1284-line state machine with several preprocessor-gated
language-specific branches (US English, UK English, German, Spanish,
Latin American Spanish) plus shared phone-rewriting / stress-
assignment passes. Porting it requires the unported phone-rewrite
helpers, the stress-state machine, plus a large per-language
phoneme rule table.

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


def all_phsort(phTTS: TtsHandle) -> int:  # noqa: N803 -- mirror C arg name
    """Default per-language PH-sort entry; routes through ``_capi``.

    Mirrors the C signature ``int all_phsort(LPTTS_HANDLE_T phTTS)``.

    The Python pipeline currently delegates the PH-sort stage to
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


__all__ = ["all_phsort"]
