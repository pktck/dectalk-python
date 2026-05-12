"""Public TTS API constants from ``ttsapi.h`` and ``ttserr.h``.

Translated from ``src/dapi/src/api/ttsapi.h`` and
``src/dapi/src/api/ttserr.h``. These are the named integer constants
that callers of the DECtalk TTS API pass via int arguments — startup
flags, MMRESULT error codes, speaker IDs, log channels, message types,
wave format IDs, etc.

Already-exposed subset (in ``dectalk._capi``):
    TTS_NORMAL, TTS_FORCE, WAVE_FORMAT_*.

This module exposes the full ttsapi.h surface so the public Python API
can re-export them with the names the C clients expect.
"""

from __future__ import annotations

from typing import Final

# -- Startup-option flags ---------------------------------------------------

OWN_AUDIO_DEVICE: Final[int] = 0x00000001
REPORT_OPEN_ERROR: Final[int] = 0x00000002
USE_SAPI5_AUDIO_DEVICE: Final[int] = 0x40000000
DO_NOT_USE_AUDIO_DEVICE: Final[int] = 0x80000000


# -- MMRESULT error codes ---------------------------------------------------

MMSYSERR_BASE: Final[int] = 0
MMSYSERR_NOERROR: Final[int] = 0
MMSYSERR_ERROR: Final[int] = MMSYSERR_BASE + 1
MMSYSERR_BADDEVICEID: Final[int] = MMSYSERR_BASE + 2
MMSYSERR_NOTENABLED: Final[int] = MMSYSERR_BASE + 3
MMSYSERR_ALLOCATED: Final[int] = MMSYSERR_BASE + 4
MMSYSERR_INVALHANDLE: Final[int] = MMSYSERR_BASE + 5
MMSYSERR_NODRIVER: Final[int] = MMSYSERR_BASE + 6
MMSYSERR_NOMEM: Final[int] = MMSYSERR_BASE + 7
MMSYSERR_NOTSUPPORTED: Final[int] = MMSYSERR_BASE + 8
MMSYSERR_BADERRNUM: Final[int] = MMSYSERR_BASE + 9
MMSYSERR_INVALFLAG: Final[int] = MMSYSERR_BASE + 10
MMSYSERR_INVALPARAM: Final[int] = MMSYSERR_BASE + 11
MMSYSERR_HANDLEBUSY: Final[int] = MMSYSERR_BASE + 12
MMSYSERR_INVALIDALIAS: Final[int] = MMSYSERR_BASE + 13
MMSYSERR_LASTERROR: Final[int] = MMSYSERR_BASE + 13


# -- TTSERR_* error codes ---------------------------------------------------

TTSERR_NOERROR: Final[int] = 0
TTSERR_NOMEM: Final[int] = 1
TTSERR_NOMAINDIC: Final[int] = 2
TTSERR_NOUSERDIC: Final[int] = 3
TTSERR_BADMAINDIC: Final[int] = 4
TTSERR_BADUSERDIC: Final[int] = 5


# -- VTM overload/underload warning flags -----------------------------------

VTM_GV_OVER: Final[int] = 0x00080000
VTM_GV_UNDER: Final[int] = 0x00040000
VTM_GN_OVER: Final[int] = 0x00020000
VTM_GN_UNDER: Final[int] = 0x00010000
VTM_G2_OVER: Final[int] = 0x08000000
VTM_G2_UNDER: Final[int] = 0x04000000
VTM_G3_OVER: Final[int] = 0x02000000
VTM_G3_UNDER: Final[int] = 0x01000000
VTM_G4_OVER: Final[int] = 0x00800000
VTM_G4_UNDER: Final[int] = 0x00400000
VTM_G5_OVER: Final[int] = 0x00200000
VTM_G5_UNDER: Final[int] = 0x00100000


# -- Audio-device error codes -----------------------------------------------

ERROR_IN_AUDIO_WRITE: Final[int] = 1
ERROR_OPENING_WAVE_OUTPUT_DEVICE: Final[int] = 2
ERROR_GETTING_DEVICE_CAPABILITIES: Final[int] = 3
ERROR_READING_DICTIONARY: Final[int] = 4
ERROR_WRITING_FILE: Final[int] = 5
ERROR_ALLOCATING_INDEX_MARK_MEMORY: Final[int] = 6
ERROR_OPENING_WAVE_FILE: Final[int] = 7


