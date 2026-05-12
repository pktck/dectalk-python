"""Verify ASYNC_* bit flags from kernel.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.kernel import async_flags as af

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/kernel.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> 0xN``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+0x([0-9A-Fa-f]+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1), 16)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("ASYNC_voice", "ASYNC_voice", 0x0001),
        ("ASYNC_rate", "ASYNC_rate", 0x0002),
        ("ASYNC_period", "ASYNC_period", 0x0004),
        ("ASYNC_comma", "ASYNC_comma", 0x0008),
        ("ASYNC_rate_delta", "ASYNC_rate_delta", 0x0010),
    ],
)
def test_async_flag(py_attr: str, c_name: str, expected: int) -> None:
    """Each ASYNC_* flag matches kernel.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(af, py_attr) == expected


def test_async_flags_are_powers_of_two() -> None:
    """All five flags are single-bit values."""
    flags = [
        af.ASYNC_voice,
        af.ASYNC_rate,
        af.ASYNC_period,
        af.ASYNC_comma,
        af.ASYNC_rate_delta,
    ]
    for f in flags:
        assert f > 0
        assert (f & (f - 1)) == 0
    assert len(set(flags)) == 5
