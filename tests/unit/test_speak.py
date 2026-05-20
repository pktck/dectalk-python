"""End-to-end tests for the public text → audio API."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dectalk.api import UnknownWordError, speak, text_to_phonemes, to_wav
from dectalk.api.speak import _pump_frames_to_samples, _speak_via_python


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


def test_text_to_phonemes_unknown_word_raises_when_lts_disabled() -> None:
    """``text_to_phonemes`` (approximate path) still honours ``lts_fallback``."""
    with pytest.raises(UnknownWordError, match="not in the us lexicon"):
        text_to_phonemes("xyzzynotaword", lts_fallback=False)


def test_speak_pronounces_unknown_word_via_c_lts() -> None:
    """``speak`` routes through _capi; the C library always pronounces."""
    samples = speak("xyzzy")
    assert samples.size > 0


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


# -- DECTALK_FULL_PIPELINE gate --------------------------------------------


def test_full_pipeline_gate_walks_phsettar_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """``DECTALK_FULL_PIPELINE=1`` runs init_phclause + phsettar end-to-end.

    The wiring layer tokenizes the text, maps ARPABET to US allophone
    codes, populates ``DphT``, calls ``init_phclause``, and iterates
    ``phsettar`` over every nphone. The final ``NotImplementedError``
    fires at the ph_draw / hlsyn frame-emission boundary -- everything
    before it executes.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    with pytest.raises(NotImplementedError, match=r"ph_draw"):
        _speak_via_python(
            text="hello world",
            rate=1.0,
            voice=None,
            lang="us",
            lts_fallback=True,
        )


def test_full_pipeline_gate_short_circuits_for_empty_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty/un-tokenizable input returns zero samples (no phsettar walk)."""
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    samples = _speak_via_python(
        text="",
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert len(samples) == 0


def test_full_pipeline_gate_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``DECTALK_FULL_PIPELINE=1``, the legacy path runs.

    Tests that the gate is truly opt-in: with the env var unset, the
    legacy approximate pipeline produces samples without raising.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.delenv("DECTALK_FULL_PIPELINE", raising=False)
    samples = _speak_via_python(
        text="hello",
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert len(samples) > 0


def test_pump_frames_to_samples_empty_returns_zero() -> None:
    """``_pump_frames_to_samples([], None)`` short-circuits to zero samples."""
    out = _pump_frames_to_samples([], None)
    assert len(out) == 0
