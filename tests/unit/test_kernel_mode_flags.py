"""Verify ``modeflag`` and ``pronflag`` bit values from esc.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.kernel import mode_flags as mf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/esc.h")


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
        ("MODE_MATH", "MODE_MATH", 0x0004),
        ("MODE_EUROPE", "MODE_EUROPE", 0x0008),
        ("MODE_SPELL", "MODE_SPELL", 0x0010),
        ("MODE_NAME", "MODE_NAME", 0x0040),
        ("MODE_HOMOGRAPH", "MODE_HOMOGRAPH", 0x0080),
        ("MODE_CITATION", "MODE_CITATION", 0x0100),
        ("MODE_LATIN", "MODE_LATIN", 0x0200),
        ("MODE_SESEO", "MODE_SESEO", 0x0200),
        ("MODE_TABLE", "MODE_TABLE", 0x0400),
        ("MODE_EMAIL", "MODE_EMAIL", 0x1000),
        ("PRON_DIC_PRIMARY", "PRON_DIC_PRIMARY", 0x0001),
        ("PRON_DIC_ALTERNATE", "PRON_DIC_ALTERNATE", 0x0002),
        ("PRON_ACNA_NAME", "PRON_ACNA_NAME", 0x0004),
        ("PRON_DIC_NOUN", "PRON_DIC_NOUN", 0x0008),
        ("PRON_DIC_VERB", "PRON_DIC_VERB", 0x0010),
        ("PRON_DIC_ADJECTIVE", "PRON_DIC_ADJECTIVE", 0x0020),
        ("PRON_DIC_FUNCTION", "PRON_DIC_FUNCTION", 0x0040),
        ("PRON_DIC_INTERJECTION", "PRON_DIC_INTERJECTION", 0x0080),
    ],
)
def test_mode_pron_flag_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each mode/pron flag matches the C header."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(mf, py_attr) == expected


def test_mode_seseo_aliases_latin() -> None:
    """``MODE_SESEO`` and ``MODE_LATIN`` share the same bit by design."""
    assert mf.MODE_SESEO == mf.MODE_LATIN


def test_mode_flags_distinct_except_aliases() -> None:
    """All MODE flags are pairwise distinct (except SESEO/LATIN aliases)."""
    flags = {
        mf.MODE_MATH,
        mf.MODE_EUROPE,
        mf.MODE_SPELL,
        mf.MODE_NAME,
        mf.MODE_HOMOGRAPH,
        mf.MODE_CITATION,
        mf.MODE_LATIN,
        mf.MODE_TABLE,
        mf.MODE_EMAIL,
    }
    assert len(flags) == 9  # 10 names but LATIN==SESEO


def test_pron_dic_pos_tags_distinct() -> None:
    """The four POS pronflags are pairwise distinct."""
    pos = {
        mf.PRON_DIC_NOUN,
        mf.PRON_DIC_VERB,
        mf.PRON_DIC_ADJECTIVE,
        mf.PRON_DIC_FUNCTION,
        mf.PRON_DIC_INTERJECTION,
    }
    assert len(pos) == 5
