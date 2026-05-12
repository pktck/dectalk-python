"""Verify TTS feature-bit flags match ttsfeat.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.api import tts_feats as tf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/api/ttsfeat.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int-or-hex>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(0[xX][0-9A-Fa-f]+L?|\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1).rstrip("L")
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("TTS_FEATS_MULTILANG", "TTS_FEATS_MULTILANG", 0x01),
        ("TTS_FEATS_TYPINGMODE", "TTS_FEATS_TYPINGMODE", 0x02),
        ("TTS_FEATS_FASTTALK", "TTS_FEATS_FASTTALK", 0x04),
        ("TTS_FEATS_HIGHTLIGHTING", "TTS_FEATS_HIGHTLIGHTING", 0x08),
        ("TTS_FEATS_MENUTALK", "TTS_FEATS_MENUTALK", 0x10),
    ],
)
def test_tts_feats_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each TTS_FEATS_* flag matches ttsfeat.h byte-for-byte."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(tf, py_attr) == expected


def test_tts_feats_are_distinct_single_bits() -> None:
    """All 5 feature bits are single-bit and non-overlapping."""
    flags = [
        tf.TTS_FEATS_MULTILANG,
        tf.TTS_FEATS_TYPINGMODE,
        tf.TTS_FEATS_FASTTALK,
        tf.TTS_FEATS_HIGHTLIGHTING,
        tf.TTS_FEATS_MENUTALK,
    ]
    for flag in flags:
        assert flag > 0
        assert flag & (flag - 1) == 0
    assert len(set(flags)) == 5


def test_tts_feats_fit_in_low_byte() -> None:
    """The 5 features fit in the low byte of a 32-bit feature word."""
    combined = (
        tf.TTS_FEATS_MULTILANG
        | tf.TTS_FEATS_TYPINGMODE
        | tf.TTS_FEATS_FASTTALK
        | tf.TTS_FEATS_HIGHTLIGHTING
        | tf.TTS_FEATS_MENUTALK
    )
    assert combined == 0x1F
