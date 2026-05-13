"""Verify tiltf / tiltbw tables match vtmtable.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.vtm import tilt_tables as tt

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtmtable.h")


def _parse_array(name: str) -> list[int] | None:
    """Return the integers in ``const short <name>[N] = { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+short\s+{re.escape(name)}\s*\[\s*\d+\s*\]\s*=\s*\{{([^}}]+)\}}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    return [int(tok) for tok in re.findall(r"-?\d+", body)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_tiltf_matches_c() -> None:
    """``tiltf`` is byte-identical to the C array."""
    c_values = _parse_array("tiltf")
    assert c_values is not None
    assert tuple(c_values) == tt.tiltf
    assert len(tt.tiltf) == 42


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_tiltbw_matches_c() -> None:
    """``tiltbw`` is byte-identical to the C array."""
    c_values = _parse_array("tiltbw")
    assert c_values is not None
    assert tuple(c_values) == tt.tiltbw
    assert len(tt.tiltbw) == 42


def test_tables_have_matching_length() -> None:
    """``tiltf`` and ``tiltbw`` are indexed in lock-step (same length)."""
    assert len(tt.tiltf) == len(tt.tiltbw) == 42


def test_first_entry_is_highest_frequency() -> None:
    """``tiltf[0]`` (4400 Hz) is the highest centre-frequency entry."""
    assert tt.tiltf[0] == 4400
    assert max(tt.tiltf) == tt.tiltf[0]


def test_last_entry_is_lowest_frequency() -> None:
    """``tiltf[-1]`` (312 Hz) is the lowest centre-frequency entry."""
    assert tt.tiltf[-1] == 312
    assert min(tt.tiltf) == tt.tiltf[-1]


def test_response_db_has_9_rows() -> None:
    """The C-source comment reference table has 9 (F, BW, db..) rows."""
    assert len(tt.tilt_response_db) == 9
    for row in tt.tilt_response_db:
        assert len(row) == 7  # F, BW, 5 dB measurements
