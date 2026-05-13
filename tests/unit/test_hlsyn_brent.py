"""Verify brent / brent_bracket match hlsyn/brent.c."""

from __future__ import annotations

import math
from typing import cast

from dectalk.hlsyn.brent import brent, brent_bracket


def _poly_quadratic(x: float, _args: object) -> float:
    """``f(x) = x^2 - 4`` (roots at +-2)."""
    return x * x - 4.0


def _poly_linear(x: float, args: object) -> float:
    """``f(x) = a*x + b`` with ``args = (a, b)``."""
    pair = cast("tuple[float, float]", args)
    a, b = pair
    return a * x + b


def _poly_cubic(x: float, _args: object) -> float:
    """``f(x) = x^3 - x - 2`` (root near 1.5214)."""
    return x * x * x - x - 2.0


def test_brent_finds_root_of_x2_minus_4() -> None:
    """Brent locates the root of ``x^2 - 4`` in ``[1, 5]``."""
    root = brent(_poly_quadratic, None, 1.0, 5.0, 1e-6, 100, 1e-9)
    assert math.isclose(root, 2.0, abs_tol=1e-5)


def test_brent_finds_negative_root() -> None:
    """Brent locates the root of ``x^2 - 4`` in ``[-5, -1]``."""
    root = brent(_poly_quadratic, None, -5.0, -1.0, 1e-6, 100, 1e-9)
    assert math.isclose(root, -2.0, abs_tol=1e-5)


def test_brent_linear_function() -> None:
    """For a linear function, Brent converges to the analytic root."""
    # 2x + 4 = 0 → x = -2
    root = brent(_poly_linear, (2.0, 4.0), -5.0, 0.0, 1e-9, 100, 1e-12)
    assert math.isclose(root, -2.0, abs_tol=1e-6)


def test_brent_cubic_function() -> None:
    """Brent locates ``x^3 - x - 2 = 0`` near 1.5214."""
    root = brent(_poly_cubic, None, 1.0, 2.0, 1e-9, 100, 1e-12)
    assert math.isclose(root, 1.5213797068045676, abs_tol=1e-6)


def test_brent_returns_root_when_bracket_endpoint_is_root() -> None:
    """If ``f(x1) == 0``, Brent returns near ``x1`` (NR convergence)."""
    # f(2) = 0; bracket [2, 5].
    root = brent(_poly_quadratic, None, 2.0, 5.0, 1e-6, 100, 1e-9)
    assert math.isclose(root, 2.0, abs_tol=1e-5)


def test_brent_bracket_expands_to_find_sign_change() -> None:
    """Bracket expansion finds a sign change when starting away from root."""
    # f(x) = x^2 - 4: try [10, 11] (both positive). Expand toward root.
    x1 = [10.0]
    x2 = [11.0]
    # factor=-2 shrinks each side toward the other; with ntry=10 should find.
    # Use negative factor to *contract* — but the C source uses positive factor
    # to expand outward. Use a wide initial bracket: expand symmetrically.
    x1 = [-1.0]
    x2 = [1.0]
    rc = brent_bracket(_poly_quadratic, None, x1, x2, 1.6, 20)
    assert rc == 1
    # Sign change confirmed.
    assert _poly_quadratic(x1[0], None) * _poly_quadratic(x2[0], None) < 0.0


def test_brent_bracket_returns_zero_when_no_sign_change_found() -> None:
    """If ``ntry`` iterations don't find a bracket, returns 0."""

    # f(x) = x^2 - 4 is always >= -4. A function with no real root
    # would leave brent_bracket returning 0. Use f(x) = x^2 + 1.
    def _no_root(x: float, _: object) -> float:
        return x * x + 1.0

    x1 = [-1.0]
    x2 = [1.0]
    rc = brent_bracket(_no_root, None, x1, x2, 1.6, 5)
    assert rc == 0


def test_brent_bracket_mutates_bounds_in_place() -> None:
    """Successful bracketing leaves the bounds wider than the initial pair."""
    x1 = [-0.1]
    x2 = [0.1]
    initial_x1, initial_x2 = x1[0], x2[0]
    rc = brent_bracket(_poly_quadratic, None, x1, x2, 1.6, 20)
    assert rc == 1
    assert x1[0] < initial_x1 or x2[0] > initial_x2
