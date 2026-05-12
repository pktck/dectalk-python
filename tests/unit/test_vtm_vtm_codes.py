"""Verify VTM sample-rate / frame-size constants from vtm.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.vtm import vtm_codes as vc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vtm.h")


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
        ("MAXIMUM_FRAME_SIZE", "MAXIMUM_FRAME_SIZE", 100),
        ("SAMPLE_RATE_INCREASE", "SAMPLE_RATE_INCREASE", 0),
        ("SAMPLE_RATE_DECREASE", "SAMPLE_RATE_DECREASE", 1),
        ("NO_SAMPLE_RATE_CHANGE", "NO_SAMPLE_RATE_CHANGE", 2),
    ],
)
def test_vtm_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each VTM constant matches vtm.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(vc, py_attr) == expected


def test_sample_rate_codes_distinct() -> None:
    """The three sample-rate change codes 0/1/2 are pairwise distinct."""
    codes = {vc.SAMPLE_RATE_INCREASE, vc.SAMPLE_RATE_DECREASE, vc.NO_SAMPLE_RATE_CHANGE}
    assert codes == {0, 1, 2}
