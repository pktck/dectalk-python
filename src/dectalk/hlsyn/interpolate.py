"""Generic interpolation helpers from hlsyn/nasalf1x.c.

Translated from ``src/dapi/src/hlsyn/nasalf1x.c`` lines 215-280.

The HLsyn module uses two general-purpose interpolation helpers
throughout its parametric-frame computation:

- :func:`linear_interpolate` — straight-line interpolation between
  two ``(x, y)`` knots.
- :func:`interpolate_table` — piecewise-linear interpolation over
  a monotone-increasing 2-column table, with end-point clamping
  for out-of-range inputs.

The table format mirrors the C source's ``TableRow`` struct:
``[(column1, column2), ...]`` where ``column1`` is strictly
increasing. The original C uses a fixed-length array plus a
length argument; the Python port takes a ``Sequence`` since the
length is available from ``len()``.
"""

from __future__ import annotations

from collections.abc import Sequence


def linear_interpolate(
    x: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    """Return the value at ``x`` on the line through ``(x1, y1)``-``(x2, y2)``.

    Faithful translation of:

    .. code-block:: c

        static float LinearInterpolate(float x, float x1, float y1,
                                       float x2, float y2) {
            float Slope = (y2 - y1) / (x2 - x1);
            float yIntercept = y1 - Slope * x1;
            return Slope * x + yIntercept;
        }

    Args:
        x: Point at which to evaluate the line.
        x1: First knot's x-coordinate.
        y1: First knot's y-coordinate.
        x2: Second knot's x-coordinate.
        y2: Second knot's y-coordinate.

    Returns:
        ``slope * x + y_intercept`` where the line passes through
        both knots. The caller must ensure ``x1 != x2`` (the C
        source has a ``DEBUG`` assertion for this).
    """
    slope = (y2 - y1) / (x2 - x1)
    y_intercept = y1 - slope * x1
    return slope * x + y_intercept


def interpolate_table(
    table: Sequence[tuple[float, float]],
    column1_point: float,
) -> float:
    """Piecewise-linear lookup over a monotone-increasing 2-column table.

    Faithful translation of:

    .. code-block:: c

        static float InterpolateTable(TableRow TheTable[], short TableLength,
                                      float Column1Point) {
            if (TheTable[0].Column1 >= Column1Point)
                return TheTable[0].Column2;
            else if (TheTable[TableLength-1].Column1 <= Column1Point)
                return TheTable[TableLength-1].Column2;
            else
                for (i = 0; i < TableLength-1; ++i)
                    if (Column1Point >= TheTable[i].Column1
                        && Column1Point < TheTable[i+1].Column1)
                        return LinearInterpolate(...);
        }

    Inputs below ``table[0].column1`` clamp to ``table[0].column2``;
    inputs at-or-above ``table[-1].column1`` clamp to ``table[-1].column2``.
    Inputs in between are interpolated linearly between adjacent rows.

    Args:
        table: Sequence of ``(column1, column2)`` rows.
            ``column1`` must be strictly increasing.
        column1_point: Input value to look up.

    Returns:
        Interpolated ``column2`` value (or clamped end-point).
    """
    # Clamp below the table.
    if table[0][0] >= column1_point:
        return table[0][1]
    # Clamp above the table.
    if table[-1][0] <= column1_point:
        return table[-1][1]
    # Linear interpolation between adjacent rows.
    for i in range(len(table) - 1):
        x1, y1 = table[i]
        x2, y2 = table[i + 1]
        if x1 <= column1_point < x2:
            return linear_interpolate(column1_point, x1, y1, x2, y2)
    # Unreachable: the loop above always matches when the input is
    # strictly inside the table range (which the two clamps above
    # guarantee). The C source's DEBUG branch is silent in release.
    return table[-1][1]


# Aliases under the original C-source names for inventory tests.
InterpolateTable = interpolate_table
LinearInterpolate = linear_interpolate

__all__ = [
    "InterpolateTable",
    "LinearInterpolate",
    "interpolate_table",
    "linear_interpolate",
]
