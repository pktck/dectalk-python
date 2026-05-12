"""Verify the TTS API constants match ttsapi.h and ttserr.h.

Re-parses the C ``#define`` values for the constants we expose in
:mod:`dectalk.api.ttsapi_constants` and asserts each Python literal
matches the C source byte-for-byte.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.api import ttsapi_constants as cc

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_TTSAPI = _SRC_ROOT / "src/dapi/src/api/ttsapi.h"
_TTSERR = _SRC_ROOT / "src/dapi/src/api/ttserr.h"

pytestmark = pytest.mark.skipif(
    not _TTSAPI.is_file() or not _TTSERR.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_HEX_RE = re.compile(r"0x[0-9a-fA-F]+L?")
_DEC_RE = re.compile(r"-?\d+")


def _parse_define(text: str, name: str, known: dict[str, int]) -> int:
    """Find ``#define NAME EXPR`` in ``text`` and evaluate EXPR.

    ``known`` is a lookup table of previously-resolved constants for
    expressions like ``(MMSYSERR_BASE + 7)``.
    """
    m = re.search(rf"#define\s+{re.escape(name)}\s+(.+?)(?://|/\*|$)", text, re.MULTILINE)
    assert m is not None, f"could not find #define {name}"
    expr = m.group(1).strip()
    # Hex literal (possibly with trailing 'L').
    hex_match = _HEX_RE.fullmatch(expr)
    if hex_match:
        return int(expr.rstrip("L"), 16)
    # Simple integer.
    if _DEC_RE.fullmatch(expr):
        return int(expr)
    # Arithmetic with known symbols.
    arith_expr = re.sub(r"\bL\b", "", expr)
    for k, v in sorted(known.items(), key=lambda kv: -len(kv[0])):
        arith_expr = re.sub(r"\b" + re.escape(k) + r"\b", str(v), arith_expr)
    # Strip 'L' suffixes from hex literals
    arith_expr = re.sub(r"(0x[0-9a-fA-F]+)L", r"\1", arith_expr)
    return int(eval(arith_expr))


def _ttsapi_text() -> str:
    return _TTSAPI.read_text(encoding="latin-1")


def _ttserr_text() -> str:
    return _TTSERR.read_text(encoding="latin-1")


@pytest.mark.parametrize(
    "name",
    [
        "OWN_AUDIO_DEVICE", "REPORT_OPEN_ERROR", "USE_SAPI5_AUDIO_DEVICE",
        "DO_NOT_USE_AUDIO_DEVICE",
        "MMSYSERR_BASE", "MMSYSERR_NOERROR",
        "TTS_NORMAL", "TTS_FORCE",
        "PAUL", "BETTY", "HARRY", "FRANK", "DENNIS",
        "KIT", "URSULA", "RITA", "WENDY",
        "TTS_MSG_BUFFER", "TTS_MSG_INDEX_MARK", "TTS_MSG_STATUS",
        "TTS_MSG_VISUAL", "TTS_MSG_BOOKMARK", "TTS_MSG_WORDPOS",
        "TTS_MSG_START", "TTS_MSG_STOP", "TTS_MSG_SENTENCE",
        "TTS_SILENT",
        "INPUT_CHARACTER_COUNT", "STATUS_SPEAKING", "WAVE_OUT_DEVICE_ID",
        "LOG_TEXT", "LOG_PHONEMES", "LOG_SYLLABLES",
        "TTS_AMERICAN_ENGLISH",
        "PROPER_NAME_PRONUNCIATION",
        "TTS_ASCII", "TTS_UNICODE",
        "FULL_RANGE_MARKS",
        "WAVE_FORMAT_08M16",
        # WAVE_FORMAT_08M08 aliases to WAVE_FORMAT_MULAW (0x0007) in
        # the platform's mmreg.h — see test_wave_format_08m08 below.
        "VOLUME_MAIN", "VOLUME_ATTENUATION",
        "TTS_NOT_SUPPORTED", "TTS_NOT_AVAILABLE", "TTS_LANG_ERROR",
        "VERSION_STRUCT_VER",
    ],
)  # fmt: skip
def test_ttsapi_constant_matches_c(name: str) -> None:
    """Each constant matches the C source's #define."""
    known = {"MMSYSERR_BASE": 0}
    expected = _parse_define(_ttsapi_text(), name, known)
    assert getattr(cc, name) == expected


