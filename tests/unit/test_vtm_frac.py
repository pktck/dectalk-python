"""Verify ``frac4mul`` parity with viphdefs.h.

The C macro is ``#define frac4mul(x,y) (((x)*(S32)(y))>>12)``.
"""

from __future__ import annotations

import ctypes

import pytest

from dectalk.vtm import frac


def _c_frac4mul(x: int, y: int) -> int:
    """Reference implementation using ctypes to mirror C semantics exactly."""
    x16 = ctypes.c_int16(x).value
    y32 = ctypes.c_int32(y).value
    product = ctypes.c_int32(x16 * y32).value
    return product >> 12


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0, 0, 0),
        (4096, 4096, 4096),  # 1.0 * 1.0 == 1.0
        (4096, 2048, 2048),  # 1.0 * 0.5 == 0.5
        (2048, 2048, 1024),  # 0.5 * 0.5 == 0.25
        (-4096, 4096, -4096),  # -1.0 * 1.0 == -1.0
        (4096, -4096, -4096),  # 1.0 * -1.0 == -1.0
        (-4096, -4096, 4096),  # -1.0 * -1.0 == 1.0
        (1, 1, 0),  # too small to register after >>12
        (2048, 100, 50),  # 0.5 * 100 (Q12) == 50
        (4095, 4095, 4094),  # (4095*4095)>>12 == 4094 (slightly less than 4096 due to truncation)
    ],
)
def test_known_values(x: int, y: int, expected: int) -> None:
    """Spot-check named cases."""
    assert frac.frac4mul(x, y) == expected


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (1000, 1000),
        (-1000, 1000),
        (1000, -1000),
        (-1000, -1000),
        (12345, 6789),
        (-32768, 1),  # min S16
        (32767, 1),  # max S16
        (-32768, -32768),  # min * min — large product
        (32767, 32767),  # max * max
        (0, 32767),
        (-1, -1),  # small negative
    ],
)
def test_matches_ctypes_reference(x: int, y: int) -> None:
    """For a broad set of inputs, the Python output matches a ctypes reference."""
    assert frac.frac4mul(x, y) == _c_frac4mul(x, y)


def test_typical_resonator_calculation() -> None:
    """Typical VTM call: r * 2*cos(2*pi*f*t) ≈ r * cosine_table[f].

    With r=3000 (≈ 0.73) and cosine_table value ≈ 3500 (≈ 0.85),
    the result should be ≈ 3000 * 3500 / 4096 ≈ 2563.
    """
    expected = (3000 * 3500) >> 12
    assert frac.frac4mul(3000, 3500) == expected


# ---- frac1mul (Q15) ----


def _c_frac1mul(x: int, y: int) -> int:
    """Reference implementation using ctypes to mirror C semantics exactly."""
    x16 = ctypes.c_int16(x).value
    y32 = ctypes.c_int32(y).value
    product = ctypes.c_int32(x16 * y32).value
    return product >> 15


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (0, 0, 0),
        (16384, 16384, 8192),  # 0.5 * 0.5 == 0.25 (Q15)
        (32767, 32767, 32766),  # near-1 squared (Q15 ≈ 0.999^2)
        (-16384, 16384, -8192),  # -0.5 * 0.5
        (24574, 1000, 749),  # 24574000 >> 15 = 749 (truncated)
    ],
)
def test_frac1mul_known_values(x: int, y: int, expected: int) -> None:
    """Spot-check named Q15 cases."""
    assert frac.frac1mul(x, y) == expected


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (24574, 1000),  # typical noise-LPF input
        (1000, 1000),
        (-1000, 1000),
        (1000, -1000),
        (-1000, -1000),
        (24574, 24574),  # nolast * 0.75 (typical pair)
        (-32768, -32768),
        (32767, 32767),
    ],
)
def test_frac1mul_matches_ctypes_reference(x: int, y: int) -> None:
    """For a broad set of inputs, Q15 matches a ctypes reference."""
    assert frac.frac1mul(x, y) == _c_frac1mul(x, y)


def test_frac1mul_aspiration_lpf_usage() -> None:
    """The C source uses ``frac1mul(24574, nolast)`` as a 0.75 LPF coefficient.

    24574 / 32768 ≈ 0.7500244 ≈ 0.75, the noise-LPF filter coefficient.
    """
    nolast = 16000
    # The actual computation is: (24574 * 16000) >> 15 = 393184000 >> 15 = 11999
    expected = (24574 * nolast) >> 15
    assert frac.frac1mul(24574, nolast) == expected
    # Sanity check the coefficient is roughly 0.75 of nolast.
    assert 0.74 * nolast < expected < 0.76 * nolast
