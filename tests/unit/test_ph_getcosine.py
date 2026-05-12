"""Verify ``getcosine`` parity with ph_drwt01.c.

Cross-checks the integer-arithmetic cosine approximation against
math.cos for representative angles plus the documented boundary
values (cos(0) = ONE, cos(π/2) = 0, cos(π) = -ONE).
"""

from __future__ import annotations

import math

import pytest

from dectalk.ph import getcosine as gc


def test_constants_match_c_source() -> None:
    """PI/TWOPI/PIOVER2/ONE match the ph_drwt01.c #defines."""
    expected_twopi = 4096
    expected_pi = 2048
    expected_piover2 = 1024
    expected_one = 1024 * 1024
    assert expected_twopi == gc.TWOPI
    assert expected_pi == gc.PI
    assert expected_piover2 == gc.PIOVER2
    assert expected_one == gc.ONE


def test_zero_returns_one() -> None:
    """cos(0) approximated as ONE."""
    # time=0 → temptime=0, cosine = 0 - ONE = -ONE, time==temptime → -cosine = ONE
    assert gc.getcosine(0) == gc.ONE


def test_pi_returns_minus_one() -> None:
    """cos(π) approximated as -ONE."""
    # time=PI > PI? No. temptime=PI > PIOVER2 → temptime = PI - PI = 0.
    # cosine = 0 - ONE = -ONE. time(2048) != temptime(0) → return cosine = -ONE.
    assert gc.getcosine(gc.PI) == -gc.ONE


def test_piover2_returns_zero() -> None:
    """cos(π/2) approximated as 0 (since temptime² = PIOVER2² = ONE)."""
    # time=PIOVER2=1024. time>PI? No. temptime=1024. temptime>PIOVER2(1024)? No (not strictly >).
    # cosine = 1024² - ONE = ONE - ONE = 0. time == temptime → return -cosine = 0.
    assert gc.getcosine(gc.PIOVER2) == 0


def test_three_piover2_returns_zero() -> None:
    """cos(3π/2) approximated as 0."""
    three_piover2 = gc.PI + gc.PIOVER2  # 3072
    # time > PI → time = TWOPI - time = 4096 - 3072 = 1024
    # temptime=1024 > 1024? No. cosine=0. time(1024)==temptime(1024) → -cosine=0.
    assert gc.getcosine(three_piover2) == 0


def test_symmetry_around_pi() -> None:
    """getcosine(2π - x) == getcosine(x) for x ≤ π."""
    for x in (100, 500, 1000, 1500, 2000):
        assert gc.getcosine(gc.TWOPI - x) == gc.getcosine(x), f"x={x}"


@pytest.mark.parametrize(
    "time",
    [0, 200, 500, 800, 1000, 1024, 1300, 1500, 1800, 2000, 2048, 2200, 2500, 3000, 3500, 4000],
)
def test_within_unit_circle_bounds(time: int) -> None:
    """The result is always in [-ONE, +ONE]."""
    val = gc.getcosine(time)
    assert -gc.ONE <= val <= gc.ONE


@pytest.mark.parametrize(
    ("time", "expected_sign"),
    [
        (0, +1),  # cos(0) > 0
        (gc.PIOVER2 - 100, +1),  # just before π/2 — still positive
        (gc.PIOVER2 + 100, -1),  # just after π/2 — negative
        (gc.PI - 100, -1),  # just before π — negative
        (gc.PI + 100, -1),  # just after π — negative
        (gc.PI + gc.PIOVER2 - 100, -1),  # before 3π/2 — negative
        (gc.PI + gc.PIOVER2 + 100, +1),  # after 3π/2 — positive
    ],
)
def test_sign_in_each_quadrant(time: int, expected_sign: int) -> None:
    """Sign of cosine in each quadrant matches expectation."""
    val = gc.getcosine(time)
    if expected_sign > 0:
        assert val > 0, f"time={time}: expected positive, got {val}"
    else:
        assert val < 0, f"time={time}: expected negative, got {val}"


def test_approximates_math_cos() -> None:
    """The integer approximation tracks math.cos within ~3% (it's a poor approx).

    The C source uses cosine ≈ ONE * (1 - t²/PIOVER2²) which is a
    parabolic fit, not Taylor. Loose tolerance reflects that.
    """
    tolerance = 0.06  # 6% of ONE — parabolic approx has up to ~5.5% error
    for time in (0, 256, 512, 768, 1024, 1280, 1536, 1792, 2048):
        angle = (time / gc.TWOPI) * 2 * math.pi
        expected = math.cos(angle) * gc.ONE
        actual = gc.getcosine(time)
        rel_err = abs(actual - expected) / gc.ONE
        assert rel_err < tolerance, (
            f"time={time}: cos={expected:.0f}, got={actual}, err={rel_err:.4f}"
        )