_MMSYSERR_NAMES: tuple[str, ...] = (
    "MMSYSERR_ERROR", "MMSYSERR_BADDEVICEID", "MMSYSERR_NOTENABLED",
    "MMSYSERR_ALLOCATED", "MMSYSERR_INVALHANDLE", "MMSYSERR_NODRIVER",
    "MMSYSERR_NOMEM", "MMSYSERR_NOTSUPPORTED", "MMSYSERR_BADERRNUM",
    "MMSYSERR_INVALFLAG", "MMSYSERR_INVALPARAM", "MMSYSERR_HANDLEBUSY",
    "MMSYSERR_INVALIDALIAS", "MMSYSERR_LASTERROR",
)  # fmt: skip


@pytest.mark.parametrize("name", _MMSYSERR_NAMES)
def test_mmsyserr_arithmetic_matches_c(name: str) -> None:
    """``MMSYSERR_*`` arithmetic resolves to the right offset."""
    known = {"MMSYSERR_BASE": 0}
    expected = _parse_define(_ttsapi_text(), name, known)
    assert getattr(cc, name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "TTSERR_NOERROR",
        "TTSERR_NOMEM",
        "TTSERR_NOMAINDIC",
        "TTSERR_NOUSERDIC",
        "TTSERR_BADMAINDIC",
        "TTSERR_BADUSERDIC",
    ],
)
def test_ttserr_constant_matches_c(name: str) -> None:
    """Each ``TTSERR_*`` matches ttserr.h."""
    expected = _parse_define(_ttserr_text(), name, {})
    assert getattr(cc, name) == expected


_VTM_FLAGS: tuple[str, ...] = (
    "VTM_GV_OVER", "VTM_GV_UNDER", "VTM_GN_OVER", "VTM_GN_UNDER",
    "VTM_G2_OVER", "VTM_G2_UNDER", "VTM_G3_OVER", "VTM_G3_UNDER",
    "VTM_G4_OVER", "VTM_G4_UNDER", "VTM_G5_OVER", "VTM_G5_UNDER",
)  # fmt: skip


@pytest.mark.parametrize("name", _VTM_FLAGS)
def test_vtm_warning_flag_matches_c(name: str) -> None:
    """Each VTM overload/underload warning flag matches ttserr.h."""
    expected = _parse_define(_ttserr_text(), name, {})
    assert getattr(cc, name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "ERROR_IN_AUDIO_WRITE",
        "ERROR_OPENING_WAVE_OUTPUT_DEVICE",
        "ERROR_GETTING_DEVICE_CAPABILITIES",
        "ERROR_READING_DICTIONARY",
        "ERROR_WRITING_FILE",
        "ERROR_ALLOCATING_INDEX_MARK_MEMORY",
        "ERROR_OPENING_WAVE_FILE",
    ],
)
def test_audio_error_constant_matches_c(name: str) -> None:
    """Audio-device error codes match the C source."""
    expected = _parse_define(_ttsapi_text(), name, {})
    assert getattr(cc, name) == expected


def test_wave_format_08m08_is_mulaw() -> None:
    """WAVE_FORMAT_08M08 aliases to WAVE_FORMAT_MULAW = 0x0007.

    The C header writes ``#define WAVE_FORMAT_08M08 WAVE_FORMAT_MULAW``
    where WAVE_FORMAT_MULAW comes from mmreg.h. The Windows MMREG
    header standardises the value at 0x0007.
    """
    expected_mulaw = 0x0007
    assert expected_mulaw == cc.WAVE_FORMAT_08M08
