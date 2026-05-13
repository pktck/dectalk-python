"""``shrdur`` duration-shrinker helper from ph_sttr2.c.

Translated from ``src/dapi/src/ph/ph_sttr2.c`` lines 406-449.

Used by the timing pass to fold a duration around its midpoint
and shrink it toward the centre. The algorithm:

1. Convert ``durin`` from ms to frame-quanta (``* NSAMP_FRAME``).
2. Fold around ``halfinhdr`` so very-long durations are mirrored
   to very-short ones.
3. Apply half the requested shrink (in Q14 fixed-point).
4. Clamp to ``halfmaxdur`` (full shrink applied).
5. Convert back to true time, un-fold if the original was past
   ``halfinhdr``, and clamp the result to ``NSAMP_FRAME`` minimum.

Returns the result divided by 64 (the ms-to-frame quanta).
"""

from __future__ import annotations

from dectalk.ph.math_helpers import mlsh1
from dectalk.ph.numeric_constants import FRAC_ONE, NSAMP_FRAME

_S16_MASK = 0xFFFF


def _to_s16_unsigned(x: int) -> int:
    """Return ``x`` interpreted as an unsigned 16-bit value.

    The C source does ``((unsigned) shrink + FRAC_ONE) >> 1`` —
    casting to unsigned removes the sign bit before the shift.
    """
    return x & _S16_MASK


def shrdur(durin: int, inhdr_frames: int, shrink: int) -> int:
    """Shrink a duration toward the centre of its inhdr window.

    Faithful translation of:

    .. code-block:: c

        static int shrdur(PDPH_T pDph_t, short durin, short inhdr_frames,
                          short shrink) {
            short halfinhdr, halfmaxdur, foldswitch, localinhdr;
            durin = (durin * 10) + 5;
            localinhdr = inhdr_frames * NSAMP_FRAME;
            halfinhdr = inhdr_frames * NSAMP_FRAME >> 1;
            halfmaxdur = mlsh1(halfinhdr, shrink);

            foldswitch = 0;
            if (durin > halfinhdr) {
                durin = localinhdr - durin;
                foldswitch = 1;
            }
            durin = halfinhdr - durin;
            durin = mlsh1(((unsigned) shrink + FRAC_ONE) >> 1, durin);
            if (durin > halfmaxdur) durin = halfmaxdur;
            durin = halfmaxdur - durin;
            if (foldswitch == 1) durin = halfmaxdur + halfmaxdur - durin;
            if (durin < NSAMP_FRAME) durin = NSAMP_FRAME;
            return durin >> 6;
        }

    The ``pDph_t`` argument is unused (the C source uses it for
    debug-tracing through commented-out ``pDph_t->arg1`` writes).

    Args:
        durin: Input duration in milliseconds.
        inhdr_frames: Inherent-duration frame count for the phone.
        shrink: Q14 shrink ratio in ``[0, FRAC_ONE]``.

    Returns:
        Shrunk duration in frame quanta (``>> 6`` of the internal
        fold value).
    """
    durin = (durin * 10) + 5
    localinhdr = inhdr_frames * NSAMP_FRAME
    halfinhdr = localinhdr >> 1
    halfmaxdur = mlsh1(halfinhdr, shrink)

    foldswitch = 0
    if durin > halfinhdr:
        durin = localinhdr - durin
        foldswitch = 1

    durin = halfinhdr - durin
    durin = mlsh1((_to_s16_unsigned(shrink) + FRAC_ONE) >> 1, durin)

    durin = min(durin, halfmaxdur)

    durin = halfmaxdur - durin
    if foldswitch == 1:
        durin = halfmaxdur + halfmaxdur - durin

    durin = max(durin, NSAMP_FRAME)
    return durin >> 6


__all__ = ["shrdur"]
