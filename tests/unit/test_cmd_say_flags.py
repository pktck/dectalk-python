"""Verify SAY_* / R2_* / DCS framing codes match esc.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import say_flags as sf
from dectalk.cmd.dcs_codes import DCS_ERROR

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/esc.h")


def _parse_define(name: str) -> int | None:
    """Return the integer value of ``#define <name> <int>``."""
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
        ("SAY_CLAUSE", "SAY_CLAUSE", 0x0000),
        ("SAY_WORD", "SAY_WORD", 0x0001),
        ("SAY_LETTER", "SAY_LETTER", 0x0002),
        ("SAY_LINE", "SAY_LINE", 0x0004),
        ("SAY_SYLLABLE", "SAY_SYLLABLE", 0x0008),
        ("SAY_FLETTER", "SAY_FLETTER", 0x0010),
        ("R2_IX_REPLY", "R2_IX_REPLY", 31),
        ("R2_IX_QUERY", "R2_IX_QUERY", 32),
        ("R2_ERROR", "R2_ERROR", 300),
        ("P1_DECTALK", "P1_DECTALK", 0),
    ],
)
def test_define_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each integer constant matches its C ``#define``."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(sf, py_attr) == expected


def test_say_clause_is_zero() -> None:
    """``SAY_CLAUSE`` (0) is the default — no bits set."""
    assert sf.SAY_CLAUSE == 0


def test_say_flags_are_distinct_powers_of_two() -> None:
    """Each non-zero ``SAY_*`` is a distinct power of two."""
    bits = (sf.SAY_WORD, sf.SAY_LETTER, sf.SAY_LINE, sf.SAY_SYLLABLE, sf.SAY_FLETTER)
    for bit in bits:
        assert bit & (bit - 1) == 0  # single-bit set
    assert sum(bits) == sf.SAY_WORD | sf.SAY_LETTER | sf.SAY_LINE | sf.SAY_SYLLABLE | sf.SAY_FLETTER


def test_dcs_f_dectalk_is_lowercase_z() -> None:
    """The DECtalk DCS-final byte is ASCII ``'z'`` (122)."""
    assert chr(sf.DCS_F_DECTALK) == "z"
    assert sf.DCS_F_DECTALK == 0x7A


def test_r2_error_matches_dcs_error() -> None:
    """``R2_ERROR`` shares the value 300 with ``DCS_ERROR`` — same wire code."""
    assert sf.R2_ERROR == DCS_ERROR == 300
