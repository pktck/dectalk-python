"""``filter_seg_commands`` two-pole IIR filter helper from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 2426-2465.

Applies a cascaded two-pole IIR filter to the segmental F0 target
(``pDphsettar->tarseg`` and ``tarseg1``), producing the smoothed
``pDph_t->f0s`` output. The filter state lives on
``pDphsettar->f0slas1`` / ``f0slas2``; the coefficients live on
``pDphsettar->f0sa1`` / ``f0sa2`` / ``f0sb``.

Despite the ``f0in`` parameter, the C body never reads it — the
function actually filters ``pDphsettar->tarseg`` (the comment in
the C source acknowledges the misnamed parameter).
"""

from __future__ import annotations

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import F0SHFT
from dectalk.ph.math_helpers import mlsh1


def filter_seg_commands(p_dph_t: DphT, f0in: int) -> None:
    """Convert ``tarseg`` to smoothed ``pDphsettar->f0s`` via 2-pole IIR.

    Faithful translation of:

    .. code-block:: c

        static void filter_seg_commands(PDPH_T pDph_t, short f0in) {
            short f0souta, f0soutb, f0soutc, f0soutd, f0sout1, f0sout2;
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            // First pole
            pDph_t->arg1 = pDphsettar->f0sa1;
            pDph_t->arg2 = pDphsettar->tarseg;
            f0souta = mlsh1(pDphsettar->f0sa1, pDphsettar->tarseg);
            pDph_t->arg1 = pDphsettar->f0sb;
            pDph_t->arg2 = pDphsettar->f0slas1;
            f0soutb = mlsh1(pDphsettar->f0sb, pDphsettar->f0slas1);
            f0sout1 = f0souta + f0soutb;
            pDphsettar->f0slas1 = f0sout1;
            // Second pole
            pDph_t->arg1 = pDphsettar->f0sa2;
            pDph_t->arg2 = f0sout1 + (pDphsettar->tarseg1 << F0SHFT);
            f0soutc = mlsh1(pDphsettar->f0sa2,
                            (f0sout1 + (pDphsettar->tarseg1 << F0SHFT)));
            pDph_t->arg1 = pDphsettar->f0sb;
            pDph_t->arg2 = pDphsettar->f0slas2;
            f0soutd = mlsh1(pDphsettar->f0sb, pDphsettar->f0slas2);
            f0sout2 = f0soutc + f0soutd;
            pDphsettar->f0slas2 = f0sout2;
            pDph_t->f0s = f0sout2 >> F0SHFT;
        }

    The ``arg1`` / ``arg2`` writes are vestigial debug traces in the
    C source (the original DECtalk debugger reads them); the Python
    port mirrors them faithfully so the field-write sequence is
    identical.

    The ``f0in`` parameter is unused — the C source's own comment
    says the parameter name is misleading; the actual input is
    ``pDphsettar->tarseg``.

    Args:
        p_dph_t: PH thread state (mutated in-place).
        f0in: Vestigial; unused in the C source and the port.
    """
    del f0in  # Unused in the C source — kept for ABI parity.
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    # First pole.
    p_dph_t.arg1 = pdphsettar.f0sa1
    p_dph_t.arg2 = pdphsettar.tarseg
    f0souta = mlsh1(pdphsettar.f0sa1, pdphsettar.tarseg)
    p_dph_t.arg1 = pdphsettar.f0sb
    p_dph_t.arg2 = pdphsettar.f0slas1
    f0soutb = mlsh1(pdphsettar.f0sb, pdphsettar.f0slas1)
    f0sout1 = f0souta + f0soutb
    pdphsettar.f0slas1 = f0sout1

    # Second pole.
    p_dph_t.arg1 = pdphsettar.f0sa2
    p_dph_t.arg2 = f0sout1 + (pdphsettar.tarseg1 << F0SHFT)
    f0soutc = mlsh1(pdphsettar.f0sa2, f0sout1 + (pdphsettar.tarseg1 << F0SHFT))
    p_dph_t.arg1 = pdphsettar.f0sb
    p_dph_t.arg2 = pdphsettar.f0slas2
    f0soutd = mlsh1(pdphsettar.f0sb, pdphsettar.f0slas2)
    f0sout2 = f0soutc + f0soutd
    pdphsettar.f0slas2 = f0sout2

    p_dph_t.f0s = f0sout2 >> F0SHFT


__all__ = ["filter_seg_commands"]
