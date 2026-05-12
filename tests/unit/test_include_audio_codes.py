"""Verify the audio-device state codes from audiodef.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import audio_codes as ac

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/audiodef.h")


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
        ("AUDIO_DEVICE_INACTIVE", "AUDIO_DEVICE_INACTIVE", 0),
        ("AUDIO_DEVICE_STARTING_UP", "AUDIO_DEVICE_STARTING_UP", 1),
        ("AUDIO_DEVICE_ACTIVE", "AUDIO_DEVICE_ACTIVE", 2),
        ("AUDIO_DEVICE_SHUTTING_DOWN", "AUDIO_DEVICE_SHUTTING_DOWN", 3),
    ],
)
def test_audio_state(py_attr: str, c_name: str, expected: int) -> None:
    """Each audio-device state code matches audiodef.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(ac, py_attr) == expected


def test_states_dense() -> None:
    """Four states form the dense set ``{0, 1, 2, 3}``."""
    states = {
        ac.AUDIO_DEVICE_INACTIVE,
        ac.AUDIO_DEVICE_STARTING_UP,
        ac.AUDIO_DEVICE_ACTIVE,
        ac.AUDIO_DEVICE_SHUTTING_DOWN,
    }
    assert states == {0, 1, 2, 3}
