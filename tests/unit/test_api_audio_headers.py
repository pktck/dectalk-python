"""Verify WaveFileHdr / AuFileHdr structs mirror tts.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.api.audio_headers import AuFileHdr, WaveFileHdr

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/api/tts.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_wave_file_hdr_fields_match_c() -> None:
    """The C struct's field set matches the Python dataclass."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+WAVE_FILE_HDR_TAG\s*\{(.*?)\}\s*WAVE_FILE_HDR_T\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    c_fields = {
        name.rstrip(";").strip()
        for name in re.findall(
            r"^\s*(?:DWORD|WORD|char)\s+(\w+)",
            body,
            re.MULTILINE,
        )
    }
    py_fields = set(WaveFileHdr.__slots__)
    assert c_fields == py_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_au_file_hdr_fields_match_c() -> None:
    """The C struct's field set matches the AuFileHdr dataclass."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+AU_FILE_HDR_TAG\s*\{(.*?)\}\s*AU_FILE_HDR_T\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    c_fields = {
        name.rstrip(";").strip()
        for name in re.findall(
            r"^\s*(?:DWORD|WORD|char)\s+(\w+)",
            body,
            re.MULTILINE,
        )
    }
    py_fields = set(AuFileHdr.__slots__)
    assert c_fields == py_fields


def test_wave_default_values_are_dectalk_default() -> None:
    """Default-constructed WaveFileHdr is DECtalk's native 11025 Hz mono 16-bit."""
    hdr = WaveFileHdr()
    assert hdr.psRiff == b"RIFF"
    assert hdr.psWaveFmt == b"WAVEfmt "
    assert hdr.psData == b"data"
    assert hdr.wFormatTag == 1
    assert hdr.wNumberOfChannels == 1
    assert hdr.dwSamplesPerSecond == 11025
    assert hdr.wBitsPerSample == 16
    assert hdr.dwAvgBytesPerSecond == hdr.dwSamplesPerSecond * hdr.wBitsPerSample // 8


def test_au_default_values() -> None:
    """Default-constructed AuFileHdr is .snd magic, 32-byte header."""
    hdr = AuFileHdr()
    assert hdr.magic == b".snd"
    assert hdr.hdr_size == 32
    assert hdr.encoding == 1
    assert hdr.sample_rate == 8000
    assert hdr.channels == 1
    assert len(hdr.comment) == 8


def test_wave_uses_slots() -> None:
    """WaveFileHdr is a slots dataclass."""
    hdr = WaveFileHdr()
    assert not hasattr(hdr, "__dict__")


def test_au_uses_slots() -> None:
    """AuFileHdr is a slots dataclass."""
    hdr = AuFileHdr()
    assert not hasattr(hdr, "__dict__")
