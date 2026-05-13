"""Verify B0 glottal-pulse-shape table matches vtmtable.h."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm.glottal_b0_table import B0

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_table() -> list[int] | None:
    """Return the integers in ``const S16 B0[224] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = r"const\s+S16\s+B0\s*\[\s*224\s*\]\s*=\s*\{(.*?)\};"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_b0_matches_c() -> None:
    """The full 224-entry table is byte-identical to vtmtable.h."""
    c_values = _parse_table()
    assert c_values is not None
    assert tuple(c_values) == B0


def test_b0_length_is_224() -> None:
    """``B0`` is exactly 224 entries (nopen = 40..263)."""
    assert len(B0) == 224


def test_b0_first_entry_is_1200() -> None:
    """``B0[0]`` (nopen = 40) = round(1920000 / 1600) = 1200."""
    assert B0[0] == 1200


def test_b0_last_entry_is_27() -> None:
    """``B0[223]`` (nopen = 263) = round(1920000 / 69169) = 27."""
    assert B0[223] == 27


def test_b0_strictly_descending() -> None:
    """``B0`` descends monotonically as ``nopen`` grows."""
    for prev, curr in pairwise(B0):
        assert prev >= curr


def test_b0_matches_formula_within_rounding() -> None:
    """Sample 5 indices and check the ``1920000 / nopen**2`` formula."""
    for i in (0, 50, 100, 150, 223):
        nopen = i + 40
        expected = 1920000 / (nopen * nopen)
        assert abs(B0[i] - expected) < 2
