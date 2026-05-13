"""``getbegtar`` -- beginning-of-phone target lookup from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1293 (~65 lines).

The C function returns the target value at the beginning of a
phone, including coarticulatory shifts from adjacent phones. For
diphthongised vowels (target < -1), it dereferences the diph table
and applies a per-language ``*_special_coartic`` adjustment:

.. code-block:: c

    short getbegtar (LPTTS_HANDLE_T phTTS, int nfone)
    {
        short                 temp, tmp;
        PDPH_T                pDph_t = phTTS->pPHThreadData;
        PDPHSETTAR_ST         pDphsettar = pDph_t->pSTphsettar;

        temp = gettar (phTTS, nfone);

        if (temp < -1)
        {
            /* If next seg diphthong, use diph first value */
            temp = pDph_t->p_diph[-temp];
            if (pDphsettar->par_type IS_FORM_FREQ)
            {
                tmp = get_phone(pDph_t, nfone);
                tmp = nfone & PFONT;
                if (tmp == PFUSA<<PSFONT) {
                    temp += us_special_coartic(pDph_t, (short)nfone, 0);
                }
                else if (tmp == PFGR<<PSFONT) { ... }
                else if (tmp == PFLA<<PSFONT) { ... }
                else if (tmp == PFSP<<PSFONT) { ... }
                else if (tmp == PFFR<<PSFONT) { /* commented out */ }
            }
        }
        return (temp);
    }

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


def getbegtar(phTTS: TtsHandle, nfone: int) -> int:  # noqa: N803 -- mirror C arg name
    """Beginning-of-phone target lookup; routes through ``_capi``.

    Mirrors the C signature ``short getbegtar(LPTTS_HANDLE_T phTTS,
    int nfone)``.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        phTTS: Two-pointer engine handle.
        nfone: Index into the ``allophons[]`` buffer naming the phone
            whose beginning target is wanted.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del phTTS, nfone
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["getbegtar"]