# -- Speaker IDs (the numeric IDs the C library uses) -----------------------

PAUL: Final[int] = 0
BETTY: Final[int] = 1
HARRY: Final[int] = 2
FRANK: Final[int] = 3
DENNIS: Final[int] = 4
KIT: Final[int] = 5
URSULA: Final[int] = 6
RITA: Final[int] = 7
WENDY: Final[int] = 8


# -- Speak() force flags ----------------------------------------------------

TTS_NORMAL: Final[int] = 0
TTS_FORCE: Final[int] = 1


# -- TTS message types (callback message IDs) -------------------------------

TTS_MSG_BUFFER: Final[int] = 9
TTS_MSG_INDEX_MARK: Final[int] = 1
TTS_MSG_STATUS: Final[int] = 2
TTS_MSG_VISUAL: Final[int] = 3
TTS_MSG_BOOKMARK: Final[int] = 4
TTS_MSG_WORDPOS: Final[int] = 5
TTS_MSG_START: Final[int] = 6
TTS_MSG_STOP: Final[int] = 7
TTS_MSG_SENTENCE: Final[int] = 8

TTS_SILENT: Final[int] = 0x2


# -- GetCaps() capability indices -------------------------------------------

INPUT_CHARACTER_COUNT: Final[int] = 0
STATUS_SPEAKING: Final[int] = 1
WAVE_OUT_DEVICE_ID: Final[int] = 2


# -- Log channel bitmask ----------------------------------------------------

LOG_TEXT: Final[int] = 0x0001
LOG_PHONEMES: Final[int] = 0x0002
LOG_SYLLABLES: Final[int] = 0x0010


# -- Language IDs -----------------------------------------------------------

TTS_AMERICAN_ENGLISH: Final[int] = 1


# -- Pronunciation modes ----------------------------------------------------

PROPER_NAME_PRONUNCIATION: Final[int] = 0x00000001


# -- Encoding flags ---------------------------------------------------------

TTS_ASCII: Final[int] = 0
TTS_UNICODE: Final[int] = 1


# -- Index-mark range -------------------------------------------------------

FULL_RANGE_MARKS: Final[int] = 0xF011


# -- WAVE format IDs --------------------------------------------------------

WAVE_FORMAT_08M16: Final[int] = 0x00002000
# WAVE_FORMAT_MULAW (0x0007) — the C source aliases WAVE_FORMAT_08M08 to it
# on platforms where MULAW is defined; we expose the explicit value.
WAVE_FORMAT_08M08: Final[int] = 0x0007


# -- Volume targets ---------------------------------------------------------

VOLUME_MAIN: Final[int] = 1
VOLUME_ATTENUATION: Final[int] = 2


# -- Special-result sentinels -----------------------------------------------

TTS_NOT_SUPPORTED: Final[int] = 0x7FFF
TTS_NOT_AVAILABLE: Final[int] = 0x7FFE
TTS_LANG_ERROR: Final[int] = 0x4000


# -- Output-state codes (from tts.h) ----------------------------------------

STATE_OUTPUT_AUDIO: Final[int] = 0
"""TTS engine routing audio to the OS audio device."""

STATE_OUTPUT_MEMORY: Final[int] = 1
"""TTS engine writing audio into a caller-provided memory buffer."""

STATE_OUTPUT_WAVE_FILE: Final[int] = 2
"""TTS engine writing audio to a WAVE file."""

STATE_OUTPUT_LOG_FILE: Final[int] = 3
"""TTS engine writing phoneme / syllable log to a file."""

STATE_OUTPUT_NULL: Final[int] = 4
"""TTS engine discarding all output (silent processing)."""

STATE_OUTPUT_SAPI5: Final[int] = 5
"""TTS engine routing audio through the SAPI5 interface."""


# -- License-error codes ----------------------------------------------------

LIC_NO_PAK: Final[int] = 1
"""No product authorization key (PAK) found."""

LIC_NO_MORE_UNITS: Final[int] = 2
"""License count exhausted."""

LIC_UNKNOWN_ERR: Final[int] = 3
"""Unknown licensing error."""


# -- Audio file header offsets ----------------------------------------------

RIFF_HEADER_OFFSET: Final[int] = 36
"""Byte offset of audio data in a RIFF (WAV) file header."""

