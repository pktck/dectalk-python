"""``fr_phsort`` -- French-specific PH-sort engine from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` line 286 (~140 lines).

The C function is the French-only counterpart to :func:`all_phsort`:
when ``pKsd_t->lang_curr == LANG_french`` the :func:`phsort` dispatcher
routes here instead of into the all-languages engine. The body
performs a per-clause sweep that:

.. code-block:: c

    int fr_phsort (LPTTS_HANDLE_T phTTS)
    {
        PKSD_T        pKsd_t = phTTS->pKernelShareData;
        PDPH_T        pDph_t = phTTS->pPHThreadData;
        PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
        short *cp;
        short tmp;
        ...
        /* French-specific cleanup, durations, stress, F0 commands */
        return TRUE;
    } // phsort () for FRENCH

French is the only language with its own per-language sort engine
in the C source; every other language goes through
:func:`all_phsort`.

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


def fr_phsort(phTTS: TtsHandle) -> int:  # noqa: N803 -- mirror C arg name
    """French-specific PH-sort entry; routes through ``_capi``.

    Mirrors the C signature ``int fr_phsort(LPTTS_HANDLE_T phTTS)``.

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


__all__ = ["fr_phsort"]
