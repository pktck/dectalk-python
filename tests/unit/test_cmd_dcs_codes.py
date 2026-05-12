"""Verify DCS_* inline-command codes match esc.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import dcs_codes as dc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/esc.h")


def _parse_define(name: str, text: str) -> int | None:
    """Return the int value of ``#define <name> <expr>``.

    Accepts ``200``, ``SKIP_ESCAPE+0``, ``SKIP_ESCAPE + 11``, etc.
    """
    pattern = rf"^\s*#define\s+{re.escape(name)}\s+(.+?)(?://|/\*|$)"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            expr = match.group(1).strip()
            expr = expr.replace("SKIP_ESCAPE", str(dc.SKIP_ESCAPE))
            expr = expr.replace("ESCAPE_CODE", str(dc.ESCAPE_CODE))
            try:
                return int(eval(expr))
            except (SyntaxError, ValueError):
                return None
    return None


@pytest.fixture
def header_text() -> str:
    """De-CRLFed esc.h."""
    if not _C_HEADER.exists():
        pytest.skip("C source not available")
    return _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")


@pytest.mark.parametrize(
    ("py_attr", "c_name"),
    [
        ("SKIP_ESCAPE", "SKIP_ESCAPE"),
        ("ESCAPE_CODE", "ESCAPE_CODE"),
        ("DCS_RIGHT_BRACKET", "DCS_RIGHT_BRACKET"),
        ("DCS_RATE", "DCS_RATE"),
        ("DCS_NAME", "DCS_NAME"),
        ("DCS_COMMA", "DCS_COMMA"),
        ("DCS_PERIOD", "DCS_PERIOD"),
        ("DCS_PUNCT", "DCS_PUNCT"),
        ("DCS_NAME_PAUL", "DCS_NAME_PAUL"),
        ("DCS_NAME_BETTY", "DCS_NAME_BETTY"),
        ("DCS_NAME_HARRY", "DCS_NAME_HARRY"),
        ("DCS_NAME_FRANK", "DCS_NAME_FRANK"),
        ("DCS_NAME_DENNIS", "DCS_NAME_DENNIS"),
        ("DCS_NAME_THE_KID", "DCS_NAME_THE_KID"),
        ("DCS_NAME_URSULA", "DCS_NAME_URSULA"),
        ("DCS_NAME_RITA", "DCS_NAME_RITA"),
        ("DCS_NAME_WILLY", "DCS_NAME_WILLY"),
        ("DCS_LATIN", "DCS_LATIN"),
        ("DCS_VOLUME_SET", "DCS_VOLUME_SET"),
        ("DCS_VOLUME_UP", "DCS_VOLUME_UP"),
        ("DCS_VOLUME_DOWN", "DCS_VOLUME_DOWN"),
        ("DCS_VOLUME_LSET", "DCS_VOLUME_LSET"),
        ("DCS_VOLUME_LUP", "DCS_VOLUME_LUP"),
        ("DCS_VOLUME_LDOWN", "DCS_VOLUME_LDOWN"),
        ("DCS_VOLUME_RSET", "DCS_VOLUME_RSET"),
        ("DCS_VOLUME_RUP", "DCS_VOLUME_RUP"),
        ("DCS_VOLUME_RDOWN", "DCS_VOLUME_RDOWN"),
        ("DCS_VOLUME_SSET", "DCS_VOLUME_SSET"),
        ("DCS_VOLUME_ATT", "DCS_VOLUME_ATT"),
        ("VOLUME_SET", "VOLUME_SET"),
        ("VOLUME_UP", "VOLUME_UP"),
        ("VOLUME_DOWN", "VOLUME_DOWN"),
        ("DCS_INDEX", "DCS_INDEX"),
        ("DCS_INDEX_REPLY", "DCS_INDEX_REPLY"),
        ("DCS_INDEX_QUERY", "DCS_INDEX_QUERY"),
        ("DCS_INDEX_PAUSE", "DCS_INDEX_PAUSE"),
        ("DCS_INDEX_BOOKMARK", "DCS_INDEX_BOOKMARK"),
        ("DCS_INDEX_WORDPOS", "DCS_INDEX_WORDPOS"),
        ("DCS_INDEX_START", "DCS_INDEX_START"),
        ("DCS_INDEX_STOP", "DCS_INDEX_STOP"),
        ("DCS_INDEX_SENTENCE", "DCS_INDEX_SENTENCE"),
        ("DCS_INDEX_VOLUME", "DCS_INDEX_VOLUME"),
        ("DCS_INDEX_NOISE", "DCS_INDEX_NOISE"),
        ("DCS_ERROR", "DCS_ERROR"),
        ("DCS_MODE", "DCS_MODE"),
        ("DCS_LOG", "DCS_LOG"),
        ("DCS_SAY", "DCS_SAY"),
        ("DCS_PHONEME", "DCS_PHONEME"),
        ("DCS_PAUSE", "DCS_PAUSE"),
        ("DCS_RESUME", "DCS_RESUME"),
        ("DCS_SYNC", "DCS_SYNC"),
        ("DCS_FLUSH", "DCS_FLUSH"),
        ("DCS_ENABLE", "DCS_ENABLE"),
        ("DCS_DIAL", "DCS_DIAL"),
        ("DCS_TONE", "DCS_TONE"),
        ("DCS_TIMEOUT", "DCS_TIMEOUT"),
        ("DCS_DEFINE", "DCS_DEFINE"),
        ("DCS_PRONOUNCE", "DCS_PRONOUNCE"),
        ("DCS_DIGITIZED", "DCS_DIGITIZED"),
        ("DCS_LANGUAGE", "DCS_LANGUAGE"),
        ("DCS_REMOVE", "DCS_REMOVE"),
        ("DCS_TYPE", "DCS_TYPE"),
        ("DCS_STRESS", "DCS_STRESS"),
        ("DCS_BREAK", "DCS_BREAK"),
        ("DCS_CPU_RATE", "DCS_CPU_RATE"),
        ("DCS_CODE_PAGE", "DCS_CODE_PAGE"),
        ("DCS_DEBUG", "DCS_DEBUG"),
        ("DCS_SKIP", "DCS_SKIP"),
        ("DCS_GENDER", "DCS_GENDER"),
        ("TEXT_OUTPUT", "TEXT_OUTPUT"),
        ("ESCAPE_OUTPUT", "ESCAPE_OUTPUT"),
        ("SPC_INDEX_PAUSE", "SPC_INDEX_PAUSE"),
    ],
)
def test_dcs_constant_matches_c(header_text: str, py_attr: str, c_name: str) -> None:
    """Each DCS_* constant matches esc.h byte-for-byte."""
    c_value = _parse_define(c_name, header_text)
    assert c_value is not None, f"could not parse {c_name}"
    assert getattr(dc, py_attr) == c_value


def test_skip_escape_and_escape_code_partition() -> None:
    """``SKIP_ESCAPE`` (0x8000) and ``ESCAPE_CODE`` (0x7FFF) partition 16 bits."""
    assert dc.SKIP_ESCAPE == 0x8000
    assert dc.ESCAPE_CODE == 0x7FFF
    assert dc.SKIP_ESCAPE | dc.ESCAPE_CODE == 0xFFFF
    assert dc.SKIP_ESCAPE & dc.ESCAPE_CODE == 0


def test_voice_shortcuts_have_skip_escape_set() -> None:
    """All DCS_NAME_* voice shortcuts have the SKIP_ESCAPE bit set."""
    shortcuts = [
        dc.DCS_NAME_PAUL,
        dc.DCS_NAME_BETTY,
        dc.DCS_NAME_HARRY,
        dc.DCS_NAME_FRANK,
        dc.DCS_NAME_DENNIS,
        dc.DCS_NAME_THE_KID,
        dc.DCS_NAME_URSULA,
        dc.DCS_NAME_RITA,
        dc.DCS_NAME_WILLY,
        dc.DCS_NAME_CHRIS,
        dc.DCS_NAME_VAL,
    ]
    for code in shortcuts:
        assert code & dc.SKIP_ESCAPE
        assert (code & dc.ESCAPE_CODE) < 12


def test_voice_shortcuts_dense_ladder() -> None:
    """Slots 0..8 for Paul..Willy, 9 for Chris, 10 for Val (HLSYN build)."""
    assert dc.DCS_NAME_PAUL == dc.SKIP_ESCAPE + 0
    assert dc.DCS_NAME_BETTY == dc.SKIP_ESCAPE + 1
    assert dc.DCS_NAME_HARRY == dc.SKIP_ESCAPE + 2
    assert dc.DCS_NAME_FRANK == dc.SKIP_ESCAPE + 3
    assert dc.DCS_NAME_DENNIS == dc.SKIP_ESCAPE + 4
    assert dc.DCS_NAME_THE_KID == dc.SKIP_ESCAPE + 5
    assert dc.DCS_NAME_URSULA == dc.SKIP_ESCAPE + 6
    assert dc.DCS_NAME_RITA == dc.SKIP_ESCAPE + 7
    assert dc.DCS_NAME_WILLY == dc.SKIP_ESCAPE + 8
    assert dc.DCS_NAME_CHRIS == dc.SKIP_ESCAPE + 9
    assert dc.DCS_NAME_VAL == dc.SKIP_ESCAPE + 10


def test_index_codes_dense() -> None:
    """``DCS_INDEX``..``DCS_INDEX_NOISE`` is a dense 20..30 range."""
    codes = (
        dc.DCS_INDEX,
        dc.DCS_INDEX_REPLY,
        dc.DCS_INDEX_QUERY,
        dc.DCS_INDEX_PAUSE,
        dc.DCS_INDEX_BOOKMARK,
        dc.DCS_INDEX_WORDPOS,
        dc.DCS_INDEX_START,
        dc.DCS_INDEX_STOP,
        dc.DCS_INDEX_SENTENCE,
        dc.DCS_INDEX_VOLUME,
        dc.DCS_INDEX_NOISE,
    )
    assert codes == tuple(range(20, 31))


def test_output_type_codes_dense() -> None:
    """TEXT/ESCAPE/SPC_INDEX_PAUSE form a dense 0..2 ladder."""
    assert (dc.TEXT_OUTPUT, dc.ESCAPE_OUTPUT, dc.SPC_INDEX_PAUSE) == (0, 1, 2)
