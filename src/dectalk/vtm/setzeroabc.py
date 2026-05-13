"""``setzeroabc`` antiresonator-coefficient helper from vtm3.c.

Translated from ``src/dapi/src/vtm/vtm3.c`` lines 2395-2434.

Converts a (frequency, bandwidth, zero-gain) triple to the three
antiresonator filter coefficients used by the Klatt synthesiser for
nasal / fricative zeros. The algorithm first builds the equivalent
*resonator* coefficients (a, b, c) and then inverts the response by
forming (a' = 1/a, b' = -b/a, c' = -c/a) -- the standard 2-pole-to-
2-zero transform applied at gain ``rnzg``.

The numerical recipe (verbatim from the C comments):

1.  ``r = radius_table[bw >> 3]``  -- pole radius from
    ``4096 * exp(-pi * bw / 10000)`` lookup.
2.  ``ccoef = -frac4mul(r, r)``    -- ``-r**2`` in Q12.
3.  ``bcoef = frac4mul(r, cosine_table[f >> 3])`` -- ``r * 2*cos(2 pi f t)``
    in Q12 (the cosine LUT already encodes the factor of 2).
4.  ``acoef = 4096 - bcoef - ccoef`` -- ``1.0 - b - c`` in Q12.
5.  Divide each by ``acoef`` and scale by ``rnzg``; negate ``b`` and
    ``c``. ``acoef`` itself becomes ``4096 * rnzg / acoef``.

The divisions truncate toward zero (C ``/`` semantics) -- the
:func:`_c_div` helper below preserves that under Python's floor-div
default.

The C source notes the divides are a candidate for chip-side
table-isation; we keep them as native integer divides because the
Python port is not target-cycle-constrained.
"""

from __future__ import annotations

from dectalk.vtm.cosine_radius_tables import cosine_table, radius_table
from dectalk.vtm.frac import frac4mul


def _c_div(a: int, b: int) -> int:
    """Return ``a / b`` with C truncate-toward-zero integer semantics.

    Python's ``//`` floors, so ``(-7) // 3 == -3`` while C's ``/``
    truncates toward zero (``-7 / 3 == -2``). The helper restores C
    behaviour by dividing absolute values and reattaching the sign of
    the mathematical quotient.
    """
    if (a < 0) ^ (b < 0):
        return -(abs(a) // abs(b))
    return abs(a) // abs(b)


def setzeroabc(f: int, bw: int, rnzg: int) -> tuple[int, int, int]:
    """Return ``(sacoef, sbcoef, sccoef)`` antiresonator coefficients.

    Faithful translation of:

    .. code-block:: c

        void setzeroabc(int f, int bw, int rnzg,
                        short *sacoef, short *sbcoef, short *sccoef) {
            S16 acoef;
            S16 bcoef;
            S16 ccoef;
            S16 r;

            /* First compute ordinary resonator coefficients */
            /* Let r = exp(-pi bw t) */
            r = radius_table[bw >> 3];

            /* Let c = -r**2 */
            ccoef = -frac4mul(r, r);

            /* Let b = r * 2*cos(2 pi f t) */
            bcoef = frac4mul(r, cosine_table[f >> 3]);

            /* Let a = 1.0 - b - c */
            acoef = 4096 - bcoef - ccoef;

            /* Now convert to antiresonator coefficients
               (a' = 1/a, b' = -b/a, c' = -c/a) */
            *sacoef =  ((4096 * rnzg) / acoef);
            *sbcoef = -((bcoef  * rnzg) / acoef);
            *sccoef = -((ccoef  * rnzg) / acoef);
        }

    The 3 ``short *`` output parameters are collapsed into a returned
    tuple. Callers in the porting effort should re-bind locals from
    that tuple rather than via pointer aliasing.

    Args:
        f: Centre frequency in Hz of the zero. Scaled to the
            :data:`~dectalk.vtm.cosine_radius_tables.cosine_table`
            index by ``f >> 3``.
        bw: Bandwidth in Hz of the zero. Scaled to the
            :data:`~dectalk.vtm.cosine_radius_tables.radius_table`
            index by ``bw >> 3``.
        rnzg: Nasal-zero gain in Q12 (``4096`` represents unity
            gain). The output is scaled by this factor so the zero's
            DC gain matches the caller's intent.

    Returns:
        ``(sacoef, sbcoef, sccoef)`` -- the three antiresonator
        coefficients, computed with C ``int`` arithmetic
        (truncate-toward-zero division). Callers should treat them
        as 16-bit signed quantities; out-of-range values can occur
        when ``acoef`` is tiny (the C version wraps via the
        ``short *`` store, which is what the synth back-end
        normally relies on, but the Python port returns the
        full-precision ``int`` so the wrap is up to the caller).

    Raises:
        ZeroDivisionError: When ``acoef == 0`` (i.e. ``b + c == 4096``).
            The C source has the same failure mode -- it would either
            divide-by-zero-trap or produce an undefined ``INT_MIN`` on
            the embedded targets. Callers must pre-screen pathological
            (f, bw) combinations.
    """
    # Step 1: r = exp(-pi * bw * t) from the radius_table lookup.
    r = radius_table[bw >> 3]

    # Step 2: c = -r**2 in Q12.
    ccoef = -frac4mul(r, r)

    # Step 3: b = r * 2*cos(2 pi f t) in Q12.
    bcoef = frac4mul(r, cosine_table[f >> 3])

    # Step 4: a = 1.0 - b - c in Q12 (4096 represents 1.0).
    acoef = 4096 - bcoef - ccoef

    # Step 5: convert to antiresonator coefficients (a'=1/a, b'=-b/a,
    # c'=-c/a), scaled by rnzg. C ``/`` truncates toward zero.
    sacoef = _c_div(4096 * rnzg, acoef)
    sbcoef = -_c_div(bcoef * rnzg, acoef)
    sccoef = -_c_div(ccoef * rnzg, acoef)
    return sacoef, sbcoef, sccoef


__all__ = ["setzeroabc"]
