"""Verify ph_defs.h numeric tuning constants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import numeric_constants as nc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(-?\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FRAC_ONE", "FRAC_ONE", 16384),
        ("FRAC_HALF", "FRAC_HALF", 8192),
        ("FRAC_3_4THS", "FRAC_3_4THS", 12288),
        ("FRAC_3_HALVES", "FRAC_3_HALVES", 24567),
        ("F0", "F0", 0),
        ("F1", "F1", 1),
        ("F2", "F2", 2),
        ("F3", "F3", 3),
        ("FZ", "FZ", 4),
        ("F2max", "F2max", 2500),
        ("F3max", "F3max", 3500),
        ("MALE", "MALE", 1),
        ("FEMALE", "FEMALE", 0),
        ("SYNC_PARS", "SYNC_PARS", 0),
    ],
)
def test_numeric_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each numeric constant matches ph_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(nc, py_attr) == expected


def test_frac_q14_relationships() -> None:
    """The Q14 fractions form the expected mathematical ratios."""
    assert nc.FRAC_HALF == nc.FRAC_ONE // 2
    assert nc.FRAC_3_4THS == nc.FRAC_ONE * 3 // 4
    # FRAC_3_HALVES is intentionally 24567 (not 24576) — copied verbatim.
    assert nc.FRAC_3_HALVES == 24567


def test_voice_pars_is_40() -> None:
    """``VOICE_PARS = 40`` (the BATS#667 update). Old build had 21."""
    assert nc.VOICE_PARS == 40


def test_male_female_distinct() -> None:
    """Voice-sex codes are 0 (female) and 1 (male)."""
    assert nc.MALE == 1
    assert nc.FEMALE == 0


def test_formant_caps_ordered() -> None:
    """F2max < F3max (overload caps grow with formant index)."""
    assert nc.F2max < nc.F3max


def test_param_indices_dense() -> None:
    """``F0..FZ`` parameter indices form the dense set ``{0, 1, 2, 3, 4}``."""
    indices = {nc.F0, nc.F1, nc.F2, nc.F3, nc.FZ}
    assert indices == {0, 1, 2, 3, 4}


def test_max_speakers() -> None:
    """``MAX_SPEAKERS`` (10) matches ph_data.h."""
    assert nc.MAX_SPEAKERS == 10
