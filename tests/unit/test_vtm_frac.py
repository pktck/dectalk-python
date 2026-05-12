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
