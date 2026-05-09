"""Synthesizer initialization.

Translated from `src/dapi/src/hlsyn/llinit.c`. Resets the synthesizer's
running state, clears every resonator, and copies the speaker's static
fields (number of cascade formants, parallel-only flag, frame size,
output tap) into the state struct so per-sample / per-frame functions
can read them without a second pointer indirection.

Notably the C source initialises the random-noise seed from
``spkr.RS`` here. Calling :func:`ll_init` therefore yields a
deterministic noise sequence regardless of any prior synthesis on
this :class:`LLSynth` instance.
"""

from __future__ import annotations

from dataclasses import fields

from dectalk.hlsyn.llsyn import LLSynth, Speaker
from dectalk.hlsyn.reson import Resonator
from dectalk.hlsyn.synth import OutputIdx


def ll_init(synth: LLSynth, spkr: Speaker | None = None) -> None:
    """Reset ``synth`` to a fresh post-construction state for the given speaker.

    Equivalent to the C `LLInit`. Mutates ``synth`` in place. Calling
    pattern mirrors the C: construct the instance, then call this once
    before the first frame.

    Args:
        synth: The :class:`LLSynth` instance to initialise.
        spkr: Optional speaker whose static fields seed ``synth.state``
            and whose ``RS`` field re-seeds the noise generator. When
            None, ``synth.spkr`` is used in place (matching the typical
            "set spkr first, then init" idiom).
    """
    if spkr is not None:
        synth.spkr = spkr

    state = synth.state
    s = synth.spkr

    # Static fields copied from speaker -> state.
    state.parallel_only_flag = s.CP
    state.num_casc_formants = s.NF
    state.num_samples = s.UI
    state.output_select = s.OS

    # Runtime state — reset to a fresh start.
    state.glottis_open = 0
    state.period_ctr = 0
    state.global_time = 0
    state.pulse = 0
    state.voicing_time = 0
    state.voicing_amp = 0.0
    state.voicing_state = 0
    state.glottal_state = 0.0
    state.asp_state = 0.0
    state.integrator = 0.0
    state.random = s.RS
    state.f0 = 0
    state.fl = 0
    state.oq = 0
    state.sq = 0
    state.di = 0
    state.av = 0
    state.tl = 0
    state.close_shortened = 0
    state.close_time = 0

    # Clear every resonator's filter memory and (for the InterPolePair'ed
    # ones) explicitly zero Coef.A so the smoothing path is bypassed on
    # the first transition.
    for f in fields(synth):
        attr = getattr(synth, f.name)
        if isinstance(attr, Resonator):
            attr.clear()
            attr.a = 0.0
            attr.b = 0.0
            attr.c = 0.0

    # Reset every output tap to zero.
    for i in range(len(synth.out)):
        synth.out[i] = 0.0
    # Touch OutputIdx so the import isn't dropped by static analysers
    # (the values appear elsewhere in the module via the synth.out access).
    _ = OutputIdx.NORMAL
