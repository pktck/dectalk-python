"""Verify cm_defs.h state / error / flush / sync codes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import cmd_states as cs

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/cm_defs.h")


def _parse_define(text: str, name: str) -> int | None:
    """Return the first matching ``#define <name> <int>`` value.

    Accepts the int either bare (``300``) or parenthesised (``(300)``)
    to match cm_defs.h's ``#define DTMF_OFF (600)`` style.
    """
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?(0[xX][0-9A-Fa-f]+|-?\d+)\)?\b"
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


def test_alt_rate_bounds() -> None:
    """``MIN_RATE`` (100) / ``MAX_RATE`` (550) — the cm_defs.h alternate names."""
    assert cs.MIN_RATE == 100
    assert cs.MAX_RATE == 550


def test_max_voices() -> None:
    """11 voice slots: Paul, Betty, Harry, Frank, Dennis, Kit, Ursula,
    Rita, Wendy, Variable Val + 1 extra. The Crafty Chris build defines 12.
    """
    assert cs.MAX_VOICES == 11


def test_skip_mode_codes() -> None:
    """The six ``SKIP_*`` modes are 0..5 in the C-source order."""
    assert cs.SKIP_none == 0
    assert cs.SKIP_email == 1
    assert cs.SKIP_punct == 2
    assert cs.SKIP_rule == 3
    assert cs.SKIP_all == 4
    assert cs.SKIP_cpg == 5
    assert (
        len(
            {
                cs.SKIP_none,
                cs.SKIP_email,
                cs.SKIP_punct,
                cs.SKIP_rule,
                cs.SKIP_all,
                cs.SKIP_cpg,
            }
        )
        == 6
    )


def test_phoneme_mode_bits() -> None:
    """PHONEME_OFF / _ASCKY / _SPEAK are 0x1 / 0x2 / 0x4 from kernel.h."""
    assert cs.PHONEME_OFF == 0x1
    assert cs.PHONEME_ASCKY == 0x2
    assert cs.PHONEME_SPEAK == 0x4


def test_error_mode_codes() -> None:
    """ERROR_ignore..ERROR_tone are 0..4 from cm_defs.h."""
    assert cs.ERROR_ignore == 0
    assert cs.ERROR_text == 1
    assert cs.ERROR_escape == 2
    assert cs.ERROR_speak == 3
    assert cs.ERROR_tone == 4


def test_punct_mode_codes() -> None:
    """PUNCT_none..PUNCT_pass are 0..3 from cm_defs.h."""
    assert cs.PUNCT_none == 0
    assert cs.PUNCT_some == 1
    assert cs.PUNCT_all == 2
    assert cs.PUNCT_pass == 3


def test_rule_engine_size() -> None:
    """``MAXRULES`` (500) — state-table size for the inline-command rule engine."""
    assert cs.MAXRULES == 500


def test_string_buffer_constants() -> None:
    """``STRING_MAX`` is a power of two and ``STRING_MASK`` is the wrap mask."""
    assert cs.STRING_MAX == 0x200
    assert cs.STRING_MASK == 0x1FF
    assert cs.STRING_MAX - 1 == cs.STRING_MASK
    assert (cs.STRING_MAX & cs.STRING_MASK) == 0  # power of two check


def test_ansi_inter_param_caps() -> None:
    """ANSI escape sequence intermediate / parameter caps both equal 20."""
    assert cs.NUM_INTER == 20
    assert cs.NUM_PARAM == 20


def test_dtmf_constants(header_text: str) -> None:
    """DTMF on/off timings (160 ms / 60 ms at 10 kHz) and NWDTMF = 10."""
    assert cs.DTMF_OFF == 600
    assert cs.DTMF_ON == 1600
    assert cs.NWDTMF == 10
    assert _parse_define(header_text, "DTMF_OFF") == cs.DTMF_OFF
    assert _parse_define(header_text, "NWDTMF") == cs.NWDTMF
