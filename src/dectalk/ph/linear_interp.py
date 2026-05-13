"""``linear_interp`` singing-mode F0 interpolation helper from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 2479-2517.

Linearly interpolates between ``pDphsettar->f0start`` and
``pDphsettar->newnote`` by accumulating ``pDphsettar->delnote`` into
``pDphsettar->delcum`` once per call, producing the next ``pDph_t->f0``
sample. Clamps the contour so it never overshoots ``newnote`` (handling
positive and negative ``delnote`` separately). When ``vibsw == 1``
(singing mode), adds a 6.2 Hz / +/- 2.05 Hz vibrato to ``f0prime``
sampled from the 64-entry ``getcosine`` lookup table.

The C source has a ``#ifdef TOMBUCHLER`` debug switch that forces
``vibsw = 1`` unconditionally; that build flag is not defined in our
Linux build, so the write is skipped.
"""

from __future__ import annotations

from dectalk.ph.cosine_tilt_tables import getcosine_tab
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import TWOPI


def linear_interp(p_dph_t: DphT) -> None:
    """Advance the singing-mode F0 contour by one frame.

    Faithful translation of:

    .. code-block:: c

        static void linear_interp(PDPH_T pDph_t) {
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            pDphsettar->delcum += pDphsettar->delnote;
            pDph_t->f0 = pDphsettar->f0start + (pDphsettar->delcum >> 2);
        #ifdef TOMBUCHLER
            pDphsettar->vibsw = 1;
        #endif
            if (pDphsettar->delnote >= 0) {
                if (pDph_t->f0 > pDphsettar->newnote) {
                    pDph_t->f0 = pDphsettar->newnote;
                    pDphsettar->f0start = pDphsettar->newnote;
                    pDphsettar->delcum = 0;
                    pDphsettar->delnote = 0;
                }
            } else {
                if (pDph_t->f0 < pDphsettar->newnote) {
                    pDph_t->f0 = pDphsettar->newnote;
                    pDphsettar->f0start = pDphsettar->newnote;
                    pDphsettar->delcum = 0;
                    pDphsettar->delnote = 0;
                }
            }
            pDph_t->f0prime = pDph_t->f0;
            if (pDphsettar->vibsw == 1) {
                pDphsettar->timecosvib += 165;
                if (pDphsettar->timecosvib > TWOPI)
                    pDphsettar->timecosvib -= TWOPI;
                pDph_t->f0prime += getcosine[pDphsettar->timecosvib>>6] >> 3;
            }
        }

    The ``getcosine`` reference in the C body is the 64-entry signed-short
    ``getcosine[]`` LUT from ``ph_romi.c`` (mirrored as
    :data:`~dectalk.ph.cosine_tilt_tables.getcosine_tab` here), NOT the
    finer-grained ``getcosine()`` *function* in
    :mod:`dectalk.ph.getcosine`. The C source declares both with the same
    name (``extern short getcosine[]`` and ``int getcosine(short)``)
    because of an early-DECtalk redesign that turned the function into a
    table; the function form survives only in ``ph_drwt01.c``.

    The ``#ifdef TOMBUCHLER`` debug switch is not defined in our Linux
    build, so the unconditional ``vibsw = 1`` write inside it is skipped.

    Args:
        p_dph_t: PH thread state (mutated in-place).
    """
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    pdphsettar.delcum += pdphsettar.delnote
    p_dph_t.f0 = pdphsettar.f0start + (pdphsettar.delcum >> 2)

    if pdphsettar.delnote >= 0:
        # Do not overshoot pDphsettar->newnote.
        if p_dph_t.f0 > pdphsettar.newnote:
            p_dph_t.f0 = pdphsettar.newnote
            pdphsettar.f0start = pdphsettar.newnote
            pdphsettar.delcum = 0
            pdphsettar.delnote = 0
    elif p_dph_t.f0 < pdphsettar.newnote:
        p_dph_t.f0 = pdphsettar.newnote
        pdphsettar.f0start = pdphsettar.newnote
        pdphsettar.delcum = 0
        pdphsettar.delnote = 0

    p_dph_t.f0prime = p_dph_t.f0  # To be scaled by spdef.

    if pdphsettar.vibsw == 1:
        # Singing: add vibrato of 6.2 Hz (25 frames/cycle), +/- 2.05 Hz ampl.
        pdphsettar.timecosvib += 165
        if pdphsettar.timecosvib > TWOPI:
            pdphsettar.timecosvib -= TWOPI
        p_dph_t.f0prime += getcosine_tab[pdphsettar.timecosvib >> 6] >> 3


__all__ = ["linear_interp"]
