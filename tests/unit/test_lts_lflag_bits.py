"""Verify ``lflag`` bit-flag constants match ls_defs.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import lflag_bits as lf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int-or-hex>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(0[xX][0-9A-Fa-f]+|\d+)\b"
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
        ("LSTRIP", "LSTRIP", 0x0001),
        ("RSTRIP", "RSTRIP", 0x0002),
        ("DIGSLSH", "DIGSLSH", 0x0004),
        ("SQUOTE", "SQUOTE", 0x0008),
        ("HVOWEL", "HVOWEL", 0x0010),
        ("HCONS", "HCONS", 0x0020),
        ("HHYPHEN", "HHYPHEN", 0x0040),
        ("HNONY", "HNONY", 0x0080),
    ],
)
def test_lflag_bit_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each ``lflag`` bit matches ls_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(lf, py_attr) == expected


def test_lflag_bits_are_single_bits() -> None:
    """Each flag is a power of two (single-bit mask)."""
    bits = [
        lf.LSTRIP,
        lf.RSTRIP,
        lf.DIGSLSH,
        lf.SQUOTE,
        lf.HVOWEL,
        lf.HCONS,
        lf.HHYPHEN,
        lf.HNONY,
    ]
    for bit in bits:
        assert bit > 0
        assert bit & (bit - 1) == 0  # power of two


def test_lflag_bits_are_distinct() -> None:
    """All 8 flags occupy distinct bit positions."""
    bits = {
        lf.LSTRIP,
        lf.RSTRIP,
        lf.DIGSLSH,
        lf.SQUOTE,
        lf.HVOWEL,
        lf.HCONS,
        lf.HHYPHEN,
        lf.HNONY,
    }
    assert len(bits) == 8


def test_lflag_bits_fit_in_low_byte() -> None:
    """All 8 flags fit in the low byte of a 16-bit lflag word."""
    combined = (
        lf.LSTRIP
        | lf.RSTRIP
        | lf.DIGSLSH
        | lf.SQUOTE
        | lf.HVOWEL
        | lf.HCONS
        | lf.HHYPHEN
        | lf.HNONY
    )
    assert combined == 0xFF
