"""Verify ls_defs.h miscellaneous atoms."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.dic.form_class_bits import FC_CHARACTER, FC_PREP, FC_VERB
from dectalk.lts import ls_misc as lm

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?(0[xX][0-9A-Fa-f]+|-?\d+)\)?\b"
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
        ("FORW", "FORW", 0),
        ("BACK", "BACK", 1),
        ("TWOPH", "TWOPH", 0x80),
        ("MSKPH", "MSKPH", 0x7F),
        ("ILLEGAL", "ILLEGAL", 0),
        ("OK", "OK", 1),
        ("TRYS", "TRYS", 2),
        ("DGC", "DGC", 1),
        ("INGS", "INGS", 1),
        ("ERS", "ERS", 1),
        ("SSES", "SSES", 1),
        ("LOOK_HIGHER", "LOOK_HIGHER", 0xFFFF),
        ("LOOK_LOWER", "LOOK_LOWER", 0xFFFE),
        ("NOMAP", "NOMAP", 0),
    ],
)
def test_misc_atom_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each ls_defs.h atom matches the C header."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(lm, py_attr) == expected


def test_twoph_mskph_complementary() -> None:
    """``TWOPH`` (0x80) and ``MSKPH`` (0x7F) partition a byte cleanly."""
    assert lm.TWOPH | lm.MSKPH == 0xFF
    assert lm.TWOPH & lm.MSKPH == 0


def test_phrase_aliases() -> None:
    """``VPHRASE`` / ``PPHRASE`` are FC bit-ORs."""
    assert lm.VPHRASE == FC_VERB | FC_CHARACTER
    assert lm.PPHRASE == FC_PREP | FC_CHARACTER


def test_look_sentinels_in_unsigned_range() -> None:
    """LOOK_HIGHER (0xFFFF) and LOOK_LOWER (0xFFFE) are the top two 16-bit
    sentinel values.
    """
    assert lm.LOOK_HIGHER == 0xFFFF
    assert lm.LOOK_LOWER == 0xFFFE
    assert lm.LOOK_HIGHER - 1 == lm.LOOK_LOWER


def test_forw_back_distinct() -> None:
    """``FORW`` (0) and ``BACK`` (1) are distinct booleans."""
    assert lm.FORW != lm.BACK
    assert {lm.FORW, lm.BACK} == {0, 1}


def test_cluster_validity_codes() -> None:
    """``ILLEGAL`` < ``OK`` < ``TRYS`` form a 3-level scale."""
    assert lm.ILLEGAL == 0
    assert lm.OK == 1
    assert lm.TRYS == 2
