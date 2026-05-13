"""Verify sample-rate constants match the C headers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include.sample_rate import MULAW_SAMPLE_RATE, PC_SAMPLE_RATE

_SAMPRATE_H: Path = Path("/tmp/dectalk-src/src/dapi/src/include/samprate.h")
_VISMPRAT_H: Path = Path("/tmp/dectalk-src/src/dapi/src/vtm/vismprat.h")


@pytest.mark.skipif(not _SAMPRATE_H.exists(), reason="C source not available")
def test_mulaw_rate_matches_c() -> None:
    """``MULAW_SAMPLE_RATE`` matches samprate.h's #define."""
    text = _SAMPRATE_H.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(r"#define\s+MULAW_SAMPLE_RATE\s+(\d+)", text)
    assert match is not None
    assert int(match.group(1)) == MULAW_SAMPLE_RATE == 8000


@pytest.mark.skipif(not _VISMPRAT_H.exists(), reason="C source not available")
def test_pc_rate_matches_c() -> None:
    """``PC_SAMPLE_RATE`` matches vismprat.h's #define."""
    text = _VISMPRAT_H.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(r"#define\s+PC_SAMPLE_RATE\s+(\d+)", text)
    assert match is not None
    assert int(match.group(1)) == PC_SAMPLE_RATE == 11025


def test_pc_rate_is_higher_than_mulaw() -> None:
    """The PC-resolution rate is higher than the mu-law rate."""
    assert PC_SAMPLE_RATE > MULAW_SAMPLE_RATE


def test_pc_rate_is_11025() -> None:
    """DECtalk's native rate is 11.025 kHz."""
    assert PC_SAMPLE_RATE == 11025


def test_mulaw_rate_is_8000() -> None:
    """Mu-law output rate is 8 kHz (telephone-quality)."""
    assert MULAW_SAMPLE_RATE == 8000
