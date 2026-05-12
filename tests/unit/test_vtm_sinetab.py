"""Verify ``SineTable`` matches sinetab.h value-for-value.

Re-parses the 1024-entry ``const double SineTable[]`` from
``src/dapi/src/vtm/sinetab.h`` and asserts every Python literal
matches the C source to the last printed decimal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.vtm import sinetab as st

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/vtm/sinetab.h")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_sine_table() -> tuple[float, ...]:
    """Parse ``const double SineTable[1024] = { ... };``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(r"const\s+double\s+SineTable\[1024\]\s*=\s*\{(.+?)\};", text, re.DOTALL)
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[float] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if re.fullmatch(r"-?\d*\.?\d+", tok):
            out.append(float(tok))
    return tuple(out)


def test_sine_table_matches_c_source() -> None:
    """Every entry matches the C source's decimal printout."""
    expected = _parse_sine_table()
    assert st.SineTable == expected


def test_sine_table_has_1024_entries() -> None:
    """Fixed-size 1024-entry table from sinetab.h."""
    expected = 1024
    assert len(st.SineTable) == expected


def test_two_pi_equivalent_is_1024() -> None:
    """The constant matches the C source #define."""
    expected = 1024.0
    assert expected == st.TWO_PI_EQUIVALENT


def test_sine_table_approximates_sine() -> None:
    """Spot-check: SineTable[i] ≈ sin(2*pi*i/1024) within rounding tolerance."""
    tolerance = 5e-6  # C source rounds to 6 decimals
    for i in (0, 256, 512, 768):
        expected = math.sin(2 * math.pi * i / 1024)
        assert abs(st.SineTable[i] - expected) < tolerance


def test_sine_table_quarter_cycle_is_one() -> None:
    """Index 256 (quarter cycle) should be ≈ 1.0."""
    quarter_index = 256
    assert abs(st.SineTable[quarter_index] - 1.0) < 1e-6


def test_sine_table_half_cycle_is_zero() -> None:
    """Index 512 (half cycle) should be ≈ 0.0."""
    half_index = 512
    assert abs(st.SineTable[half_index]) < 1e-6


def test_sine_table_three_quarter_cycle_is_minus_one() -> None:
    """Index 768 (3/4 cycle) should be ≈ -1.0."""
    three_quarter_index = 768
    assert abs(st.SineTable[three_quarter_index] - (-1.0)) < 1e-6
