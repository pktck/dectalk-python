"""Verify getcosine_tab / lineartilt tables match ph_romi.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import cosine_tilt_tables as ctt

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_romi.c")


def _parse_table(name: str) -> list[int]:
    """Extract values from a ``const short <name>[...] = { ... };`` initialiser."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+short\s+{re.escape(name)}\s*\[\d*\]\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, text, re.DOTALL)
    if match is None:
        return []
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return [int(v) for v in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_getcosine_tab_matches_c_source() -> None:
    """``getcosine_tab`` matches the C ``getcosine[64]`` table."""
    c_values = _parse_table("getcosine")
    assert len(c_values) == 64
    assert tuple(c_values) == ctt.getcosine_tab


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_lineartilt_matches_c_source() -> None:
    """``lineartilt`` matches ph_romi.c — 32 entries."""
    c_values = _parse_table("lineartilt")
    assert len(c_values) == 32
    assert tuple(c_values) == ctt.lineartilt


def test_getcosine_tab_starts_at_max() -> None:
    """``getcosine_tab[0]`` ≈ cos(0) *164 = 164."""
    assert ctt.getcosine_tab[0] == 164


def test_getcosine_tab_zero_crossings() -> None:
    """The table crosses zero at the quarter-points (index 16, 48)."""
    assert ctt.getcosine_tab[16] == 0
    assert ctt.getcosine_tab[48] == 0


def test_getcosine_tab_minimum_at_half() -> None:
    """``getcosine_tab[32]`` ≈ cos(π) *164 ≈ -164."""
    assert ctt.getcosine_tab[32] == -164


def test_lineartilt_zero_in_zero_out() -> None:
    """``lineartilt[0]`` = 0 (zero dB requested → zero chip value)."""
    assert ctt.lineartilt[0] == 0


def test_lineartilt_three_db_maps_to_twelve() -> None:
    """C source comment: '3 dB of tilt → send 12 to chip'."""
    assert ctt.lineartilt[3] == 12


def test_lineartilt_monotonically_increases() -> None:
    """Higher requested dB maps to a higher or equal chip value."""
    for i in range(1, len(ctt.lineartilt)):
        assert ctt.lineartilt[i] >= ctt.lineartilt[i - 1]
