"""Verify int_volume_table matches vtm3.c."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm.volume_table import int_volume_table

_C_FILE: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtm3.c")


def _parse_table() -> list[int] | None:
    """Return the integers in ``const int int_volume_table[141] = { ... };``."""
    if not _C_FILE.exists():
        return None
    text = _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = r"const\s+int\s+int_volume_table\s*\[\s*141\s*\]\s*=\s*\{([^}]+)\}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_table_matches_c() -> None:
    """The full 141-entry table is byte-identical to vtm3.c."""
    c_values = _parse_table()
    assert c_values is not None
    assert tuple(c_values) == int_volume_table


def test_length_is_141() -> None:
    """The table is exactly 141 entries."""
    assert len(int_volume_table) == 141


def test_index_zero_is_mute() -> None:
    """Index 0 means full mute (value 0)."""
    assert int_volume_table[0] == 0


def test_index_100_is_unity_q15() -> None:
    """Index 100 (mid-table) is 32767 — unity gain in Q15."""
    assert int_volume_table[100] == 32767


def test_table_strictly_ascending_after_zero() -> None:
    """Entries 1..140 strictly increase (exponential curve)."""
    nonzero_tail = int_volume_table[1:]
    for prev, curr in pairwise(nonzero_tail):
        assert prev < curr


def test_max_entry_is_127k() -> None:
    """The largest entry is 131071 (= 2^17 - 1, just over +12 dB)."""
    assert max(int_volume_table) == 131071
    assert int_volume_table[-1] == 131071


def test_curve_is_roughly_exponential() -> None:
    """Successive ratios are approximately constant (~1.036 per step)."""
    nonzero = int_volume_table[1:]
    ratios = [b / a for a, b in pairwise(nonzero)]
    assert all(1.01 < r < 1.07 for r in ratios)
