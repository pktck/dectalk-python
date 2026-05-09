r"""Per-sample Klatt cascade-parallel synthesis.

Translated from `src/dapi/src/hlsyn/sample.c`. Combines the voicing source
(:func:`dectalk.hlsyn.voice.next_voice_sample`) with aspiration noise and
runs the result through the cascade and parallel formant filter banks to
produce one audio sample.

Pipeline summary::

    voicing      noise (LCG)            frication
       |          |                        |
       v          v                        v
    [voicing] -> aspiration -> glottal -> cascade --> [F1_CASC]
                                           (F1..F8,
                                            nasal,
                                            tracheal)
                                                 \
    parallel branches: F2P-F6P from frication --> [combine]
                                                 /
    bypass branch from frication ---------------+
                                                 |
                                                 v
                                            output sample

The "special" parallel branch is an alternative voicing path used when
``parallel_only_flag`` is set; cascade and special-parallel are mutually
exclusive.
"""

from __future__ import annotations

from typing import Final

from dectalk.hlsyn.llsyn import LLFrame, LLSynth
from dectalk.hlsyn.synth import OutputIdx
from dectalk.hlsyn.voice import next_voice_sample

# Linear-congruential noise generator parameters from the C source.
_LCG_MULT: Final[int] = 20077
_LCG_ADD: Final[int] = 12345
_LCG_MOD: Final[int] = 65536
_LCG_HALF: Final[int] = 32768  # for sign-extending 16-bit values
_LCG_NORM: Final[float] = 1.0 / _LCG_MOD

# Mixer coefficients combining voicing and aspiration into the glottal signal.
_VOICING_GAIN: Final[float] = 12.0
_ASPIRATION_GAIN: Final[float] = 5.0
_CASCADE_INPUT_DIVISOR: Final[float] = 4.0  # glottal feed into trach/nasal chain

# Output integrator coefficient (when spkr.OS in {1, 2, 3}).
_INTEGRATOR_LEAK: Final[float] = 0.99


def next_sample(synth: LLSynth, frame: LLFrame) -> float:
    """Synthesize one combined output sample.

    Equivalent to the C `next_sample`. Mutates ``synth.state.random``,
    ``synth.state.asp_state``, ``synth.state.glottal_state``,
    ``synth.state.integrator``, all resonator states, and the
    ``synth.out`` per-sample tap array as a side effect.

    Args:
        synth: The active synthesizer instance.
        frame: Current frame parameters (used here for ``F0`` and to
            forward to :func:`next_voice_sample`).

    Returns:
        The output sample (typically scaled to fit a 16-bit range).
    """
    out = synth.out

    # Voicing source.
    out[OutputIdx.VOICING] = next_voice_sample(synth, frame)

    # Aspiration / frication noise via the 16-bit LCG, sign-extended.
    synth.state.random = (synth.state.random * _LCG_MULT + _LCG_ADD) % _LCG_MOD
    raw = synth.state.random
    if raw >= _LCG_HALF:
        raw -= _LCG_MOD  # sign-extend to a signed 16-bit value
    noise = raw * _LCG_NORM
    if frame.F0 and not synth.state.glottis_open and synth.state.av:
        # The C halves the noise during the closed phase of voiced speech to
        # avoid an audible "buzz". Voiceless segments keep the full noise.
        noise *= 0.5

    # Aspiration: first-difference of the gain-scaled noise.
    asp_in = synth.coefs.asp_amp * noise
    out[OutputIdx.ASPIRATION] = asp_in - synth.state.asp_state
    synth.state.asp_state = asp_in

    # Combined glottal source feeds both the cascade chain and the parallel
    # "special" branch. Frication is the negated, gain-scaled noise.
    out[OutputIdx.GLOTTAL] = (
        _VOICING_GAIN * out[OutputIdx.VOICING] + _ASPIRATION_GAIN * out[OutputIdx.ASPIRATION]
    )
    out[OutputIdx.FRICATION] = -synth.coefs.fric_amp * noise

    # Cascade vs. parallel-only mutually exclusive: only one runs per sample.
    if not synth.state.parallel_only_flag:
        _run_cascade(synth)
        synth.state.glottal_state = 0.0
        special = 0.0
    else:
        special = _run_parallel_special(synth)

    # Parallel formant branches driven by frication.
    _run_parallel_frication(synth)

    # Combined output: F1 from cascade + alternating-sign parallel formants
    # + bypass + the special-parallel-branch sum (zero when cascade is on).
    out[OutputIdx.NORMAL] = (
        out[OutputIdx.FORMANT_1_CASC]
        + out[OutputIdx.FORMANT_2_PARA]
        - out[OutputIdx.FORMANT_3_PARA]
        + out[OutputIdx.FORMANT_4_PARA]
        - out[OutputIdx.FORMANT_5_PARA]
        + out[OutputIdx.FORMANT_6_PARA]
        - out[OutputIdx.BYPASS_PARA]
        + special
    )

    # Optional 6-dB/oct integrator on the selected output tap.
    selected = synth.spkr.OS
    if selected in (1, 2, 3):
        output = out[selected] + _INTEGRATOR_LEAK * synth.state.integrator
        synth.state.integrator = output
        return output
    return out[selected]


