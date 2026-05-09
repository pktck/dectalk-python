"""End-to-end tests for the phoneme-string → audio pipeline."""

from __future__ import annotations

import numpy as np

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.sequencer import _interpolate_frame, synthesize_phonemes


def test_interpolate_frame_endpoints() -> None:
    a = LLFrame(F0=1000, F1=500, AV=60)
    b = LLFrame(F0=2000, F1=1000, AV=70)
    assert _interpolate_frame(a, b, 0.0) == a
    assert _interpolate_frame(a, b, 1.0) == b


def test_interpolate_frame_midpoint() -> None:
    a = LLFrame(F0=1000, F1=500, AV=60)
    b = LLFrame(F0=2000, F1=1000, AV=70)
    mid = _interpolate_frame(a, b, 0.5)
    assert mid.F0 == 1500
    assert mid.F1 == 750
    assert mid.AV == 65


def test_empty_phoneme_list_returns_empty() -> None:
    out = synthesize_phonemes([])
    assert out.shape == (0,)
    assert out.dtype == np.int16


def test_single_vowel_produces_audio() -> None:
    out = synthesize_phonemes(["AH"])
    assert out.size > 0
    assert int(np.max(np.abs(out))) > 0


def test_hello_word_synthesizes_at_expected_duration() -> None:
    """HH+AH+L+OW should produce ~0.4-0.6 s of audio at default rate."""
    out = synthesize_phonemes(["HH", "AH", "L", "OW"])
    duration_s = out.size / 11025
    assert 0.3 <= duration_s <= 0.7


def test_silence_produces_silence() -> None:
    out = synthesize_phonemes(["SIL"])
    # Silence should be all (or near-all) zero. Allow a tiny startup transient.
    assert int(np.max(np.abs(out))) <= 100


def test_rate_factor_scales_duration() -> None:
    fast = synthesize_phonemes(["HH", "AH", "L", "OW"], rate=0.5)
    nominal = synthesize_phonemes(["HH", "AH", "L", "OW"], rate=1.0)
    slow = synthesize_phonemes(["HH", "AH", "L", "OW"], rate=2.0)
    assert fast.size < nominal.size < slow.size


def test_no_clipping_for_dense_fricatives() -> None:
    """Soft normaliser must keep the peak within int16 range even for /S/-heavy
    sequences."""
    out = synthesize_phonemes(["S", "P", "IY", "CH"])
    peak = int(np.max(np.abs(out)))
    assert peak < 32000  # leave a safety margin below the int16 max


def test_stress_digits_accepted_in_phoneme_strings() -> None:
    """CMUDict-style markers like AH1 should not break the sequencer."""
    out = synthesize_phonemes(["HH", "AH1", "L", "OW2"])
    assert out.size > 0
