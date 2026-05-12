"""Verify voice-parameter limits match ph_vdefi.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.inton_constants import ZAPB, ZAPF
from dectalk.ph.queue_structs import Limit
from dectalk.ph.voice_limits import limit

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_vdefi.c")


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_limit_table_matches_c_source() -> None:
    """All 38 (min, max) pairs match the C ``LIMIT limit[]`` literal."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"LIMIT\s+limit\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    # Substitute the two macro tokens before extracting integers.
    body = body.replace("ZAPF", str(ZAPF)).replace("ZAPB", str(ZAPB))
    values = [int(v) for v in re.findall(r"-?\d+", body)]
    assert len(values) == 2 * len(limit)
    for i, (low, high) in enumerate(zip(values[::2], values[1::2], strict=True)):
        assert limit[i] == Limit(low, high)


def test_limit_table_length() -> None:
    """The table has exactly 38 entries (one per SPD_* parameter)."""
    expected_count = 38
    assert len(limit) == expected_count


def test_sex_range() -> None:
    """SPD_SEX is binary 0..1."""
    assert limit[0] == Limit(0, 1)


def test_pitch_range_above_zero() -> None:
    """SPD_AP (average pitch) min is 50, max is 350."""
    assert limit[3] == Limit(50, 350)


def test_head_size_range() -> None:
    """SPD_HS (head size) ranges 65..145 (% of Paul's head)."""
    assert limit[9] == Limit(65, 145)


def test_formant_limits_use_zapf() -> None:
    """Formant limits (F4, F5, P4, P5) cap at :data:`ZAPF`."""
    assert limit[10].l_max == ZAPF  # F4
    assert limit[12].l_max == ZAPF  # F5
    assert limit[14].l_max == ZAPF  # P4
    assert limit[15].l_max == ZAPF  # P5


def test_bandwidth_limits_use_zapb() -> None:
    """Bandwidth limits (B4, B5) cap at :data:`ZAPB`."""
    assert limit[11].l_max == ZAPB
    assert limit[13].l_max == ZAPB


def test_gain_limits_uniform_87() -> None:
    """Gain parameters (GF, GH, GV, GN, G1..G4, LO) all cap at 87 dB."""
    for i in range(16, 25):
        assert limit[i] == Limit(0, 87), f"limit[{i}] is {limit[i]}"


def test_os_range_signed_16bit() -> None:
    """SPD_OS / SPD_OQ uses the full signed 16-bit range."""
    assert limit[-2] == Limit(-32768, 32767)


def test_nm_range_8() -> None:
    """SPD_NM caps at 8."""
    assert limit[-1] == Limit(0, 8)
