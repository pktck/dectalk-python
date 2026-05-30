r"""``filter_commands`` two-pole critically-damped F0 smoother.

Translated from ``src/dapi/src/ph/ph_drwt01.c`` lines 3221-3274 — the
**active** (``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING``, ``HLSYN``
*undefined*) build's F0 command filter. This is the second of the two
``filter_commands`` definitions in ``ph_drwt01.c``; the first
(line 2102) is the ``NWSNOAA`` / ``ENGLISH_UK`` variant and is not
compiled for US English.

Unlike the HLSYN ``ph_drwt02.c`` build — whose ``filter_commands``
collapsed to a single-pole ``f0 += (f0in - f0) >> 2`` smoother with the
segmental fast-gesture handled by a *separate* ``filter_seg_commands``
two-pole — the production build folds everything into one cascaded
two-pole filter:

.. math::

    f0_{out1} &= \mathrm{mlsh1}(f0a1, f0in) + \mathrm{mlsh1}(f0b, f0las1) \\
    f0_{out2} &= \mathrm{mlsh1}(f0a2, f0_{out1} + (tarseg1 \ll F0SHFT))
                 + \mathrm{mlsh1}(f0b, f0las2) \\
    f0 &= f0_{out2} \gg F0SHFT

The fast segmental gesture ``tarseg1`` is injected into the second
pole's input (``<< F0SHFT``); the slow segmental target ``tarseg`` is
already mixed into ``f0in`` by the caller (``pht0draw``). There is no
separate ``f0s`` / ``filter_seg_commands`` stage and no ``f0 + f0s``
recombination in the production build — ``f0prime`` is set to ``f0``
directly here.

The coefficients are configured once in ``pht0draw``'s hard-init
(``ph_drwt01.c`` lines 2433-2435)::

    f0a2 = f0_lp_filter;  f0b = FRAC_ONE - f0_lp_filter;  f0a1 = f0a2 << F0SHFT

and the filter memories ``f0las1`` / ``f0las2`` are primed to the
baseline (``f0beginfall << F0SHFT``) at every hard/soft init so the
contour starts at the declination baseline rather than zero. This
priming is what makes the two-pole filter the dominant F0 dynamic-range
driver: without it the smoothed output collapses toward a flat line.
"""

from __future__ import annotations

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import F0SHFT
from dectalk.ph.math_helpers import mlsh1

_INT16_MASK = 0xFFFF
_INT16_SIGN = 0x8000


def _s16(x: int) -> int:
    """Truncate to 16-bit signed, matching a C ``short`` assignment."""
    x &= _INT16_MASK
    return x - (_INT16_MASK + 1) if x & _INT16_SIGN else x


def filter_commands(p_dph_t: DphT, f0in: int) -> None:
    """Convert the ``f0in`` command stream to a smoothed ``f0`` / ``f0prime``.

    Faithful translation of:

    .. code-block:: c

        static void filter_commands (PDPH_T pDph_t, short f0in)
        {
            short f0outa, f0outb, f0outc, f0outd, f0out1, f0out2;
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            /* First pole (separate into 2 poles to min truncation errors) */
            f0outa = mlsh1 (pDphsettar->f0a1, f0in);
            f0outb = mlsh1 (pDphsettar->f0b, pDphsettar->f0las1);
            f0out1 = f0outa + f0outb;
            pDphsettar->f0las1 = f0out1;
            /* Second pole */
            f0outc = mlsh1 (pDphsettar->f0a2,
                            f0out1 + (pDphsettar->tarseg1 << F0SHFT));  /* one pole */
            f0outd = mlsh1 (pDphsettar->f0b, pDphsettar->f0las2);
            f0out2 = f0outc + f0outd;
            pDphsettar->f0las2 = f0out2;
            pDph_t->f0 = f0out2 >> F0SHFT;       /* Unscaled fundamental frequency */
            pDph_t->f0prime = pDph_t->f0;        /* This is going to be scaled  */
        }

    The ``arg1`` / ``arg2`` writes are vestigial DECtalk-debugger traces
    in the C source; mirrored here so the field-write sequence matches
    the sibling ``filter_seg_commands`` port. The pole sums are truncated
    back to 16-bit signed (the C ``f0out1`` / ``f0out2`` are ``short``)
    so high-F0 transients wrap identically to the C build.

    Args:
        p_dph_t: PH thread state. Reads the filter coefficients and
            memories off ``p_dph_t.pSTphsettar`` (``f0a1`` / ``f0a2`` /
            ``f0b`` / ``f0las1`` / ``f0las2`` / ``tarseg1``); writes the
            smoothed ``p_dph_t.f0`` and ``p_dph_t.f0prime``.
        f0in: The composed F0 command input
            (``tarbas + tarhat + tarimp + tarseg``).
    """
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    # First pole (split into 2 poles to minimise truncation errors).
    p_dph_t.arg1 = pdphsettar.f0a1
    p_dph_t.arg2 = f0in
    f0outa = mlsh1(pdphsettar.f0a1, f0in)
    p_dph_t.arg1 = pdphsettar.f0b
    p_dph_t.arg2 = pdphsettar.f0las1
    f0outb = mlsh1(pdphsettar.f0b, pdphsettar.f0las1)
    f0out1 = _s16(f0outa + f0outb)
    pdphsettar.f0las1 = f0out1

    # Second pole. The fast segmental gesture tarseg1 enters here.
    p_dph_t.arg1 = pdphsettar.f0a2
    p_dph_t.arg2 = f0out1 + (pdphsettar.tarseg1 << F0SHFT)
    f0outc = mlsh1(pdphsettar.f0a2, f0out1 + (pdphsettar.tarseg1 << F0SHFT))
    p_dph_t.arg1 = pdphsettar.f0b
    p_dph_t.arg2 = pdphsettar.f0las2
    f0outd = mlsh1(pdphsettar.f0b, pdphsettar.f0las2)
    f0out2 = _s16(f0outc + f0outd)
    pdphsettar.f0las2 = f0out2

    p_dph_t.f0 = f0out2 >> F0SHFT  # Unscaled fundamental frequency.
    p_dph_t.f0prime = p_dph_t.f0  # Scaled later by pht0draw.


__all__ = ["filter_commands"]
