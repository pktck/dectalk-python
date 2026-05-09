"""Tests for :func:`dectalk.hlsyn.synthesize.ll_synthesize` and the vowel demo.

The end-to-end test here is the Phase 1 deliverable verification: a hand-built
``/ah/`` (open-mid back unrounded vowel, F1≈730, F2≈1090, F3≈2440) frame
should produce a non-trivial periodic waveform whose spectrum has peaks
near those formant frequencies.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.voice import SOURCE_NATURAL
from dectalk.nt.audio import write_wav


def _ah_speaker() -> Speaker:
    """A reasonable Klatt speaker (Perfect Paul-ish defaults)."""
    return Speaker(
        DU=0,
        UI=110,  # 110 samples/frame at 11025 Hz = ~10 ms frames
        SR=11025,
        NF=5,
        SS=SOURCE_NATURAL,
        RS=8191,
        SB=0,
        CP=0,
        OS=0,
        GV=60,
        GH=60,
        GF=60,
    )


def _ah_frame(f0_hz: float = 122.0) -> LLFrame:
    """Build a frame for a steady /ah/ (Klatt 1980 reference values)."""
    return LLFrame(
        F0=round(f0_hz * 10),
        AV=60,
        OQ=50,
        SQ=200,
        TL=0,
        FL=0,
        DI=0,
        Ah=0,
        Af=0,
        F1=730,
        B1=90,
        F2=1090,
        B2=110,
        F3=2440,
        B3=170,
        F4=3500,
        B4=250,
        F5=4500,
        B5=300,
        F6=5500,
        B6=500,
        FNP=270,
        BNP=100,
        FNZ=270,
        BNZ=100,
        FTP=2150,
        BTP=180,
        FTZ=2150,
        BTZ=180,
        # Parallel-formant amps default to 0 (cascade-only synthesis).
    )


def test_ll_synthesize_fills_output_buffer() -> None:
    synth = LLSynth(spkr=_ah_speaker())
    frame = _ah_frame()
    wave = np.zeros(synth.spkr.UI, dtype=np.int16)
    ll_synthesize(synth, frame, wave)
    # Should have produced *something* — silent output would be a bug.
    assert int(np.max(np.abs(wave))) > 0


def test_ll_synthesize_silent_frame_returns_zero() -> None:
    synth = LLSynth(spkr=_ah_speaker())
    frame = LLFrame()  # all zero -> silent
    wave = np.zeros(synth.spkr.UI, dtype=np.int16)
    clip = ll_synthesize(synth, frame, wave)
    assert clip == 0
    assert int(np.max(np.abs(wave))) == 0


def test_ah_vowel_periodicity_matches_f0() -> None:
    """With F0 = 100 Hz, the synthesized vowel should be periodic at ~110 samples
    (11025/100). Detect this via autocorrelation."""
    synth = LLSynth(spkr=_ah_speaker())
    target_f0 = 100.0
    frame = _ah_frame(f0_hz=target_f0)
    n_frames = 50  # ~0.5 s of audio
    wave = np.zeros(synth.spkr.UI * n_frames, dtype=np.int16)
    for fi in range(n_frames):
        ll_synthesize(synth, frame, wave[fi * synth.spkr.UI : (fi + 1) * synth.spkr.UI])

    # Skip the first 0.1 s (transient) then autocorrelate.
    transient = int(0.1 * synth.spkr.SR)
    sig = wave[transient:].astype(np.float64)
    sig -= np.mean(sig)
    expected_period = round(synth.spkr.SR / target_f0)

    # Look for the autocorrelation peak in a window around the expected period.
    # Use a narrow search range so the test isn't dominated by sub-harmonics.
    search_lo = expected_period - 5
    search_hi = expected_period + 5
    n = len(sig)
    autocorr = [
        float(np.dot(sig[: n - lag], sig[lag:n])) for lag in range(search_lo, search_hi + 1)
    ]
    best_lag_offset = int(np.argmax(autocorr))
    best_period = search_lo + best_lag_offset
    assert abs(best_period - expected_period) <= 2


@pytest.mark.audio
def test_ah_vowel_writes_wav(tmp_path: Path) -> None:
    """End-to-end: synthesize 1 s of /ah/ and write it to a WAV file."""
    out_path = tmp_path / "ah.wav"

    synth = LLSynth(spkr=_ah_speaker())
    frame = _ah_frame()
    n_frames = 100  # 1 s at 110 samples/frame
    wave = np.zeros(synth.spkr.UI * n_frames, dtype=np.int16)
    for fi in range(n_frames):
        ll_synthesize(synth, frame, wave[fi * synth.spkr.UI : (fi + 1) * synth.spkr.UI])

    # write at the synth's native 11025 Hz rate (matches DECtalk's WAV rate).
    write_wav(wave, out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 1000
