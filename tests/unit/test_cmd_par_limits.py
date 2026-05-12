"""Verify parser buffer-size limits match par_def.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import par_limits as pl

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/par_def.h")


def _parse_defines(name: str) -> list[int]:
    """Return all occurrences of ``#define <name> <int>`` (both branches)."""
    if not _C_HEADER.exists():
        return []
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    return [int(m.group(1)) for m in re.finditer(pattern, text, re.MULTILINE)]


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "win32_value", "non_win32_value"),
    [
        ("PAR_MAX_INPUT_ARRAY", "PAR_MAX_INPUT_ARRAY", 500, 300),
        ("PAR_MAX_OUTPUT_ARRAY", "PAR_MAX_OUTPUT_ARRAY", 500, 300),
        ("PAR_ROLLING_STOP_VALUE", "PAR_ROLLING_STOP_VALUE", 300, 200),
    ],
)
def test_par_limit_branched_define(
    py_attr: str,
    c_name: str,
    win32_value: int,
    non_win32_value: int,
) -> None:
    """``#define`` appears twice in par_def.h (Win32 + non-Win32); Python
    uses the Win32 value.
    """
    defines = _parse_defines(c_name)
    assert win32_value in defines, f"{c_name} Win32 value not in C source"
    assert non_win32_value in defines, f"{c_name} non-Win32 value not in C source"
    assert getattr(pl, py_attr) == win32_value


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("PAR_MAX_RETURN_LEVEL", "PAR_MAX_RETURN_LEVEL", 10),
        ("PAR_MIN_INPUT_SIZE", "PAR_MIN_INPUT_SIZE", 5),
    ],
)
def test_par_limit_single_define(py_attr: str, c_name: str, expected: int) -> None:
    """Single-branch defines match exactly."""
    defines = _parse_defines(c_name)
    assert defines == [expected]
    assert getattr(pl, py_attr) == expected


def test_min_below_rolling_below_max() -> None:
    """``min < rolling_stop < max`` — the buffer policy invariants."""
    assert pl.PAR_MIN_INPUT_SIZE < pl.PAR_ROLLING_STOP_VALUE
    assert pl.PAR_ROLLING_STOP_VALUE < pl.PAR_MAX_INPUT_ARRAY


def test_input_equals_output() -> None:
    """Input and output buffer sizes are equal."""
    assert pl.PAR_MAX_INPUT_ARRAY == pl.PAR_MAX_OUTPUT_ARRAY
