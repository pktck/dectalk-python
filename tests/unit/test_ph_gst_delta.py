"""Verify gst_delta table matches ph_drwt02.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.gst_delta import gst_delta

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_drwt02.c")


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_gst_delta_matches_c_source() -> None:
    """All 9 entries match the C ``gst_delta[9]`` literal (with zero-fill)."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"const\s+short\s+gst_delta\s*\[\s*9\s*\]\s*=\s*\{(.*?)\}",
        text,
        re.DOTALL,
    )
    assert match is not None
    values = tuple(int(v) for v in re.findall(r"-?\d+", match.group(1)))
    # C source provides 8 entries; the 9th is zero-filled.
    expected = (*values, *([0] * (9 - len(values))))
    assert gst_delta == expected


def test_gst_delta_length() -> None:
    """9-entry table (matches C array size)."""
    expected_count = 9
    assert len(gst_delta) == expected_count


def test_gst_delta_monotonic_decreasing() -> None:
    """The deltas monotonically decrease as gesture number increases."""
    for i in range(len(gst_delta) - 1):
        assert gst_delta[i] >= gst_delta[i + 1]


def test_gst_delta_first_is_90() -> None:
    """First gesture has the largest delta (90)."""
    assert gst_delta[0] == 90


def test_gst_delta_zero_filled_tail() -> None:
    """Entries beyond the 7th are zero."""
    assert gst_delta[7] == 0
    assert gst_delta[8] == 0
