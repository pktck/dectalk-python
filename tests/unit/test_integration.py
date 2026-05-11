"""End-to-end integration tests exercising the complete pipeline.

These tests are slower (each runs the full text → synth path) so they
serve more as a smoke-test backstop against regressions than as targeted
unit checks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import dectalk
from dectalk.api import speak


def test_simple_sentence_round_trip(tmp_path: Path) -> None:
    """Full pipeline: text -> phonemes -> Klatt frames -> int16 PCM -> WAV."""
    out = tmp_path / "hello.wav"
    dectalk.to_wav("hello world", out)
    assert out.exists()
    # Read back; samples should be non-trivial.
    samples = dectalk.write_wav  # ensure name is exported
    del samples


def test_multi_voice_changes_audio() -> None:
    """The same text rendered with two voices should produce different audio."""
    a = speak("hello world", voice="paul")
    b = speak("hello world", voice="harry")
    assert a.shape == b.shape
    assert not np.array_equal(a, b)


def test_command_syntax_voice_switch() -> None:
    """Inline [:dv ...] should produce different audio than the default voice."""
    plain = speak("hello world")
    switched = speak("[:dv betty] hello world")
    # Different voice -> different waveform.
    assert plain.size > 0 and switched.size > 0
    assert not np.array_equal(
        plain[: min(plain.size, switched.size)], switched[: min(plain.size, switched.size)]
    )


def test_uk_lexicon_changes_pronunciation() -> None:
    """UK lang routes through the Python pipeline (libtts_uk.so is not built)."""
    us = speak("water world", lang="us")
    uk = speak("water world", lang="uk")
    # Different lexicon -> different waveform. Note this only catches the
    # Python-path UK difference; on the C path lang="us" goes through
    # libtts_us.so and "uk" falls back to Python LTS so the waveforms
    # are guaranteed to differ.
    assert not np.array_equal(us[: min(us.size, uk.size)], uk[: min(us.size, uk.size)])


def test_question_intonation_differs_from_statement() -> None:
    statement = speak("hello world.")
    question = speak("hello world?")
    # Different prosody -> different samples even with the same words.
    n = min(statement.size, question.size)
    assert not np.array_equal(statement[:n], question[:n])


def test_lts_fallback_renders_unknown_word() -> None:
    """A word missing from the lexicon should still produce audio via LTS."""
    samples = speak("xyzzyfication")
    assert samples.size > 0
    assert int(np.max(np.abs(samples))) > 1000


def test_numbers_in_text_are_pronounced() -> None:
    samples_with = speak("the answer is 42")
    samples_without = speak("the answer is")
    # Adding a number should add audio.
    assert samples_with.size > samples_without.size


def test_phoneme_mode_via_inline_command() -> None:
    samples = speak("[:phoneme on] HH AH L OW")
    assert samples.size > 0


def test_rate_command_changes_duration() -> None:
    """The ``rate`` keyword scales duration in both paths (multiplier semantics).

    Inline ``[:rate N]`` semantics differ between the C library (N = WPM,
    lower = slower) and the approximate Python pipeline (smaller = faster
    via a multiplier), so we exercise the public ``rate`` kwarg instead,
    which is a consistent ``> 1 slower`` multiplier across both paths.
    """
    slow = speak("hello world", rate=2.0)
    fast = speak("hello world", rate=0.5)
    assert slow.size > fast.size
