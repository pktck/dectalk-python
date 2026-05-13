"""Brent's root-finding method from hlsyn/brent.c.

Translated from ``src/dapi/src/hlsyn/brent.c``. The HLsyn module's
parametric-frame conversion uses Brent's algorithm to find the
resonator frequencies that satisfy specific bandwidth or
susceptance constraints (``acxf1c.c`` and ``nasalf1x.c`` call into
these helpers).

- :func:`brent_bracket` — expands an initial range until it
  encloses a sign change in the target function.
- :func:`brent` — refines that range to the root using inverse
  quadratic interpolation with bisection fallback (from Numerical
  Recipes in C, page 268).

Both functions take a callable of the form
``f(x: float, other_args: Any) -> float``. The ``other_args`` slot
carries arbitrary state through to the function — the C source
uses ``void *`` for the same purpose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    BrentFunction = Callable[[float, "Any"], float]


def brent_bracket(
    f: BrentFunction,
    other_args: Any,  # noqa: ANN401 — C "void *".
    x1: list[float],
    x2: list[float],
    factor: float,
    ntry: int,
) -> int:
    """Expand ``[x1, x2]`` until ``f(x1)`` and ``f(x2)`` have opposite signs.

    Faithful translation of:

    .. code-block:: c

        short BrentBracket(BrentFunctionType *pF, void *pOtherArgs,
                           float *x1, float *x2, float factor, int ntry) {
            f1 = (*pF)(*x1, pOtherArgs);
            f2 = (*pF)(*x2, pOtherArgs);
            for (j = 1; j <= ntry; j++) {
                if (f1 * f2 < 0.0f) return 1;
                if (fabs(f1) < fabs(f2))
                    f1 = (*pF)(*x1 += factor * (*x1 - *x2), pOtherArgs);
                else
                    f2 = (*pF)(*x2 += factor * (*x2 - *x1), pOtherArgs);
            }
            return 0;
        }

    The C source mutates the caller's ``*x1`` and ``*x2`` in place;
    the Python port wraps each in a single-element list to preserve
    that aliasing.

    Args:
        f: Function ``f(x, other_args) -> float`` whose root we want.
        other_args: Opaque payload passed verbatim to ``f``.
        x1: Mutable single-element list holding the lower bound.
        x2: Mutable single-element list holding the upper bound.
        factor: Expansion factor applied to whichever side has the
            larger ``|f|`` at each step.
        ntry: Maximum number of expansion iterations.

    Returns:
        1 if the bracket now encloses a sign change; 0 if ``ntry``
        iterations expired without finding one.
    """
    f1 = f(x1[0], other_args)
    f2 = f(x2[0], other_args)
    for _ in range(ntry):
        if f1 * f2 < 0.0:
            return 1
        if abs(f1) < abs(f2):
            x1[0] += factor * (x1[0] - x2[0])
            f1 = f(x1[0], other_args)
        else:
            x2[0] += factor * (x2[0] - x1[0])
            f2 = f(x2[0], other_args)
    return 0


def brent(  # noqa: PLR0912, PLR0915 — mirror C control flow.
    f: BrentFunction,
    other_args: Any,  # noqa: ANN401
    x1: float,
    x2: float,
    tol: float,
    itmax: int,
    eps: float,
) -> float:
    """Find a root of ``f`` known to lie in ``[x1, x2]`` via Brent's method.

    Faithful translation of ``Brent`` from ``brent.c`` (lines 70-180),
    which is in turn from Numerical Recipes in C, page 268. Uses
    inverse quadratic interpolation between three points with
    bisection as a fallback when interpolation would step outside
    the bracket. Convergence is checked at every iteration; the
    function returns when ``|xm| <= tol1`` or ``fb == 0``.

    Args:
        f: Function ``f(x, other_args) -> float``.
        other_args: Opaque payload passed verbatim to ``f``.
        x1: Lower bracket bound. Must have ``f(x1) * f(x2) <= 0``.
        x2: Upper bracket bound.
        tol: Absolute root tolerance.
        itmax: Maximum iterations.
        eps: Relative tolerance for convergence check.

    Returns:
        Refined root ``b`` such that ``|b - true_root| <= tol`` (in
        practice; mirrors C). On non-convergence the C source's
        DEBUG build calls ``exit(1)``; the release fall-through is
        ``x2 + 1`` (or ``x2 - 1`` if ``x1 > x2``) as an out-of-range
        sentinel, which this port preserves.
    """
    a = x1
    b = x2
    c = 0.0
    d = 0.0
    e = 0.0
    fa = f(a, other_args)
    fb = f(b, other_args)
    fc = fb

    for _ in range(itmax):
        if fb * fc > 0.0:
            # Rename a, b, c and adjust bounding interval d.
            c = a
            fc = fa
            e = d = b - a

        if abs(fc) < abs(fb):
            a = b
            b = c
            c = a
            fa = fb
            fb = fc
            fc = fa

        tol1 = 2.0 * eps * abs(b) + 0.5 * tol  # Convergence check.
        xm = 0.5 * (c - b)

        if abs(xm) <= tol1 or fb == 0.0:
            return b

        if abs(e) >= tol1 and abs(fa) > abs(fb):
            # Attempt inverse quadratic interpolation.
            s = fb / fa
            if a == c:
                p = 2.0 * xm * s
                q = 1.0 - s
            else:
                q = fa / fc
                r = fb / fc
                p = s * (2.0 * xm * q * (q - r) - (b - a) * (r - 1.0))
                q = (q - 1.0) * (r - 1.0) * (s - 1.0)
            if p > 0.0:
                q = -q  # Check whether in bounds.
            p = abs(p)
            min1 = 3.0 * xm * q - abs(tol1 * q)
            min2 = abs(e * q)
            if 2.0 * p < min(min1, min2):
                e = d  # Accept interpolation.
                d = p / q
            else:
                # Interpolation failed, use bisection.
                d = xm
                e = d
        else:
            # Bounds decreasing too slowly, use bisection.
            d = xm
            e = d

        a = b  # Move last best guess to a.
        fa = fb
        if abs(d) > tol1:  # Evaluate new trial root.
            b += d
        else:
            b += abs(tol1) if xm > 0.0 else -abs(tol1)

        fb = f(b, other_args)

    # Maximum number of iterations exceeded.
    return x2 + 1 if x1 < x2 else x2 - 1


__all__ = ["brent", "brent_bracket"]
