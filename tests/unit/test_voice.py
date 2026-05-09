"""Unit tests for the voicing-source generator (`dectalk.hlsyn.voice`).

These tests exercise the public :func:`next_voice_sample` entry point with
hand-built :class:`LLSynth` and :class:`LLFrame` instances, verifying:

- F0 = 0 produces silence and resets pulse-period state.
- A non-zero F0 produces a periodic source whose period matches the
  configured fundamental.
- Frame parameters are latched on glottal-open transitions.
- Each of the three source-shape variants (impulsive, natural, LF) runs
  without raising.
"""

from __future__ import annotations

import numpy as np

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.voice import (
    SOURCE_IMPULSIVE,
    SOURCE_LF,
    SOURCE_NATURAL,
    next_voice_sample,
)

# A reasonable speaker for exercise: 11025 Hz sample rate, modest gains.
DEFAULT_SR_HZ = 11025


def _build_synth(source_shape: int, sr_hz: int = DEFAULT_SR_HZ) -> LLSynth:
    synth = LLSynth()
    synth.spkr = Speaker(SR=sr_hz, SS=source_shape, GV=60)
    return synth


def _build_frame_at_f0(f0_x10: int, av_db: int = 60) -> LLFrame:
    """Build a frame at the given F0 (Hz x 10) with sane defaults for voicing."""
    return LLFrame(
        F0=f0_x10,
        AV=av_db,
        OQ=50,  # 50% open quotient
        SQ=200,  # speed quotient (only relevant for LF source)
        TL=0,  # no spectral tilt
        F1=500,
        B1=60,
    )


def test_zero_f0_returns_silence() -> None:
    synth = _build_synth(SOURCE_IMPULSIVE)
    frame = _build_frame_at_f0(f0_x10=0)
    samples = [next_voice_sample(synth, frame) for _ in range(200)]
    # spectral_tilt has zero coefficients initially -> output is identically zero.
    assert all(s == 0.0 for s in samples)


def test_zero_f0_resets_glottal_state() -> None:
    synth = _build_synth(SOURCE_IMPULSIVE)
    synth.state.glottis_open = 1
    synth.state.period_ctr = 50
    synth.state.voicing_state = 1
    frame = _build_frame_at_f0(f0_x10=0)
    next_voice_sample(synth, frame)
    assert synth.state.glottis_open == 0
    assert synth.state.period_ctr == 0
    assert synth.state.voicing_state == 0


def test_global_time_advances_every_call() -> None:
    synth = _build_synth(SOURCE_IMPULSIVE)
    frame = _build_frame_at_f0(f0_x10=0)
    for i in range(1, 11):
        next_voice_sample(synth, frame)
        assert synth.state.global_time == i


def test_open_glottis_latches_frame_params() -> None:
    """First call with non-zero F0 should latch AV/OQ/SQ/DI/TL into state."""
    synth = _build_synth(SOURCE_IMPULSIVE)
    frame = _build_frame_at_f0(f0_x10=1100, av_db=72)
    frame.OQ = 60
    frame.SQ = 250
    frame.DI = 0
    frame.TL = 4
    next_voice_sample(synth, frame)
    state = synth.state
    assert state.f0 == 1100
    assert state.av == 72
    assert state.oq == 60
    assert state.sq == 250
    assert state.tl == 4
    assert state.glottis_open == 1


def test_impulsive_source_period_matches_f0() -> None:
    """The number of pulse onsets in a buffer should match the expected F0."""
    f0_hz = 100.0
    duration_s = 0.5
    synth = _build_synth(SOURCE_IMPULSIVE)
    frame = _build_frame_at_f0(f0_x10=round(f0_hz * 10))

    n = round(duration_s * DEFAULT_SR_HZ)
    samples = np.asarray([next_voice_sample(synth, frame) for _ in range(n)], dtype=np.float64)
    # The impulsive source emits a (filtered) pulse at every glottal opening.
    # A simple proxy for "number of pulses" is the count of local maxima above
    # 1% of the peak. Tolerate ±2 cycles slop from flutter and edge effects.
    peak = float(np.max(np.abs(samples)))
    assert peak > 0.0, "expected non-zero source output"

    threshold = 0.5 * peak
    # Count rising-edge crossings of the threshold (each pulse exceeds it once).
    crossings = np.sum((samples[:-1] < threshold) & (samples[1:] >= threshold))
    expected = round(f0_hz * duration_s)
    assert abs(int(crossings) - expected) <= 2


def test_natural_source_runs_without_error() -> None:
    synth = _build_synth(SOURCE_NATURAL)
    frame = _build_frame_at_f0(f0_x10=1200)
    for _ in range(500):
        next_voice_sample(synth, frame)


def test_lf_source_runs_without_error() -> None:
    synth = _build_synth(SOURCE_LF)
    frame = _build_frame_at_f0(f0_x10=1200)
    # LF source needs SQ in [100, 500] (so SQ // 10 - 10 ∈ [0, 40]).
    frame.SQ = 200
    for _ in range(500):
        next_voice_sample(synth, frame)


def test_zero_av_yields_zero_voicing_amp() -> None:
    """AV = 0 should set voicing_amp to 0.0 (avoiding the dB2amp branch)."""
    synth = _build_synth(SOURCE_IMPULSIVE)
    frame = _build_frame_at_f0(f0_x10=1000, av_db=0)
    next_voice_sample(synth, frame)
    assert synth.state.voicing_amp == 0.0
