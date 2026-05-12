"""Verify ph_inton2.c hat-rise / clause / delta constants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import inton_constants as ic

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_inton2.c")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <integer-or-hex>``."""
    if not _C_SOURCE.exists():
        return None
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(0[xX][0-9A-Fa-f]+|-?\d+)"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("BEFORE_HAT_RISE", "BEFORE_HAT_RISE", 0),
        ("ON_TOP_OF_HAT", "ON_TOP_OF_HAT", 1),
        ("AFTER_FINAL_FALL", "AFTER_FINAL_FALL", 2),
        ("AFTER_NONFINAL_FALL", "AFTER_NONFINAL_FALL", 3),
    ],
)
def test_hat_rise_phases(py_attr: str, c_name: str, expected: int) -> None:
    """Four hat-rise phase codes 0..3 match ph_inton2.c."""
    assert _parse_define(c_name) == expected
    assert getattr(ic, py_attr) == expected


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("DONTKNOW", "DONTKNOW", 0),
        ("QUESTCLAUSE", "QUESTCLAUSE", 1),
        ("VERBPHRASE", "VERBPHRASE", 2),
        ("PERIODCLAUSE", "PERIODCLAUSE", 3),
    ],
)
def test_clause_types(py_attr: str, c_name: str, expected: int) -> None:
    """Four clause-type codes 0..3 match ph_inton2.c."""
    assert _parse_define(c_name) == expected
    assert getattr(ic, py_attr) == expected


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("EMPH_FALL", "EMPH_FALL", 1),
        ("DELTAEMPH_SPEC", "DELTAEMPH_SPEC", 505),
        ("DELTAEMPH", "DELTAEMPH", 501),
        ("DELTARISE", "DELTARISE", 200),
        ("DELTAFINAL", "DELTAFINAL", 100),
        ("FINAL_FALL", "FINAL_FALL", 1),
    ],
)
def test_delta_tuning(py_attr: str, c_name: str, expected: int) -> None:
    """F0 delta tuning constants match ph_inton2.c."""
    assert _parse_define(c_name) == expected
    assert getattr(ic, py_attr) == expected


def test_hat_phases_dense_set() -> None:
    """The four hat-rise phases form the dense set ``{0, 1, 2, 3}``."""
    phases = {
        ic.BEFORE_HAT_RISE,
        ic.ON_TOP_OF_HAT,
        ic.AFTER_FINAL_FALL,
        ic.AFTER_NONFINAL_FALL,
    }
    assert phases == {0, 1, 2, 3}


def test_clause_types_dense_set() -> None:
    """The four clause types form the dense set ``{0, 1, 2, 3}``."""
    clauses = {ic.DONTKNOW, ic.QUESTCLAUSE, ic.VERBPHRASE, ic.PERIODCLAUSE}
    assert clauses == {0, 1, 2, 3}


def test_f0_modes() -> None:
    """``NORMAL`` .. ``PHONE_TARGETS_SPECIFIED`` are 1..5 per viphdefs.h."""
    assert ic.NORMAL == 1
    assert ic.HAT_LOCATIONS_SPECIFIED == 2
    assert ic.HAT_F0_SIZES_SPECIFIED == 3
    assert ic.SINGING == 4
    assert ic.PHONE_TARGETS_SPECIFIED == 5


def test_zap_values() -> None:
    """``ZAPF`` and ``ZAPB`` are both 6000 (non-MSDOS / HLSYN build)."""
    assert ic.ZAPF == 6000
    assert ic.ZAPB == 6000


def test_safety_offset() -> None:
    """``SAFETY`` (8) — offset between phonemes[] and allophons[]."""
    assert ic.SAFETY == 8