AU_HEADER_OFFSET: Final[int] = 32
"""Byte offset of audio data in an AU file header."""


# -- Misc -------------------------------------------------------------------

VERSION_STRUCT_VER: Final[int] = 0x0001


__all__ = [
    "AU_HEADER_OFFSET",
    "BETTY",
    "DENNIS",
    "DO_NOT_USE_AUDIO_DEVICE",
    "ERROR_ALLOCATING_INDEX_MARK_MEMORY",
    "ERROR_GETTING_DEVICE_CAPABILITIES",
    "ERROR_IN_AUDIO_WRITE",
    "ERROR_OPENING_WAVE_FILE",
    "ERROR_OPENING_WAVE_OUTPUT_DEVICE",
    "ERROR_READING_DICTIONARY",
    "ERROR_WRITING_FILE",
    "FRANK",
    "FULL_RANGE_MARKS",
    "HARRY",
    "INPUT_CHARACTER_COUNT",
    "KIT",
    "LIC_NO_MORE_UNITS",
    "LIC_NO_PAK",
    "LIC_UNKNOWN_ERR",
    "LOG_PHONEMES",
    "LOG_SYLLABLES",
    "LOG_TEXT",
    "MMSYSERR_ALLOCATED",
    "MMSYSERR_BADDEVICEID",
    "MMSYSERR_BADERRNUM",
    "MMSYSERR_BASE",
    "MMSYSERR_ERROR",
    "MMSYSERR_HANDLEBUSY",
    "MMSYSERR_INVALFLAG",
    "MMSYSERR_INVALHANDLE",
    "MMSYSERR_INVALIDALIAS",
    "MMSYSERR_INVALPARAM",
    "MMSYSERR_LASTERROR",
    "MMSYSERR_NODRIVER",
    "MMSYSERR_NOERROR",
    "MMSYSERR_NOMEM",
    "MMSYSERR_NOTENABLED",
    "MMSYSERR_NOTSUPPORTED",
    "OWN_AUDIO_DEVICE",
    "PAUL",
    "PROPER_NAME_PRONUNCIATION",
    "REPORT_OPEN_ERROR",
    "RIFF_HEADER_OFFSET",
    "RITA",
    "STATE_OUTPUT_AUDIO",
    "STATE_OUTPUT_LOG_FILE",
    "STATE_OUTPUT_MEMORY",
    "STATE_OUTPUT_NULL",
    "STATE_OUTPUT_SAPI5",
    "STATE_OUTPUT_WAVE_FILE",
    "STATUS_SPEAKING",
    "TTSERR_BADMAINDIC",
    "TTSERR_BADUSERDIC",
    "TTSERR_NOERROR",
    "TTSERR_NOMAINDIC",
    "TTSERR_NOMEM",
    "TTSERR_NOUSERDIC",
    "TTS_AMERICAN_ENGLISH",
    "TTS_ASCII",
    "TTS_FORCE",
    "TTS_LANG_ERROR",
    "TTS_MSG_BOOKMARK",
    "TTS_MSG_BUFFER",
    "TTS_MSG_INDEX_MARK",
    "TTS_MSG_SENTENCE",
    "TTS_MSG_START",
    "TTS_MSG_STATUS",
    "TTS_MSG_STOP",
    "TTS_MSG_VISUAL",
    "TTS_MSG_WORDPOS",
    "TTS_NORMAL",
    "TTS_NOT_AVAILABLE",
    "TTS_NOT_SUPPORTED",
    "TTS_SILENT",
    "TTS_UNICODE",
    "URSULA",
    "USE_SAPI5_AUDIO_DEVICE",
    "VERSION_STRUCT_VER",
    "VOLUME_ATTENUATION",
    "VOLUME_MAIN",
    "VTM_G2_OVER",
    "VTM_G2_UNDER",
    "VTM_G3_OVER",
    "VTM_G3_UNDER",
    "VTM_G4_OVER",
    "VTM_G4_UNDER",
    "VTM_G5_OVER",
    "VTM_G5_UNDER",
    "VTM_GN_OVER",
    "VTM_GN_UNDER",
    "VTM_GV_OVER",
    "VTM_GV_UNDER",
    "WAVE_FORMAT_08M08",
    "WAVE_FORMAT_08M16",
    "WAVE_OUT_DEVICE_ID",
    "WENDY",
]
