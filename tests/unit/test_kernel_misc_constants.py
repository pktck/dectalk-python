"""Verify misc kernel.h constants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.kernel import misc_constants as mc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/kernel.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int-or-hex>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?(0[xX][0-9A-Fa-f]+|\d+)\)?\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("VERSIONLEN", "VERSIONLEN", 80),
        ("SPEAKLEN", "SPEAKLEN", 190),
        ("TICKS_PER_SECOND", "TICKS_PER_SECOND", 100),
        ("ANY_CHANGE", "ANY_CHANGE", 0),
        ("LOW_CHANGE", "LOW_CHANGE", 1),
        ("HIGH_CHANGE", "HIGH_CHANGE", 2),
    ],
)
def test_misc_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each misc constant matches kernel.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(mc, py_attr) == expected


def test_change_codes_dense() -> None:
    """Three volume-change codes form the dense set ``{0, 1, 2}``."""
    codes = {mc.ANY_CHANGE, mc.LOW_CHANGE, mc.HIGH_CHANGE}
    assert codes == {0, 1, 2}


def test_ticks_per_second_implies_10ms() -> None:
    """100 ticks per second means each tick = 10 milliseconds."""
    ms_per_tick = 1000 / mc.TICKS_PER_SECOND
    assert ms_per_tick == 10
