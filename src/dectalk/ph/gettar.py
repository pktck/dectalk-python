"""``gettar`` -- per-phone target-lookup dispatcher from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1879 (~80 lines).

The C function looks up the per-parameter target value for a given
phone, switching between per-language target tables (US English,
UK English, German, Latin American Spanish, Spanish, French) based
on the high bits (``PFONT``) of the phone index:

.. code-block:: c

    int gettar (LPTTS_HANDLE_T phTTS, int phone) {
        PKSD_T        pKsd_t = phTTS->pKernelShareData;
        PDPH_T        pDph_t = phTTS->pPHThreadData;
        PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
        int tmp, count = 0;
        short npar;
        int index[4] = {0, 1, 2, -1};
        int tartemp = 0;
        while (count <= 3) {
            ...
            tmp = get_phone(pDph_t, (phone + index[count]));
            tmp = tmp & PFONT;

            if (tmp != pDph_t->last_lang) {
                pDph_t->last_lang = tmp;
                if (tmp == (PFUSA << PSFONT)) {
                    pDph_t->p_diph = (short *)us_maldip /* or us_femdip */;
                    pDph_t->p_tar  = (short *)us_maltar /* or us_femtar */;
                    pDph_t->p_amp  = (short *)us_malamp /* or us_femamp */;
                }
                else if (tmp == (PFUK << PSFONT)) { ... }
                else if (tmp == (PFGR << PSFONT)) { ... }
                else if (tmp == (PFLA << PSFONT)) { ... }
                else if (tmp == (PFSP << PSFONT)) { ... }
                else if (tmp == (PFFR << PSFONT)) { ... }
            }
            ...
        }
        return (tartemp);
    }

The body re-points ``pDph_t->p_diph`` / ``p_tar`` / ``p_amp`` to the
correct per-language table on every language transition and then
returns the indexed target value.

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


def gettar(phTTS: TtsHandle, phone: int) -> int:  # noqa: N803 -- mirror C arg name
    """Look up the per-phone target value; routes through ``_capi``.

    Mirrors the C signature ``int gettar(LPTTS_HANDLE_T phTTS, int phone)``.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        phTTS: Two-pointer engine handle.
        phone: Index into the ``allophons[]`` buffer naming the phone
            whose target is wanted.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del phTTS, phone
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["gettar"]
