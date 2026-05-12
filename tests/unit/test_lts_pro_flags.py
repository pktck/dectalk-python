"""Verify the PRO_* prosody flags from ls_data.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import pro_flags as pf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_data.h")


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
        ("PRO_OPEN_PAREN", "PRO_OPEN_PAREN", 0x00000001),
        ("PRO_CLOSE_PAREN", "PRO_CLOSE_PAREN", 0x00000002),
        ("PRO_OPEN_QUOTE", "PRO_OPEN_QUOTE", 0x00000004),
        ("PRO_CLOSE_QUOTE", "PRO_CLOSE_QUOTE", 0x00000008),
        ("PRO_DASH", "PRO_DASH", 0x00000010),
        ("PRO_CONJ", "PRO_CONJ", 0x00000020),
        ("PRO_FUNC", "PRO_FUNC", 0x00000040),
        ("PRO_PREP", "PRO_PREP", 0x00000080),
        ("PRO_THAT", "PRO_THAT", 0x00000100),
        ("PRO_MULTI_CONJ", "PRO_MULTI_CONJ", 0x00000200),
        ("PRO_OPT_BREAK", "PRO_OPT_BREAK", 0x00400000),
        ("PRO_REQ_BREAK", "PRO_REQ_BREAK", 0x00800000),
    ],
)
def test_pro_flag_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each PRO_* flag matches ls_data.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(pf, py_attr) == expected


def test_pro_flags_distinct_and_single_bit() -> None:
    """All 12 PRO_* flags are pairwise distinct single-bit values."""
    flags = [
        pf.PRO_OPEN_PAREN,
        pf.PRO_CLOSE_PAREN,
        pf.PRO_OPEN_QUOTE,
        pf.PRO_CLOSE_QUOTE,
        pf.PRO_DASH,
        pf.PRO_CONJ,
        pf.PRO_FUNC,
        pf.PRO_PREP,
        pf.PRO_THAT,
        pf.PRO_MULTI_CONJ,
        pf.PRO_OPT_BREAK,
        pf.PRO_REQ_BREAK,
    ]
    for v in flags:
        assert v > 0
        assert (v & (v - 1)) == 0, f"{v:#x} is not a single bit"
    assert len(set(flags)) == len(flags)


def test_break_flags_in_high_byte() -> None:
    """``PRO_OPT_BREAK`` / ``PRO_REQ_BREAK`` sit in bits 22 / 23."""
    assert pf.PRO_OPT_BREAK >> 22 == 1
    assert pf.PRO_REQ_BREAK >> 23 == 1
