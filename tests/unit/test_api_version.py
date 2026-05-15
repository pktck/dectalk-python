"""Bit-parity tests for :func:`dectalk.api.version.TextToSpeechVersion`."""

from __future__ import annotations

from dectalk.api.version import (
    DECTALK_VERSION_STRING,
    DLL_MAJ_VERSION,
    DLL_MIN_VERSION,
    DTALK_MAJ_VERSION,
    DTALK_MIN_VERSION,
    TextToSpeechVersion,
)


def test_packed_version_matches_coop_h_values() -> None:
    """Returned integer == ``(maj<<24)|(min<<16)|(dll_maj<<8)|dll_min``."""
    expected = (
        (DTALK_MAJ_VERSION << 24)
        | (DTALK_MIN_VERSION << 16)
        | (DLL_MAJ_VERSION << 8)
        | DLL_MIN_VERSION
    )
    assert TextToSpeechVersion() == expected


def test_version_string_written_to_out_param() -> None:
    """When ``VersionStr`` is provided, version string is written there."""
    out: list[str] = []
    TextToSpeechVersion(out)
    assert out == [DECTALK_VERSION_STRING]


def test_version_string_overwrites_existing_slot() -> None:
    """Pre-populated list slot is overwritten, not appended."""
    out: list[str] = ["leftover"]
    TextToSpeechVersion(out)
    assert out == [DECTALK_VERSION_STRING]


def test_version_packed_integer_is_0x05000300() -> None:
    """For the Linux ``us`` build, the packed value is exactly 0x05000300."""
    assert TextToSpeechVersion() == 0x05000300


def test_dectalk_version_string() -> None:
    """Faithful sprintf result ``v5.00 Github NORMAL US``."""
    assert DECTALK_VERSION_STRING == "v5.00 Github NORMAL US"
