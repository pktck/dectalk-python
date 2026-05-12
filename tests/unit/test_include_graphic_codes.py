"""Verify Latin-1 graphics codes match l_all_ph.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import graphic_codes as gc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/l_all_ph.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> 0x..``."""
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
        ("CENT", "CENT", 0xA2),
        ("STERLING", "STERLING", 0xA3),
        ("YEN", "YEN", 0xA5),
        ("SECTION", "SECTION", 0xA7),
        ("DEGREE", "DEGREE", 0xB0),
        ("PLUS_MINUS", "PLUS_MINUS", 0xB1),
        ("PARAGRAPH", "PARAGRAPH", 0xB6),
        ("FOURTH", "FOURTH", 0xBC),
        ("HALF", "HALF", 0xBD),
        ("SUPER_1", "SUPER_1", 0xB9),
        ("SUPER_2", "SUPER_2", 0xB2),
        ("SUPER_3", "SUPER_3", 0xB3),
        ("SUPER_O", "SUPER_O", 0xBA),
        ("SUPER_A", "SUPER_A", 0xAA),
    ],
)
def test_graphic_code_matches_c_source(py_attr: str, c_name: str, expected: int) -> None:
    """Each Latin-1 graphics code matches l_all_ph.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(gc, py_attr) == expected


def test_fraction_codes_are_latin1() -> None:
    """``FOURTH`` and ``HALF`` are valid Latin-1 byte values."""
    assert gc.FOURTH == 0xBC
    assert gc.HALF == 0xBD
    assert bytes([gc.FOURTH]).decode("latin-1") == "¼"  # ¼
    assert bytes([gc.HALF]).decode("latin-1") == "½"  # ½


def test_superscript_digits_dense() -> None:
    """``SUPER_1`` / ``SUPER_2`` / ``SUPER_3`` form a complete set."""
    superscripts = {gc.SUPER_1, gc.SUPER_2, gc.SUPER_3}
    assert len(superscripts) == 3
    # Latin-1 puts SUPER_2 and SUPER_3 adjacent (0xB2, 0xB3) and SUPER_1
    # at 0xB9 — verify the unusual layout matches Latin-1.
    assert gc.SUPER_2 + 1 == gc.SUPER_3
    assert gc.SUPER_1 == 0xB9


def test_ordinal_indicators_distinct() -> None:
    """Masculine and feminine ordinal indicators are distinct."""
    assert gc.SUPER_O != gc.SUPER_A
    assert bytes([gc.SUPER_O]).decode("latin-1") == "º"  # º
    assert bytes([gc.SUPER_A]).decode("latin-1") == "ª"  # ª
