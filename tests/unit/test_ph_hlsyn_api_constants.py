"""Verify HLSyn API constants match hlsynapi.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import hlsyn_api_constants as hac

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/hlsynapi.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for raw in text.splitlines():
        match = re.match(pattern, raw)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("MAXANFN", "MAXANFN", 9),
        ("MAXF1LOVERA", "MAXF1LOVERA", 11),
        ("MAXANA", "MAXANA", 6),
        ("MAXANB", "MAXANB", 6),
        ("MAXF1C", "MAXF1C", 7),
        ("MAXANK2", "MAXANK2", 17),
        ("ALV_RESOLUTION", "ALV_RESOLUTION", 50),
        ("ALV_F2_MIN", "ALV_F2_MIN", 800),
        ("ALV_F2_MAX", "ALV_F2_MAX", 2900),
        ("ALV_F3_MIN", "ALV_F3_MIN", 1800),
        ("ALV_F3_MAX", "ALV_F3_MAX", 3600),
    ],
)
def test_constant_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each HLSyn constant matches its C ``#define``."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(hac, py_attr) == expected


def test_alv_f2_points_derives_from_extents() -> None:
    """``ALV_F2_POINTS`` = (max - min) / resolution + 1 = 43."""
    expected = (hac.ALV_F2_MAX - hac.ALV_F2_MIN) // hac.ALV_RESOLUTION + 1
    assert hac.ALV_F2_POINTS == expected == 43


def test_alv_f3_points_derives_from_extents() -> None:
    """``ALV_F3_POINTS`` = (max - min) / resolution + 1 = 37."""
    expected = (hac.ALV_F3_MAX - hac.ALV_F3_MIN) // hac.ALV_RESOLUTION + 1
    assert hac.ALV_F3_POINTS == expected == 37


def test_alv_f2_grid_below_f3_grid() -> None:
    """Alveolar F2 grid covers a strictly lower band than the F3 grid."""
    assert hac.ALV_F2_MIN < hac.ALV_F3_MIN
    assert hac.ALV_F2_MAX < hac.ALV_F3_MAX


def test_max_table_sizes_all_positive() -> None:
    """Every TableRow row count is positive."""
    for name in ("MAXANFN", "MAXF1LOVERA", "MAXANA", "MAXANB", "MAXF1C", "MAXANK2"):
        assert getattr(hac, name) > 0


def test_ank2_is_largest_table() -> None:
    """``MAXANK2`` (17) is the largest HLSyn lookup table."""
    sizes = (hac.MAXANFN, hac.MAXF1LOVERA, hac.MAXANA, hac.MAXANB, hac.MAXF1C, hac.MAXANK2)
    assert max(sizes) == hac.MAXANK2 == 17
