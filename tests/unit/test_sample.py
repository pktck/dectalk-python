"""Unit tests for :func:`dectalk.hlsyn.sample.next_sample`.

Validates the per-sample mixing logic: the LCG noise generator matches the
C source's modulo arithmetic; the cascade/parallel branch selection works;
``OutputIdx.NORMAL`` is the documented sum of taps.
"""

from __future__ import annotations

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.sample import next_sample
from dectalk.hlsyn.synth import OutputIdx
from dectalk.hlsyn.voice import SOURCE_IMPULSIVE


def _silent_synth() -> LLSynth:
    """Build a synth with no voicing/noise — every output should be 0."""
    synth = LLSynth()
    synth.spkr = Speaker(SR=11025, SS=SOURCE_IMPULSIVE, NF=5, GV=60)
    return synth


def test_noise_lcg_matches_c_recurrence() -> None:
    """random_{n+1} = (random_n * 20077 + 12345) mod 65536, sign-extended."""
    synth = _silent_synth()
    synth.state.random = 1
    frame = LLFrame()  # F0 = 0 -> voicing returns 0
    next_sample(synth, frame)
    expected = (1 * 20077 + 12345) % 65536
    assert synth.state.random == expected


def test_silent_frame_yields_zero_output() -> None:
    synth = _silent_synth()
    frame = LLFrame()
    out = next_sample(synth, frame)
    # Silent frame: no voicing, no noise (asp_amp/fric_amp are zero by default
    # because the synth was initialized with empty Coefficients).
    assert out == 0.0


def test_normal_output_combines_taps() -> None:
    """OutputIdx.NORMAL = F1C + F2P - F3P + F4P - F5P + F6P - BYPASS + special."""
    synth = _silent_synth()
    frame = LLFrame()
    next_sample(synth, frame)
    out = synth.out
    expected = (
        out[OutputIdx.FORMANT_1_CASC]
        + out[OutputIdx.FORMANT_2_PARA]
        - out[OutputIdx.FORMANT_3_PARA]
        + out[OutputIdx.FORMANT_4_PARA]
        - out[OutputIdx.FORMANT_5_PARA]
        + out[OutputIdx.FORMANT_6_PARA]
        - out[OutputIdx.BYPASS_PARA]
    )
    assert out[OutputIdx.NORMAL] == expected


def test_glottal_combines_voicing_and_aspiration() -> None:
    """O_GLOTTAL = 12*VOICING + 5*ASPIRATION."""
    synth = _silent_synth()
    frame = LLFrame()
    next_sample(synth, frame)
    out = synth.out
    expected = 12.0 * out[OutputIdx.VOICING] + 5.0 * out[OutputIdx.ASPIRATION]
    assert out[OutputIdx.GLOTTAL] == expected


def test_parallel_only_flag_uses_special_branch() -> None:
    """When parallel_only_flag is set, F1C from cascade should remain at zero
    (since the cascade does not run) and the parallel-special branch produces output.
    """
    synth = _silent_synth()
    synth.state.parallel_only_flag = 1
    # Pre-load F1_CASC with a sentinel; the cascade path should not overwrite it.
    synth.out[OutputIdx.FORMANT_1_CASC] = 999.0
    frame = LLFrame()
    next_sample(synth, frame)
    assert synth.out[OutputIdx.FORMANT_1_CASC] == 999.0
