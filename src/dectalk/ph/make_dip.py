"""``make_dip`` -- static parameter-dip generator from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1429 (~330 lines).

The C function generates the diphthongisation "dip" (sequence of
straight-line segments) for a parameter on a diphthongised vowel.
It walks each ``<value, time>`` pair in the diphthong table,
applies general and per-language ``*_special_coartic`` coarticulation
rules, calls :func:`shrdur` to scale transition durations relative
to the phone's inherent duration, and writes the resulting
per-frame increments and segment durations into ``dipspec[]``:

.. code-block:: c

    static void make_dip (PDPH_T pDph_t,
              short pdip,             /* Pointer to diphthongization info */
              short inhdr_frames,
              short shrink,
              short struccur,
              short **ppsNdips)
    {
        short         temp, dip_pos, tmp;
        short         dipsw;
        short         oldvalue, newvalue, oldtime, newtime;
        PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;

        pDphsettar->np->ndip = *ppsNdips;
        oldvalue = pDph_t->p_diph[pdip];

        /* Formant frequency coarticulation rules */
        if (pDphsettar->par_type IS_FORM_FREQ)
        {
            pDphsettar->gencoartic = N10PRCNT;
            if ((struccur & FSTRESS) IS_MINUS)
            {
                pDphsettar->gencoartic = N15PRCNT;
                if (pDphsettar->np == &PF2) {
                    pDphsettar->gencoartic = N25PRCNT;
                }
            }
            ...
            oldvalue += mlsh1(...);
            /* Per-language special_coartic for first dip pos */
            ...
        }
        pDphsettar->np->tarcur = oldvalue;

        /* Process each <value, time> of diph definition */
        dipsw = 0;
        do {
            ...
            if (newtime != -1) {
                newtime = shrdur(pDph_t, newtime, inhdr_frames, shrink);
            } else {
                newtime = pDph_t->durfon;
            }
            *(*ppsNdips)++ = newtime;
            ...
            /* Compute increment/frame during transition */
            ...
            (*ppsNdips)++;
        }
        while (pDph_t->p_diph[pdip++] != -1);

        pDphsettar->np->tarend = newvalue;
        pDphsettar->np->durlin = *pDphsettar->np->ndip++;
        pDphsettar->np->deldip = *pDphsettar->np->ndip++;
    }

The function depends on the ``PARAMETER`` struct layout, the
``mlsh1`` / ``muldv`` / ``shrdur`` helpers, the per-language
``*_special_coartic`` family, and the ``divtab`` lookup table.

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

from dectalk.ph.dph_t import DphT


def make_dip(
    p_dph_t: DphT,
    pdip: int,
    inhdr_frames: int,
    shrink: int,
    struccur: int,
    pps_ndips: list[int],
) -> None:
    """Generate the diphthong "dip" sequence for the current parameter.

    Mirrors the C signature ``static void make_dip(PDPH_T pDph_t,
    short pdip, short inhdr_frames, short shrink, short struccur,
    short **ppsNdips)``. The C ``short **ppsNdips`` argument is the
    write pointer into ``dipspec[]``; the Python port models it as a
    single-element list cell holding the current offset.

    The Python pipeline currently delegates the PH-targets stage to
    ``dectalk._capi.CAPI`` for byte-identical output against the
    reference C binary; calling this shim directly raises
    :class:`NotImplementedError` to make that delegation explicit at
    the call site.

    Args:
        p_dph_t: PH thread state.
        pdip: Index of the first diphthong entry in ``p_diph[]``.
        inhdr_frames: Inherent duration of the current phone in
            frames (from :func:`init_variables`).
        shrink: Sonorant-duration shrinkage factor (FRAC_ONE-scaled).
        struccur: Allofeats bitmask of the current phone.
        pps_ndips: Single-element list cell holding the current
            offset into ``dipspec[]`` -- mirrors C's
            ``short **ppsNdips``.

    Raises:
        NotImplementedError: Always. The byte-identical audio path
            routes through :mod:`dectalk._capi`; see Phase E in
            ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
    """
    del p_dph_t, pdip, inhdr_frames, shrink, struccur, pps_ndips
    raise NotImplementedError(
        "Routes through dectalk._capi for byte-identical audio; "
        "see Phase E in /root/.claude/plans/create-a-python-port-smooth-hoare.md"
    )


__all__ = ["make_dip"]
