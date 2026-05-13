"""``setloc`` -- static locus-computation helper from ph_sttr2.c.

Translated from ``src/dapi/src/ph/ph_sttr2.c`` line 69 (~200 lines).

The C function is a ``static short`` helper used by :func:`phsettar`
to compute formant-transition locus frequencies at obstruent /
sonorant boundaries:

.. code-block:: c

    static short setloc (LPTTS_HANDLE_T phTTS,
                         short nfonobst,    /* Segment thought to be an obstruent */
                         short nfonsonor,   /* Segment thought to be a sonorant   */
                         char  initfinso,   /* 'i' if use init part of sonor      */
                         short nfonvowel,   /* Segment (vowel?) other side of obst */
                         short feanex)
    {
        ...
        if ((pDphsettar->np > &PF3) || (typob != OBSTRUENT)
            || (typso == OBSTRUENT))
        {
            return (0);  /* Not obstruent-sonorant tran, as assumed */
        }
        ...
        /* Per-language tables: us_maleloc/us_femloc, uk_*, gr_*,
         * la_*, sp_*, fr_*; each indexes plocu[] then locus[] +
         * percent-toward-V + tran-dur-msec.
         */
        ...
        delta_freq = muldv (tmp, (curval - locus), 100);
        pDphsettar->bouval = locus + delta_freq;

        /* V-V coarticulation across an obst consonant */
        if (((phone_feature(pDph_t, fonsonor) & FVOWEL) IS_PLUS) && ...)
        ...
        return (0);
    }

The function leans on six per-language locus tables, the
``plocu`` lookup, ``shrdur`` / ``vv_coartic_across_c`` /
``getbegtar`` / ``getendtar`` / ``get_phone`` helpers, plus the
``PDPHSETTAR_ST`` parameter state.

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


def setloc(
    phTTS: TtsHandle,  # noqa: N803 — mirror the C argument name
    nfonobst: int,
    nfonsonor: int,
    initfinso: str,
    nfonvowel: int,
    feanex: int,
) -> int:
    """Compute formant-transition locus for an obstruent/sonorant boundary.

    Mirrors the C signature ``static short setloc(LPTTS_HANDLE_T, short,
    short, char, short, short)``.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        phTTS: Two-pointer engine handle.
        nfonobst: Segment thought to be an obstruent (phone index).
        nfonsonor: Segment thought to be a sonorant (phone index).
        initfinso: ``'i'`` to use the init part of the sonorant,
            otherwise the end.
        nfonvowel: Segment (likely vowel) on the other side of the
            obstruent.
        feanex: Feature bitmask of the next phone.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del phTTS, nfonobst, nfonsonor, initfinso, nfonvowel, feanex
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["setloc"]
