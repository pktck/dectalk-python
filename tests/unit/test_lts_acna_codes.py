"""Verify ACNA constants and struct from ls_acna.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import acna_codes as ac

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_acna.h")


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
        ("TG_start", "TG_start", 0x80),
        ("TG_end", "TG_end", 0x40),
        ("TG_freq", "TG_freq", 0x3F),
        ("PLENGTH", "PLENGTH", 0x0F),
        ("PCONT", "PCONT", 0x10),
        ("PRCON", "PRCON", 0x20),
        ("PRVOC", "PRVOC", 0x40),
        ("P2SYL", "P2SYL", 0x80),
        ("NAME_ENGLISH", "NAME_ENGLISH", 0),
        ("NAME_FRENCH", "NAME_FRENCH", 1),
        ("NAME_GERMANIC", "NAME_GERMANIC", 2),
        ("NAME_IRISH", "NAME_IRISH", 3),
        ("NAME_ITALIAN", "NAME_ITALIAN", 4),
        ("NAME_JAPANESE", "NAME_JAPANESE", 5),
        ("NAME_SLAVIC", "NAME_SLAVIC", 6),
        ("NAME_SPANISH", "NAME_SPANISH", 7),
        ("NO_LANGS", "NO_LANGS", 8),
        ("M_R_LANG", "M_R_LANG", 0x7FFF),
        ("M_R_SPECIFIC", "M_R_SPECIFIC", 0x8000),
    ],
)
def test_acna_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each ACNA constant matches ls_acna.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(ac, py_attr) == expected


def test_tg_field_layout() -> None:
    """TG_start + TG_end + TG_freq partition a byte cleanly."""
    assert ac.TG_start | ac.TG_end | ac.TG_freq == 0xFF
    assert ac.TG_start & ac.TG_end == 0
    assert ac.TG_start & ac.TG_freq == 0


def test_name_codes_dense() -> None:
    """Eight NAME_* codes form ``{0..7}``."""
    codes = {
        ac.NAME_ENGLISH,
        ac.NAME_FRENCH,
        ac.NAME_GERMANIC,
        ac.NAME_IRISH,
        ac.NAME_ITALIAN,
        ac.NAME_JAPANESE,
        ac.NAME_SLAVIC,
        ac.NAME_SPANISH,
    }
    assert codes == set(range(8))


def test_langs_default() -> None:
    """Langs defaults to all-None / 0."""
    lang = ac.Langs()
    assert lang.tri_grams is None
    assert lang.entries == 0
    assert lang.hits == 0
    assert lang.last_prob == 0
    assert lang.eliminate == 0
    assert lang.prob == 0
    assert lang.name_type == 0


def test_langs_construction() -> None:
    """A Langs struct can be built for English."""
    lang = ac.Langs(
        tri_grams=b"\x80abc",
        entries=1000,
        name_type=ac.NAME_ENGLISH,
    )
    assert lang.entries == 1000
    assert lang.name_type == ac.NAME_ENGLISH
    assert lang.tri_grams is not None
    assert lang.tri_grams[0] == 0x80


def test_langs_uses_slots() -> None:
    """Langs uses slots=True."""
    lang = ac.Langs()
    assert not hasattr(lang, "__dict__")
