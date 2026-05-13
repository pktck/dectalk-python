r"""``filter_commands`` one-pole F0 smoother from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 2374-2412.

Smooths the F0 command stream by applying a single-pole IIR
filter:

.. math::

    f0_n = f0_{n-1} + \frac{f0_{in} - f0_{n-1}}{4}

The cascaded two-pole structure (``f0a1`` / ``f0a2`` / ``f0b``
coefficients with ``f0las1`` / ``f0las2`` state) is preserved as
commented-out code in the C source — every active code path was
collapsed to this single-line first-order smoother with a 1/4
step coefficient (a time constant of 4 frames).
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT


def filter_commands(p_dph_t: DphT, f0in: int) -> None:
    """Apply ``f0 += (f0in - f0) >> 2`` to smooth the F0 command stream.

    Faithful translation of:

    .. code-block:: c

        static void filter_commands(PDPH_T pDph_t, short f0in) {
            // The two-pole IIR is commented out; only one line is
            // active in the C source:
            pDph_t->f0 += (f0in - pDph_t->f0) >> 2;
        }

    The arithmetic-shift-right by 2 matches the C source's signed
    division: when ``f0in - f0`` is negative, Python's ``>>``
    rounds toward negative infinity (same as C on two's-complement
    platforms with arithmetic shifts), so the result stays bit-
    identical to the C build's behaviour on x86/ARM.

    Args:
        p_dph_t: PH thread state (mutated in-place).
        f0in: New F0 command target.
    """
    p_dph_t.f0 += (f0in - p_dph_t.f0) >> 2


__all__ = ["filter_commands"]
