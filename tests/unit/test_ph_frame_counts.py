"""Verify NFxxMS frame counts match ph_defs.h."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from dectalk.ph import frame_counts as fc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("NF7MS", "NF7MS", 1),
        ("NF15MS", "NF15MS", 2),
        ("NF20MS", "NF20MS", 3),
        ("NF25MS", "NF25MS", 4),
        ("NF30MS", "NF30MS", 5),
        ("NF40MS", "NF40MS", 6),
        ("NF45MS", "NF45MS", 7),
        ("NF50MS", "NF50MS", 8),
        ("NF60MS", "NF60MS", 9),
        ("NF64MS", "NF64MS", 10),
        ("NF70MS", "NF70MS", 11),
        ("NF75MS", "NF75MS", 12),
        ("NF80MS", "NF80MS", 13),
        ("NF90MS", "NF90MS", 14),
        ("NF100MS", "NF100MS", 16),
        ("NF115MS", "NF115MS", 18),
        ("NF130MS", "NF130MS", 20),
        ("NF160MS", "NF160MS", 25),
        ("NF480MS", "NF480MS", 75),
        ("NF640MS", "NF640MS", 100),
    ],
)
def test_frame_count_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each NFxxMS frame count matches ph_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(fc, py_attr) == expected


def test_frame_counts_monotonic() -> None:
    """Frame counts increase monotonically with ms."""
    pairs = [
        (7, fc.NF7MS),
        (15, fc.NF15MS),
        (20, fc.NF20MS),
        (25, fc.NF25MS),
        (30, fc.NF30MS),
        (40, fc.NF40MS),
        (45, fc.NF45MS),
        (50, fc.NF50MS),
        (60, fc.NF60MS),
        (64, fc.NF64MS),
        (70, fc.NF70MS),
        (75, fc.NF75MS),
        (80, fc.NF80MS),
        (90, fc.NF90MS),
        (100, fc.NF100MS),
        (115, fc.NF115MS),
        (130, fc.NF130MS),
        (160, fc.NF160MS),
        (480, fc.NF480MS),
        (640, fc.NF640MS),
    ]
    for (_ms_a, frames_a), (_ms_b, frames_b) in pairwise(pairs):
        assert frames_a <= frames_b


def test_nf640ms_is_100_frames() -> None:
    """640 ms is exactly 100 frames (round number for engine scaling)."""
    assert fc.NF640MS == 100


def test_nf64ms_pause_base() -> None:
    """NF64MS (10) is the pause-comma / pause-period base."""
    assert fc.NF64MS == 10
