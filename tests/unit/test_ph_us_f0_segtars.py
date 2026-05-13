"""Verify US F0 segmental-target tables match ph_drwt02.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.us_f0_segtars import us_f0fsegtars, us_f0msegtars

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_drwt02.c")


def _parse_array(name: str, after_offset: int) -> tuple[int, ...]:
    """Parse the HLSYN-build version of ``us_f0Xsegtars[]`` after a given offset."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    # The C source has two definitions of each table (#ifndef HLSYN + HLSYN);
    # we want the second (HLSYN) definition, after byte offset `after_offset`.
    pattern = rf"const\s+short\s+{re.escape(name)}\s*\[\s*\]\s*=\s*\{{(.*?)\}};"
    found = list(re.finditer(pattern, text, re.DOTALL))
    assert len(found) >= 2, f"expected ≥2 definitions of {name}, got {len(found)}"
    # Take the second occurrence (HLSYN branch).
    body = found[1].group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return tuple(int(v) for v in re.findall(r"-?\d+", body))


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_us_f0msegtars_matches_c() -> None:
    """The male table matches the HLSYN-branch C definition."""
    expected = _parse_array("us_f0msegtars", 0)
    assert us_f0msegtars == expected


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_us_f0fsegtars_matches_c() -> None:
    """The female table matches the HLSYN-branch C definition."""
    expected = _parse_array("us_f0fsegtars", 0)
    assert us_f0fsegtars == expected


def test_us_f0msegtars_length() -> None:
    """Male table has 59 entries (US allophones SIL..CZ)."""
    expected_count = 59
    assert len(us_f0msegtars) == expected_count


def test_us_f0fsegtars_length() -> None:
    """Female table has 67 entries (extra LY tuning tail)."""
    expected_count = 67
    assert len(us_f0fsegtars) == expected_count


def test_silence_entry_is_50() -> None:
    """Both tables start with SI (silence) = 50 Hz times 10 boost."""
    assert us_f0msegtars[0] == 50
    assert us_f0fsegtars[0] == 50


def test_iy_segment_boost() -> None:
    """IY (front high vowel /i/) gets a +140 Hz times 10 F0 boost in both."""
    iy_index = 1  # second slot after SIL
    assert us_f0msegtars[iy_index] == 140
    assert us_f0fsegtars[iy_index] == 140


def test_male_z_dip() -> None:
    """The male Z (slot 42) drops F0 by 200 (a known C-source quirk).

    The C row says ``DH S Z SH ZH P B T D K`` — Z is the third entry
    in row 5, so slot = 4*10 + 2 = 42.
    """
    slot_z = 42
    assert us_f0msegtars[slot_z] == -200
