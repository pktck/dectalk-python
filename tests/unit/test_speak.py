"""End-to-end tests for the public text → audio API."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dectalk.api import UnknownWordError, speak, text_to_phonemes, to_wav


def test_text_to_phonemes_hello_world() -> None:
    phones = text_to_phonemes("hello world")
    assert "HH" in phones
    assert "L" in phones
    assert "ER1" in phones
    assert "D" in phones


def test_text_to_phonemes_inserts_pauses() -> None:
    phones = text_to_phonemes("hello, world.")
    sil_count = phones.count("SIL")
    assert sil_count >= 2  # one for the comma, one for the period


def test_speak_returns_int16_pcm() -> None:
    samples = speak("hello world")
    assert samples.dtype == np.int16
    assert samples.size > 0
    assert int(np.max(np.abs(samples))) > 0


def test_speak_unknown_word_raises() -> None:
    with pytest.raises(UnknownWordError, match="not in the bundled lexicon"):
        speak("xyzzynotaword")


def test_to_wav_writes_valid_file(tmp_path: Path) -> None:
    out = tmp_path / "hello.wav"
    to_wav("hello world", out)
    assert out.exists()
    assert out.stat().st_size > 1000  # synthesis output must be substantial


def test_speak_rate_scales_duration() -> None:
    fast = speak("hello world", rate=0.5)
    slow = speak("hello world", rate=2.0)
    assert fast.size < slow.size


def test_capitalisation_is_irrelevant() -> None:
    a = text_to_phonemes("Hello World")
    b = text_to_phonemes("hello world")
    c = text_to_phonemes("HELLO WORLD")
    assert a == b == c
