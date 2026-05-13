"""Verify linear_interpolate / interpolate_table match nasalf1x.c."""

from __future__ import annotations

import math

from dectalk.hlsyn.interpolate import interpolate_table, linear_interpolate


def _close(actual: float, expected: float) -> bool:
    """Return True iff ``actual`` is within ``1e-9`` of ``expected``."""
    return math.isclose(actual, expected, abs_tol=1e-9)


def test_linear_interpolate_at_first_knot() -> None:
    """At ``x = x1``, returns ``y1``."""
    assert _close(linear_interpolate(0.0, 0.0, 5.0, 10.0, 15.0), 5.0)


def test_linear_interpolate_at_second_knot() -> None:
    """At ``x = x2``, returns ``y2``."""
    assert _close(linear_interpolate(10.0, 0.0, 5.0, 10.0, 15.0), 15.0)


def test_linear_interpolate_midpoint() -> None:
    """At ``x = (x1+x2)/2``, returns midpoint of y1 and y2."""
    assert _close(linear_interpolate(5.0, 0.0, 5.0, 10.0, 15.0), 10.0)


def test_linear_interpolate_extrapolates() -> None:
    """The line extends beyond the knots (no clamping)."""
    # Slope = (15-5)/(10-0) = 1; y_intercept = 5.
    # At x = 20: y = 1*20 + 5 = 25.
    assert _close(linear_interpolate(20.0, 0.0, 5.0, 10.0, 15.0), 25.0)
    # At x = -5: y = -5 + 5 = 0.
    assert _close(linear_interpolate(-5.0, 0.0, 5.0, 10.0, 15.0), 0.0)


def test_linear_interpolate_negative_slope() -> None:
    """Negative slope (y1 > y2) interpolates correctly."""
    assert _close(linear_interpolate(5.0, 0.0, 10.0, 10.0, 0.0), 5.0)


def test_interpolate_table_clamps_below() -> None:
    """Inputs below ``table[0].column1`` clamp to ``table[0].column2``."""
    table = [(0.0, 100.0), (10.0, 200.0), (20.0, 300.0)]
    assert interpolate_table(table, -5.0) == 100.0
    assert interpolate_table(table, -1000.0) == 100.0


def test_interpolate_table_clamps_above() -> None:
    """Inputs above ``table[-1].column1`` clamp to ``table[-1].column2``."""
    table = [(0.0, 100.0), (10.0, 200.0), (20.0, 300.0)]
    assert interpolate_table(table, 25.0) == 300.0
    assert interpolate_table(table, 1000.0) == 300.0


def test_interpolate_table_at_knot() -> None:
    """At an exact knot, returns its ``column2`` value."""
    table = [(0.0, 100.0), (10.0, 200.0), (20.0, 300.0)]
    # First knot: clamped low.
    assert interpolate_table(table, 0.0) == 100.0
    # Middle knot: matches start of [10,20) range.
    assert interpolate_table(table, 10.0) == 200.0


def test_interpolate_table_interpolates_midpoint() -> None:
    """Inputs between two knots interpolate linearly."""
    table = [(0.0, 100.0), (10.0, 200.0), (20.0, 300.0)]
    assert _close(interpolate_table(table, 5.0), 150.0)
    assert _close(interpolate_table(table, 15.0), 250.0)


def test_interpolate_table_non_linear_table() -> None:
    """Each segment is interpolated independently."""
    table = [(0.0, 0.0), (10.0, 100.0), (20.0, 110.0)]
    # First segment (slope=10): at x=5 → 50.
    assert _close(interpolate_table(table, 5.0), 50.0)
    # Second segment (slope=1): at x=15 → 105.
    assert _close(interpolate_table(table, 15.0), 105.0)


def test_interpolate_table_single_row_clamps_both_sides() -> None:
    """A 1-row table returns its single y-value for everything."""
    table = [(5.0, 42.0)]
    assert interpolate_table(table, 0.0) == 42.0
    assert interpolate_table(table, 5.0) == 42.0
    assert interpolate_table(table, 100.0) == 42.0