def _run_cascade(synth: LLSynth) -> None:
    """Run the cascade branch: trach -> nasal -> formants in series."""
    out = synth.out
    casc = synth.trach_zero_cascade.advance_anti(out[OutputIdx.GLOTTAL] / _CASCADE_INPUT_DIVISOR)
    casc = synth.trach_pole_cascade.advance(casc)
    out[OutputIdx.TRACHEAL_CASC] = casc

    casc = synth.nasal_zero_cascade.advance_anti(casc)
    out[OutputIdx.NASAL_ZERO_CASC] = casc
    casc = synth.nasal_pole_cascade.advance(casc)
    out[OutputIdx.NASAL_POLE_CASC] = casc

    # Run from the highest formant down, mirroring the C switch fall-through.
    nf = synth.spkr.NF
    if nf >= 8:  # noqa: PLR2004 - DECtalk supports 4 to 8 cascade formants
        casc = synth.formant_8_cascade.advance(casc)
    if nf >= 7:  # noqa: PLR2004
        casc = synth.formant_7_cascade.advance(casc)
    if nf >= 6:  # noqa: PLR2004
        casc = synth.formant_6_cascade.advance(casc)
    if nf >= 5:  # noqa: PLR2004
        casc = synth.formant_5_cascade.advance(casc)
        out[OutputIdx.FORMANT_5_CASC] = casc
    if nf >= 4:  # noqa: PLR2004
        casc = synth.formant_4_cascade.advance(casc)
        out[OutputIdx.FORMANT_4_CASC] = casc
    if nf >= 3:  # noqa: PLR2004
        casc = synth.formant_3_cascade.advance(casc)
        out[OutputIdx.FORMANT_3_CASC] = casc
    if nf >= 2:  # noqa: PLR2004
        casc = synth.formant_2_cascade.advance(casc)
        out[OutputIdx.FORMANT_2_CASC] = casc
    out[OutputIdx.FORMANT_1_CASC] = synth.formant_1_cascade.advance(casc)


def _run_parallel_special(synth: LLSynth) -> float:
    """Run the parallel "special" branch (cascade alternative).

    Returns:
        The summed output of the special branch, ready to mix into the
        normal output.
    """
    out = synth.out
    coefs = synth.coefs
    glottal = out[OutputIdx.GLOTTAL]

    first_diff = glottal - synth.state.glottal_state
    synth.state.glottal_state = glottal

    out[OutputIdx.NASAL_PARA] = synth.nasal_pole_special.advance(glottal * coefs.npv_amp)
    out[OutputIdx.FORMANT_1_PARA] = synth.formant_1_special.advance(glottal * coefs.f1v_amp)

    return (
        out[OutputIdx.NASAL_PARA]
        + out[OutputIdx.FORMANT_1_PARA]
        - synth.formant_2_special.advance(first_diff * coefs.f2v_amp)
        + synth.formant_3_special.advance(first_diff * coefs.f3v_amp)
        - synth.formant_4_special.advance(first_diff * coefs.f4v_amp)
        + synth.trach_pole_special.advance(first_diff * coefs.tpv_amp)
    )


def _run_parallel_frication(synth: LLSynth) -> None:
    """Run the parallel formants F2-F6 driven by the frication noise."""
    out = synth.out
    coefs = synth.coefs
    fric = out[OutputIdx.FRICATION]

    out[OutputIdx.FORMANT_2_PARA] = synth.formant_2_parallel.advance(fric * coefs.f2p_amp)
    out[OutputIdx.FORMANT_3_PARA] = synth.formant_3_parallel.advance(fric * coefs.f3p_amp)
    out[OutputIdx.FORMANT_4_PARA] = synth.formant_4_parallel.advance(fric * coefs.f4p_amp)
    out[OutputIdx.FORMANT_5_PARA] = synth.formant_5_parallel.advance(fric * coefs.f5p_amp)
    out[OutputIdx.FORMANT_6_PARA] = synth.formant_6_parallel.advance(fric * coefs.f6p_amp)
    out[OutputIdx.BYPASS_PARA] = fric * coefs.bypass_amp
