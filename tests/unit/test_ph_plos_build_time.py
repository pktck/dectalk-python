"""Verify plosive build-time constants match ph_draw.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.plos_build_time import BPLOS_BUILD_TIME, LPLOS_BUILD_TIME

_C_FILE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_draw.c")


def _parse_short_const(name: str) -> int | None:
    """Return the int value of ``const short <name> = N;``."""
    if not _C_FILE.exists():
        return None
    text = _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"const\s+short\s+{re.escape(name)}\s*=\s*(\d+)\s*;"
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_lplos_build_time_matches_c() -> None:
    """``LPLOS_BUILD_TIME`` matches the C ``lplos_build_time`` constant."""
    c_value = _parse_short_const("lplos_build_time")
    assert c_value == 7
    assert c_value == LPLOS_BUILD_TIME


@pytest.mark.skipif(not _C_FILE.exists(), reason="C source not available")
def test_bplos_build_time_matches_c() -> None:
    """``BPLOS_BUILD_TIME`` matches the C ``bplos_build_time`` constant."""
    c_value = _parse_short_const("bplos_build_time")
    assert c_value == 7
    assert c_value == BPLOS_BUILD_TIME


def test_both_build_times_match() -> None:
    """Both build-time thresholds are deliberately equal in the C source."""
    assert LPLOS_BUILD_TIME == BPLOS_BUILD_TIME == 7
