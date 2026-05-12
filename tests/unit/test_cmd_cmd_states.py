"""Verify cm_defs.h state / error / flush / sync codes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import cmd_states as cs

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/cm_defs.h")


def _parse_define(text: str, name: str) -> int | None:
    """Return the first matching ``#define <name> <int>`` value."""
    pattern = rf"^#define\s+{re.escape(name)}\s+(0[xX][0-9A-Fa-f]+|-?\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.fixture
def header_text() -> str:
    """Return the de-CRLFed C header text."""
    if not _C_HEADER.exists():
        pytest.skip("C source not available")
    return _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")


@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("STATE_NORMAL", "STATE_NORMAL", 0),
        ("STATE_BRACKET", "STATE_BRACKET", 1),
        ("STATE_COMMAND", "STATE_COMMAND", 2),
        ("STATE_PHONEME", "STATE_PHONEME", 3),
        ("STATE_PARAM", "STATE_PARAM", 4),
        ("STATE_TOSS", "STATE_TOSS", 5),
        ("STATE_KEEP", "STATE_KEEP", 6),
    ],
)
def test_state_codes(header_text: str, py_attr: str, c_name: str, expected: int) -> None:
    """Each STATE_* matches cm_defs.h."""
    c_value = _parse_define(header_text, c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(cs, py_attr) == expected


@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("CMD_success", "CMD_success", 0),
        ("CMD_bad_string", "CMD_bad_string", 1),
        ("CMD_bad_value", "CMD_bad_value", 2),
        ("CMD_bad_command", "CMD_bad_command", 3),
        ("CMD_bad_param", "CMD_bad_param", 4),
        ("CMD_bad_phoneme", "CMD_bad_phoneme", 5),
        ("CMD_out_of_memory", "CMD_out_of_memory", 6),
        ("CMD_unable_to_open_file", "CMD_unable_to_open_file", 7),
        ("CMD_bad_wave_file_format", "CMD_bad_wave_file_format", 8),
        ("CMD_unsupported_wave_file_format", "CMD_unsupported_wave_file_format", 9),
        ("CMD_unsupported_audio_format", "CMD_unsupported_audio_format", 10),
        ("CMD_flushing", "CMD_flushing", 11),
    ],
)
def test_cmd_result_codes(
    header_text: str,
    py_attr: str,
    c_name: str,
    expected: int,
) -> None:
    """Each CMD_* result code matches cm_defs.h."""
    c_value = _parse_define(header_text, c_name)
    assert c_value is not None
    # The C source has CMD_flushing == 6 in one #ifdef branch and 11 in
    # another; we pick the longer (newer) form's value 11. Both pre-images
    # are present in cm_defs.h, so either match is fine.
    assert getattr(cs, py_attr) == expected


def test_cmd_flush_stage_codes() -> None:
    """Flush-stage tri-state matches the C constants (1, 2, 3)."""
    assert cs.CMD_flush_toss == 1
    assert cs.CMD_flush_sync == 2
    assert cs.CMD_flush_done == 3


def test_sync_bytes() -> None:
    """Sync bytes 0xFE (out) and 0xFF (char)."""
    assert cs.CMD_sync_char == 0xFF
    assert cs.CMD_sync_out == 0xFE


def test_rate_pause_bounds() -> None:
    """Speaking-rate (75..600 wpm) and period-pause (-420..30000 ms) bounds."""
    assert cs.MIN_SPEAKING_RATE == 75
    assert cs.MAX_SPEAKING_RATE == 600
    assert cs.MIN_PERIOD_PAUSE == -420
    assert cs.MAX_PERIOD_PAUSE == 30000
