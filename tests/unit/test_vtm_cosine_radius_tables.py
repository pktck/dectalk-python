"""Verify cosine_table / radius_table match vtmtable.h."""

from __future__ import annotations

import math
import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm.cosine_radius_tables import cosine_table, radius_table

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_array(name: str) -> list[int] | None:
    """Return the integers in ``const S16 <name>[] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+S16\s+{re.escape(name)}\s*\[\s*\]\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_cosine_table_matches_c() -> None:
    """Every cosine entry matches the C array (751 entries)."""
    c_values = _parse_array("cosine_table")
    assert c_values is not None
    assert tuple(c_values) == cosine_table


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_radius_table_matches_c() -> None:
    """Every radius entry matches the C array (625 entries)."""
    c_values = _parse_array("radius_table")
    assert c_values is not None
    assert tuple(c_values) == radius_table


def test_cosine_table_length() -> None:
    """``cosine_table`` is 751 entries (F=0..6000 step 8)."""
    assert len(cosine_table) == 751


def test_radius_table_length() -> None:
    """``radius_table`` is 625 entries (BW=0..4992 step 8)."""
    assert len(radius_table) == 625


def test_cosine_zero_is_8192() -> None:
    """``cosine_table[0]`` = round(8192 * cos(0)) = 8192."""
    assert cosine_table[0] == 8192


def test_radius_zero_is_4096() -> None:
    """``radius_table[0]`` = round(4096 * exp(0)) = 4096."""
    assert radius_table[0] == 4096


def test_cosine_descends_then_ascends_monotonically() -> None:
    """Half-period: descends to 0 around f=2500, then continues negative."""
    # First few entries should descend (cosine starts at peak)
    for prev, curr in pairwise(cosine_table[:50]):
        assert prev >= curr


def test_radius_strictly_descends() -> None:
    """``radius_table`` strictly decreases (exponential decay)."""
    for prev, curr in pairwise(radius_table):
        assert prev > curr


def test_cosine_near_zero_at_quarter_period() -> None:
    """Index ~313 (F~2500 Hz) is roughly cos(pi/2) = 0."""
    # F = 313 * 8 = 2504 Hz, cos(2*pi*2504/10000) ≈ cos(1.573) ≈ -0.002
    assert abs(cosine_table[313]) < 50


def test_cosine_matches_formula_within_rounding() -> None:
    """Sample 5 indices and check the C formula ``8192*cos(2*pi*F/10000)``."""
    for i in (0, 100, 250, 500, 750):
        f_hz = i * 8
        expected = 8192 * math.cos(2 * math.pi * f_hz / 10000)
        assert abs(cosine_table[i] - expected) < 1.5


def test_radius_matches_formula_within_rounding() -> None:
    """Sample 5 indices and check the C formula ``4096*exp(-pi*BW/10000)``."""
    for i in (0, 100, 250, 400, 600):
        bw_hz = i * 8
        expected = 4096 * math.exp(-math.pi * bw_hz / 10000)
        assert abs(radius_table[i] - expected) < 1.5
