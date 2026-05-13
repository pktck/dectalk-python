"""Verify amptable matches vtmtable.h."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.vtm.amp_table import amptable

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_table() -> list[int] | None:
    """Return the integers in ``const S16 amptable[88] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = r"const\s+S16\s+amptable\s*\[\s*88\s*\]\s*=\s*\{([^}]+)\}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_table_matches_c() -> None:
    """The full 88-entry table is byte-identical to vtmtable.h."""
    c_values = _parse_table()
    assert c_values is not None
    assert tuple(c_values) == amptable


def test_length_is_88() -> None:
    """The table is exactly 88 entries."""
    assert len(amptable) == 88


def test_silent_floor_13_entries() -> None:
    """The first 13 entries are 0 (below -75 dB threshold)."""
    for i in range(13):
        assert amptable[i] == 0
    assert amptable[13] == 6  # first non-zero


def test_minus_6db_at_81() -> None:
    """Index 81 (-6 dB) is 16384 — half of full scale."""
    assert amptable[81] == 16384


def test_full_scale_at_87() -> None:
    """Index 87 (0 dB) is 32767 — Q15 full scale."""
    assert amptable[87] == 32767
    assert max(amptable) == 32767


def test_nonzero_strictly_ascending() -> None:
    """All non-zero entries increase monotonically."""
    nonzero = amptable[13:]
    for prev, curr in pairwise(nonzero):
        assert prev < curr


def test_each_step_is_one_db() -> None:
    """Successive non-zero entries roughly differ by 10^(1/20) (= +1 dB)."""
    nonzero = amptable[13:]
    ratios = [b / a for a, b in pairwise(nonzero) if a > 0]
    # 1 dB step ≈ 1.122; the table is integer-quantised so allow ±10 %.
    for ratio in ratios:
        assert 1.01 < ratio < 1.25
