"""Tests for :func:`dectalk.hlsyn.init.ll_init` (LLInit translation)."""

from __future__ import annotations

from dataclasses import fields

import numpy as np

from dectalk.hlsyn.init import ll_init
from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.reson import Resonator
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.voice import SOURCE_NATURAL


def _make_speaker() -> Speaker:
    return Speaker(SR=11025, UI=110, SS=SOURCE_NATURAL, NF=5, RS=8191, GV=60, GH=50, GF=45)


def test_ll_init_seeds_random_from_speaker() -> None:
    synth = LLSynth(spkr=_make_speaker())
    synth.state.random = 42  # would be overwritten
    ll_init(synth)
    assert synth.state.random == synth.spkr.RS


def test_ll_init_clears_resonator_state() -> None:
    synth = LLSynth(spkr=_make_speaker())
    # Pre-load every resonator with non-zero state.
    for f in fields(synth):
        attr = getattr(synth, f.name)
        if isinstance(attr, Resonator):
            attr.z1 = 1.0
            attr.z2 = 1.0
            attr.a = 0.5

    ll_init(synth)

    for f in fields(synth):
        attr = getattr(synth, f.name)
        if isinstance(attr, Resonator):
            assert attr.z1 == 0.0
            assert attr.z2 == 0.0
            assert attr.a == 0.0


def test_ll_init_zeroes_runtime_state() -> None:
    synth = LLSynth(spkr=_make_speaker())
    synth.state.glottis_open = 1
    synth.state.period_ctr = 99
    synth.state.global_time = 1000
    synth.state.voicing_amp = 5.5
    synth.state.f0 = 1500
    ll_init(synth)
    assert synth.state.glottis_open == 0
    assert synth.state.period_ctr == 0
    assert synth.state.global_time == 0
    assert synth.state.voicing_amp == 0.0
    assert synth.state.f0 == 0


def test_ll_init_copies_static_speaker_fields() -> None:
    spkr = Speaker(SR=11025, UI=200, SS=SOURCE_NATURAL, NF=6, CP=1, OS=2, RS=8191)
    synth = LLSynth()
    ll_init(synth, spkr)
    assert synth.state.parallel_only_flag == 1
    assert synth.state.num_casc_formants == 6
    assert synth.state.num_samples == 200
    assert synth.state.output_select == 2


def test_ll_init_then_synthesize_is_deterministic() -> None:
    """Two synth instances initialised the same way should produce identical output."""
    spkr = _make_speaker()
    frame = LLFrame(F0=1220, AV=60, OQ=50, F1=730, B1=90, F2=1090, B2=110, F3=2440, B3=170)

    samples_a: list[np.ndarray] = []
    for _ in range(2):
        synth = LLSynth()
        ll_init(synth, spkr)
        out = np.zeros(spkr.UI * 5, dtype=np.int16)
        for fi in range(5):
            ll_synthesize(synth, frame, out[fi * spkr.UI : (fi + 1) * spkr.UI])
        samples_a.append(out)

    np.testing.assert_array_equal(samples_a[0], samples_a[1])
