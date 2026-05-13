"""Verify ASCII / ISO-8859 control-code constants match esc.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import ascii_control as ac

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/esc.h")


def _parse_define(name: str) -> int | None:
    """Return the integer value of ``#define <name> (0xNN)``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?\s*(0x[0-9A-Fa-f]+|\d+)\s*\)?\s*$"
    for raw in text.splitlines():
        line = raw.split("/*")[0].split("//")[0]
        match = re.match(pattern, line)
        if match:
            token = match.group(1)
            return int(token, 16) if token.lower().startswith("0x") else int(token)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("NUL", "NUL", 0x00),
        ("SOH", "SOH", 0x01),
        ("STX", "STX", 0x02),
        ("ETX", "ETX", 0x03),
        ("ENQ", "ENQ", 0x05),
        ("BEL", "BEL", 0x07),
        ("BS", "BS", 0x08),
        ("HT", "HT", 0x09),
        ("LF", "LF", 0x0A),
        ("VT", "VT", 0x0B),
        ("FF", "FF", 0x0C),
        ("CR", "CR", 0x0D),
        ("LS1", "LS1", 0x0E),
        ("LS0", "LS0", 0x0F),
        ("SO", "SO", 0x0E),
        ("SI", "SI", 0x0F),
        ("DLE", "DLE", 0x10),
        ("XON", "XON", 0x11),
        ("XOFF", "XOFF", 0x13),
        ("NAK", "NAK", 0x15),
        ("CAN", "CAN", 0x18),
        ("SUB", "SUB", 0x1A),
        ("ESC", "ESC", 0x1B),
        ("DEL", "DEL", 0x7F),
        ("SS2", "SS2", 0x8E),
        ("SS3", "SS3", 0x8F),
        ("DCS", "DCS", 0x90),
        ("OLDID", "OLDID", 0x9A),
        ("CSI", "CSI", 0x9B),
        ("ST", "ST", 0x9C),
        ("OSC", "OSC", 0x9D),
        ("PM", "PM", 0x9E),
        ("APC", "APC", 0x9F),
        ("RDEL", "RDEL", 0xFF),
    ],
)
def test_control_code_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each ASCII / ISO-8859 control-code constant matches esc.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(ac, py_attr) == expected


def test_ls0_si_alias() -> None:
    """``LS0`` and ``SI`` are the same code point (0x0F)."""
    assert ac.LS0 == ac.SI == 0x0F


def test_ls1_so_alias() -> None:
    """``LS1`` and ``SO`` are the same code point (0x0E)."""
    assert ac.LS1 == ac.SO == 0x0E


def test_all_codes_in_byte_range() -> None:
    """Every constant fits in a single unsigned byte."""
    for name in ac.__all__:
        value = getattr(ac, name)
        assert 0 <= value <= 0xFF


def test_c0_codes_below_0x20() -> None:
    """The classical C0 control set is below 0x20 (DEL is the exception)."""
    for name in (
        "NUL",
        "SOH",
        "STX",
        "ETX",
        "ENQ",
        "BEL",
        "BS",
        "HT",
        "LF",
        "VT",
        "FF",
        "CR",
        "LS0",
        "LS1",
        "DLE",
        "XON",
        "XOFF",
        "NAK",
        "CAN",
        "SUB",
        "ESC",
    ):
        assert getattr(ac, name) < 0x20


def test_c1_codes_in_8e_to_9f() -> None:
    """The C1 control set DECtalk uses lives in 0x8E-0x9F."""
    for name in ("SS2", "SS3", "DCS", "OLDID", "CSI", "ST", "OSC", "PM", "APC"):
        assert 0x8E <= getattr(ac, name) <= 0x9F
