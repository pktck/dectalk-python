"""Verify ph_defs.h sentence-structure feature bits."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import feature_bits as fb

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``. C uses octal
    constants (``03``, ``040``, ``0400``); the regex catches both
    octal-prefixed and decimal values.
    """
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    # The C source uses both octal and hex constants; match each.
    octal_pattern = rf"^#define\s+{re.escape(name)}\s+0(\d+)\b"
    hex_pattern = rf"^#define\s+{re.escape(name)}\s+0x([0-9A-Fa-f]+)\b"
    decimal_pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        match = re.match(octal_pattern, line)
        if match:
            return int(match.group(1), 8)
        match = re.match(hex_pattern, line)
        if match:
            return int(match.group(1), 16)
        match = re.match(decimal_pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FSTRESS", "FSTRESS", 0o3),
        ("FNOSTRESS", "FNOSTRESS", 0),
        ("FSTRESS_1", "FSTRESS_1", 0o1),
        ("FSTRESS_2", "FSTRESS_2", 0o2),
        ("FEMPHASIS", "FEMPHASIS", 0o3),
        ("FWINITC", "FWINITC", 0o4),
        ("FOPEN_SYL", "FOPEN_SYL", 0o4),
        ("FSYL_SHIFT", "FSYL_SHIFT", 3),
        ("FBISYL", "FBISYL", 0o10),
        ("FTRISYL", "FTRISYL", 0o20),
        ("FMULTISYL", "FMULTISYL", 0o30),
        ("FFIRSTSYL", "FFIRSTSYL", 0o10),
        ("FMEDIALSYL", "FMEDIALSYL", 0o20),
        ("FFINALSYL", "FFINALSYL", 0o30),
        ("FTYPESYL", "FTYPESYL", 0o30),
        ("FBOUNDARY", "FBOUNDARY", 0o740),
        ("FSYBNEXT", "FSYBNEXT", 0o40),
        ("FMBNEXT", "FMBNEXT", 0o100),
        ("FWBNEXT", "FWBNEXT", 0o140),
        ("FPPNEXT", "FPPNEXT", 0o200),
        ("FVPNEXT", "FVPNEXT", 0o240),
        ("FRELNEXT", "FRELNEXT", 0o300),
        ("FCBNEXT", "FCBNEXT", 0o340),
        ("FPERNEXT", "FPERNEXT", 0o400),
        ("FQUENEXT", "FQUENEXT", 0o440),
        ("FEXCLNEXT", "FEXCLNEXT", 0o500),
        ("FSENTENDS", "FSENTENDS", 0o400),
        ("FHAT_BEGINS", "FHAT_BEGINS", 0o1000),
        ("FHAT_ENDS", "FHAT_ENDS", 0o2000),
        ("FDUMMY_VOWEL", "FDUMMY_VOWEL", 0o4000),
        ("FBLOCK", "FBLOCK", 0o20000),
        ("FDOUBLECONS", "FDOUBLECONS", 0x40000),
        ("FSBOUND", "FSBOUND", 0o1000000),
        ("FCODA", "FCODA", 0o2000000),
        ("FISBOUND", "FISBOUND", 0o3000000),
        ("F_TIME_RISE", "F_TIME_RISE", 0o1000000),
        ("FOTHER_SHIFT", "FOTHER_SHIFT", 12),
    ],
)
def test_feature_bit_matches_c_source(
    py_attr: str,
    c_name: str,
    expected: int,
) -> None:
    """Every feature-bit constant matches ph_defs.h."""
    c_value = _parse_define(c_name)
    if c_value is None:
        pytest.skip(f"{c_name} not parseable")
    assert c_value == expected, f"{c_name} expected {expected:#o}, got {c_value:#o}"
    assert getattr(fb, py_attr) == expected


def test_fstress_field_packs_into_low_two_bits() -> None:
    """``FSTRESS`` masks the four stress levels into 2 bits."""
    assert fb.FSTRESS == 3
    assert fb.FNOSTRESS & fb.FSTRESS == 0
    assert fb.FSTRESS_1 & fb.FSTRESS == 1
    assert fb.FSTRESS_2 & fb.FSTRESS == 2
    assert fb.FEMPHASIS & fb.FSTRESS == 3


def test_syllable_count_uses_fsyl_shift() -> None:
    """``FBISYL``/``FTRISYL``/``FMULTISYL`` are 1/2/3 shifted up by 3."""
    assert fb.FBISYL >> fb.FSYL_SHIFT == 1
    assert fb.FTRISYL >> fb.FSYL_SHIFT == 2
    assert fb.FMULTISYL >> fb.FSYL_SHIFT == 3


def test_fother_composite() -> None:
    """``FOTHER`` is the OR of FSBOUND / FCODA / FBLOCK / FWINITC."""
    assert fb.FOTHER == (fb.FSBOUND | fb.FCODA | fb.FBLOCK | fb.FWINITC)


def test_at_bottom_top_of_hat() -> None:
    """AT_BOTTOM_OF_HAT (1) and AT_TOP_OF_HAT (2) — hat-position codes."""
    assert fb.AT_BOTTOM_OF_HAT == 1
    assert fb.AT_TOP_OF_HAT == 2


def test_fhyphenated() -> None:
    """``FHYPHENATED`` (0o10000) — hyphenated-word marker."""
    assert fb.FHYPHENATED == 0o10000


def test_pho_fea_max() -> None:
    """``PHO_FEA_MAX`` (14) — feature count cap."""
    assert fb.PHO_FEA_MAX == 14
