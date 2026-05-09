"""Tests for the multi-voice preset system."""

from __future__ import annotations

import pytest

from dectalk.api import available_voices, speak
from dectalk.data.voices import PRESETS, get_preset


def test_nine_canonical_voices_present() -> None:
    expected = {"paul", "betty", "harry", "frank", "dennis", "kit", "ursula", "rita", "willy"}
    assert expected <= set(PRESETS.keys())


def test_get_preset_case_insensitive() -> None:
    assert get_preset("paul") is get_preset("PAUL")


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_preset("nobody")


def test_voice_changes_audible_pitch() -> None:
    """Different voices should produce different waveforms for the same text."""
    paul = speak("hello world", voice="paul")
    betty = speak("hello world", voice="betty")
    # Different F0 / formants must produce different sample arrays.
    assert paul.shape == betty.shape
    assert not (paul == betty).all()


def test_speak_unknown_voice_raises() -> None:
    with pytest.raises(KeyError):
        speak("hello", voice="not_a_voice")


def test_available_voices_listed() -> None:
    voices = available_voices()
    assert "paul" in voices
    assert voices == sorted(voices)  # alphabetical for stability
