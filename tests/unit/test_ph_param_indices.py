"""Verify PH parameter-array and SPC frame indices match ph_defs.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import param_indices as pi

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("F0", "F0", 0),
        ("F1", "F1", 1),
        ("F2", "F2", 2),
        ("F3", "F3", 3),
        ("FZ", "FZ", 4),
        ("B1", "B1", 5),
        ("B2", "B2", 6),
        ("B3", "B3", 7),
        ("AV", "AV", 8),
        ("AP", "AP", 9),
        ("A2", "A2", 10),
        ("A3", "A3", 11),
        ("A4", "A4", 12),
        ("A5", "A5", 13),
        ("A6", "A6", 14),
        ("AB", "AB", 15),
        ("TILT", "TILT", 16),
        ("AREAB", "AREAB", 17),
        ("AREAL", "AREAL", 18),
        ("AREAG", "AREAG", 19),
        ("AREAN", "AREAN", 20),
        ("PRESS", "PRESS", 21),
        ("TONGUEBODY", "TONGUEBODY", 22),
        ("CHINK", "CHINK", 23),
        ("UEL", "UEL", 24),
        ("DC", "DC", 35),
        ("OQU", "OQU", 36),
        ("BRST", "BRST", 37),
    ],
)
def test_param_index_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """PH parameter-array index matches ph_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(pi, py_attr) == expected


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("OUT_AP", "OUT_AP", 0),
        ("OUT_F1", "OUT_F1", 1),
        ("OUT_A2", "OUT_A2", 2),
        ("OUT_A3", "OUT_A3", 3),
        ("OUT_A4", "OUT_A4", 4),
        ("OUT_A5", "OUT_A5", 5),
        ("OUT_A6", "OUT_A6", 6),
        ("OUT_AB", "OUT_AB", 7),
        ("OUT_TLT", "OUT_TLT", 8),
        ("OUT_T0", "OUT_T0", 9),
        ("OUT_AV", "OUT_AV", 10),
        ("OUT_F2", "OUT_F2", 11),
        ("OUT_F3", "OUT_F3", 12),
        ("OUT_FZ", "OUT_FZ", 13),
        ("OUT_B1", "OUT_B1", 14),
        ("OUT_B2", "OUT_B2", 15),
        ("OUT_B3", "OUT_B3", 16),
        ("OUT_PH", "OUT_PH", 17),
        ("OUT_DU", "OUT_DU", 18),
        ("OUT_PH2", "OUT_PH2", 19),
        ("OUT_FNP", "OUT_FNP", 20),
        ("OUT_GF", "OUT_GF", 21),
        ("OUT_F4", "OUT_F4", 22),
        ("OUT_SEX", "OUT_SEX", 23),
        ("OUT_DP", "OUT_DP", 24),
        ("OUT_AG", "OUT_AG", 25),
        ("OUT_AL", "OUT_AL", 26),
        ("OUT_AN", "OUT_AN", 27),
        ("OUT_ABLADE", "OUT_ABLADE", 28),
        ("OUT_PS", "OUT_PS", 29),
        ("OUT_CNK", "OUT_CNK", 30),
        ("OUT_DC", "OUT_DC", 31),
        ("OUT_UE", "OUT_UE", 32),
        ("OUT_OQ", "OUT_OQ", 33),
        ("OUT_BNP", "OUT_BNP", 34),
        ("OUT_BRST", "OUT_BRST", 35),
        ("OUT_ATB", "OUT_ATB", 36),
        ("OUT_PLACE", "OUT_PLACE", 37),
    ],
)
def test_out_index_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """SPC frame data offset matches ph_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(pi, py_attr) == expected


def test_param_indices_dense_through_arean() -> None:
    """``F0``..``AREAN`` occupy 21 consecutive slots (0..20)."""
    indices = [
        pi.F0,
        pi.F1,
        pi.F2,
        pi.F3,
        pi.FZ,
        pi.B1,
        pi.B2,
        pi.B3,
        pi.AV,
        pi.AP,
        pi.A2,
        pi.A3,
        pi.A4,
        pi.A5,
        pi.A6,
        pi.AB,
        pi.TILT,
        pi.AREAB,
        pi.AREAL,
        pi.AREAG,
        pi.AREAN,
    ]
    assert indices == list(range(21))


def test_new_vtm_param_indices_have_gap() -> None:
    """``UEL`` (24) jumps to ``DC`` (35) — non-contiguous NEW_VTM range."""
    assert pi.UEL == 24
    assert pi.DC == 35
    assert pi.OQU == 36
    assert pi.BRST == 37
    assert pi.DC - pi.UEL > 1


def test_out_frame_starts_with_aspiration() -> None:
    """``OUT_AP`` (0), not ``OUT_F1`` (1) — the SPC frame leads with AP."""
    assert pi.OUT_AP == 0
    assert pi.OUT_F1 == 1


def test_out_classic_block_dense() -> None:
    """OUT_AP..OUT_PH2 fill 20 consecutive offsets (0..19)."""
    classic = [
        pi.OUT_AP,
        pi.OUT_F1,
        pi.OUT_A2,
        pi.OUT_A3,
        pi.OUT_A4,
        pi.OUT_A5,
        pi.OUT_A6,
        pi.OUT_AB,
        pi.OUT_TLT,
        pi.OUT_T0,
        pi.OUT_AV,
        pi.OUT_F2,
        pi.OUT_F3,
        pi.OUT_FZ,
        pi.OUT_B1,
        pi.OUT_B2,
        pi.OUT_B3,
        pi.OUT_PH,
        pi.OUT_DU,
        pi.OUT_PH2,
    ]
    assert classic == list(range(20))


def test_out_new_vtm_block_dense() -> None:
    """OUT_FNP..OUT_PLACE fill 18 consecutive offsets (20..37)."""
    new_vtm = [
        pi.OUT_FNP,
        pi.OUT_GF,
        pi.OUT_F4,
        pi.OUT_SEX,
        pi.OUT_DP,
        pi.OUT_AG,
        pi.OUT_AL,
        pi.OUT_AN,
        pi.OUT_ABLADE,
        pi.OUT_PS,
        pi.OUT_CNK,
        pi.OUT_DC,
        pi.OUT_UE,
        pi.OUT_OQ,
        pi.OUT_BNP,
        pi.OUT_BRST,
        pi.OUT_ATB,
        pi.OUT_PLACE,
    ]
    assert new_vtm == list(range(20, 38))
