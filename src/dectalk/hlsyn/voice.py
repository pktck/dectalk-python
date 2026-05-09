"""Glottal-pulse / voicing-source generator.

Translated from `src/dapi/src/hlsyn/voice.c`. Produces one voice sample at a
time, driving the spectral-tilt and glottal-pulse resonators based on the
current frame's voicing parameters and the speaker's source-shape selection.

The synthesizer supports three source shapes via ``Speaker.SS``:

1. **Impulsive** — a unit impulse at glottal-opening, shaped by the glottal
   resonator (a low-Q lowpass).
2. **Natural KLGLOT88** — Klatt's polynomial source: ``2t - 3t²/T`` over the
   open phase, where ``T`` is the open-phase length.
3. **LF model** — Liljencrants-Fant glottal flow model parameterised by
   speed quotient ``SQ``; uses bandwidth and amplitude tables ``bw_lf`` /
   ``e0_lf`` indexed by ``SQ // 10 - 10``.
"""

from __future__ import annotations

import math
from typing import Final

from dectalk.hlsyn.llsyn import LLFrame, LLSynth
from dectalk.hlsyn.synth import A_AV, TWO_PI, db2amp

# Source-shape selector values for ``Speaker.SS``.
SOURCE_IMPULSIVE: Final[int] = 1
SOURCE_NATURAL: Final[int] = 2
SOURCE_LF: Final[int] = 3

# Tilt index above which the spectral-tilt resonator's gain is boosted.
_TILT_BOOST_THRESHOLD: Final[int] = 10


def _round_half_up(x: float) -> int:
    """Round half-up to the nearest int (matches C ``(int)(x + 0.5f)``).

    Python's built-in :func:`round` uses banker's rounding which differs
    from the C macro for ``.5`` ties; we replicate the C behaviour for
    bit-for-bit parity with the reference implementation.

    Args:
        x: Value to round.

    Returns:
        ``floor(x + 0.5)`` for positive ``x``; symmetric for negative.
    """
    if x >= 0:
        return math.floor(x + 0.5)
    return math.ceil(x - 0.5)


# Spectral-tilt bandwidth lookup, indexed by `state.tl` ∈ [0, 41].
_TILT_BW: Final[tuple[int, ...]] = (
    5000, 4350, 3790, 3330, 2930, 2700, 2580, 2468, 2364, 2260,
    2157, 2045, 1925, 1806, 1687, 1568, 1449, 1350, 1272, 1199,
    1133, 1071, 1009, 947, 885, 833, 781, 729, 677, 625,
    599, 573, 547, 521, 495, 469, 442, 416, 390, 364,
    338, 312,
)  # fmt: skip

# LF model bandwidth table, indexed by ``SQ // 10 - 10`` ∈ [0, 40].
_BW_LF: Final[tuple[float, ...]] = (
    0.0, -0.6, -2.0, -4.0, -6.0, -8.0, -10.4, -12.7, -15.3, -17.8,
    -20.1, -22.4, -24.7, -27.0, -29.2, -31.4, -33.6, -35.8, -37.9, -40.0,
    -42.1, -44.1, -46.2, -48.3, -50.4, -52.4, -54.5, -56.6, -57.8, -60.8,
    -62.7, -64.5, -66.3, -68.1, -69.9, -71.6, -73.3, -75.0, -76.6, -78.2,
    -79.6,
)  # fmt: skip

# LF model amplitude table, indexed identically to ``_BW_LF``.
_E0_LF: Final[tuple[float, ...]] = (
    27.4, 26.3, 25.3, 24.3, 23.2, 22.1, 21.0, 20.0, 18.8, 17.6,
    16.1, 14.9, 13.8, 12.8, 11.7, 10.6, 9.81, 9.00, 8.12, 7.36,
    6.60, 6.05, 5.46, 4.92, 4.41, 3.94, 3.58, 3.14, 2.83, 2.49,
    2.24, 2.03, 1.83, 1.63, 1.48, 1.32, 1.19, 1.08, 0.982, 0.902,
    0.832,
)  # fmt: skip


def next_voice_sample(synth: LLSynth, frame: LLFrame) -> float:
    """Synthesize one voicing-source sample.

    Equivalent to the C `next_voice_sample`. Mutates ``synth.state``,
    ``synth.spectral_tilt``, ``synth.glottal_pulse``,
    ``synth.formant_1_cascade``, and ``synth.formant_1_special`` as a
    side effect.

    Args:
        synth: The active synthesizer instance (state, resonators, speaker).
        frame: Current frame's parameters (F0, FL, OQ, SQ, DI, AV, TL,
            F1, B1, DF1, DB1, …).

    Returns:
        The next voicing-source sample (float).
    """
    state = synth.state

    # Flutter time runs continuously regardless of voicing.
    state.global_time += 1

    # F0 = 0 → silent; flush state, return spectral-tilt(0).
    if not frame.F0:
        state.period_ctr = 0
        state.glottis_open = 0
        state.voicing_state = 0
        return synth.spectral_tilt.advance(0.0)

    # Decrement the period counter; <= 0 marks a glottal transition.
    state.period_ctr -= 1
    if state.period_ctr <= 0:
        if not state.glottis_open:
            _open_glottis(synth, frame)
        else:
            _close_glottis(synth, frame)
    else:
        state.voicing_time += 1
        state.pulse = 0

    # Generate the source sample for this clock tick based on source shape.
    return _voicing_source_sample(synth, frame)


def _open_glottis(synth: LLSynth, frame: LLFrame) -> None:
    """Handle glottal-opening transition: latch frame params and prep filters."""
    _latch_frame_params(synth, frame)
    _compute_period(synth)
    _apply_diplophonia(synth)
    _setup_spectral_tilt(synth)
    _setup_open_phase_f1(synth, frame)
    _setup_glottal_pulse(synth)


def _latch_frame_params(synth: LLSynth, frame: LLFrame) -> None:
    """Copy F0/voicing/glottal-source params from the frame into running state."""
    state = synth.state
    spkr = synth.spkr

    state.glottis_open = 1
    state.pulse = 1
    state.voicing_time = 0
    state.f0 = frame.F0
    state.fl = frame.FL
    state.oq = frame.OQ
    state.sq = frame.SQ
    state.di = frame.DI
    state.av = frame.AV
    state.tl = frame.TL
    state.voicing_amp = db2amp(spkr.GV + state.av + A_AV) if state.av else 0.0


def _compute_period(synth: LLSynth) -> None:
    """Compute pulse period and open/closed-phase split (with flutter)."""
    state = synth.state
    spkr = synth.spkr

    if state.fl:
        seconds = state.global_time / spkr.SR
        freq = state.f0 / 10.0 + (
            state.fl
            / 50.0
            * state.f0
            / 600.0
            * (
                math.cos(TWO_PI * 12.7 * seconds)
                + math.cos(TWO_PI * 7.1 * seconds)
                + math.cos(TWO_PI * 4.7 * seconds)
            )
        )
    else:
        freq = state.f0 / 10.0

    state.pulse_freq = _round_half_up(spkr.SR / freq)
    state.period_ctr = _round_half_up(state.pulse_freq * state.oq / 100.0)
    state.close_time = state.pulse_freq - state.period_ctr


def _apply_diplophonia(synth: LLSynth) -> None:
    """Alternate-cycle shortening/lengthening per the diplophonia parameter."""
    state = synth.state
    if not state.di:
        state.close_shortened = 0
        return

    if not state.close_shortened:
        state.close_shortened = 1
        state.close_time -= _round_half_up(state.close_time * state.di / 100.0)
        state.voicing_amp *= 1.0 - state.di / 100.0
        # The C source comment notes "the following is not quite right".
        state.tl += _round_half_up(state.di / 4.25)
    else:
        state.close_shortened = 0
        state.close_time += _round_half_up(state.close_time * state.di / 100.0)


def _setup_spectral_tilt(synth: LLSynth) -> None:
    """Configure the spectral-tilt resonator from the current TL index."""
    state = synth.state
    spkr = synth.spkr

    if spkr.SS == SOURCE_LF:  # LF source needs corner rounding
        state.tl += 2

    tilt_bw = _TILT_BW[state.tl]
    synth.spectral_tilt.set_pole_pair(
        cf_hz=_round_half_up(0.375 * tilt_bw),
        bw_hz=tilt_bw,
        sf_hz=spkr.SR,
    )
    if state.tl > _TILT_BOOST_THRESHOLD:
        delta = state.tl - _TILT_BOOST_THRESHOLD
        synth.spectral_tilt.a *= 1.0 + delta * delta / 1000.0


def _setup_open_phase_f1(synth: LLSynth, frame: LLFrame) -> None:
    """Re-tune cascade and special F1 resonators with the open-phase deltas."""
    spkr = synth.spkr
    cf = frame.F1 + frame.DF1
    bw = frame.B1 + frame.DB1
    synth.formant_1_cascade.inter_pole_pair(cf_hz=cf, bw_hz=bw, sf_hz=spkr.SR)
    synth.formant_1_special.inter_pole_pair(cf_hz=cf, bw_hz=bw, sf_hz=spkr.SR)


def _setup_glottal_pulse(synth: LLSynth) -> None:
    """Configure the glottal-pulse resonator based on speaker source shape."""
    state = synth.state
    spkr = synth.spkr

    if spkr.SS == SOURCE_IMPULSIVE:
        state.voicing_state = 0
        temp = state.pulse_freq * state.oq / 100.0
        synth.glottal_pulse.set_pole_pair(
            cf_hz=0,
            bw_hz=_round_half_up(10000.0 / temp),
            sf_hz=spkr.SR,
        )
        synth.glottal_pulse.a *= 0.002675 * temp * temp  # -51.3 dB
    elif spkr.SS == SOURCE_LF:
        freq_lf = state.f0 / (22.0 * state.oq / 100.0) * (state.sq + 100.0) / state.sq
        idx_a = state.sq // 10 - 9
        idx_b = state.sq // 10 - 10
        temp = (_BW_LF[idx_a] - _BW_LF[idx_b]) / 10.0
        bw_lf_val = (
            (_BW_LF[idx_b] + (state.sq % 10) * temp) * 200.0 / (state.pulse_freq * state.oq / 100.0)
        )
        synth.glottal_pulse.set_pole_pair(
            cf_hz=_round_half_up(freq_lf),
            bw_hz=_round_half_up(bw_lf_val),
            sf_hz=spkr.SR,
        )
        temp = (_E0_LF[idx_a] - _E0_LF[idx_b]) / 10.0
        synth.glottal_pulse.a *= (
            (_E0_LF[idx_b] + (state.sq % 10) * temp) * (state.pulse_freq * state.oq / 100.0) / 200.0
        )
    # SOURCE_NATURAL needs no setup; the polynomial is computed each sample.


def _close_glottis(synth: LLSynth, frame: LLFrame) -> None:
    """Handle glottal-closing transition: switch F1 back to closed-phase target."""
    state = synth.state
    spkr = synth.spkr

    state.glottis_open = 0
    state.voicing_time += 1
    state.pulse = 0
    state.period_ctr = state.close_time
    synth.formant_1_cascade.inter_pole_pair(cf_hz=frame.F1, bw_hz=frame.B1, sf_hz=spkr.SR)
    synth.formant_1_special.inter_pole_pair(cf_hz=frame.F1, bw_hz=frame.B1, sf_hz=spkr.SR)


def _voicing_source_sample(synth: LLSynth, frame: LLFrame) -> float:
    """Compute the source sample for the current clock tick.

    Args:
        synth: The synthesizer state and resonators.
        frame: Current frame's parameters (currently unused beyond what
            :func:`_open_glottis` already latched into state, but accepted
            for API symmetry with :func:`next_voice_sample`).

    Returns:
        Source sample after spectral-tilt shaping.
    """
    del frame  # parameters are already latched in state at glottal opening
    state = synth.state
    spkr = synth.spkr

    if spkr.SS == SOURCE_IMPULSIVE:
        pulse = state.pulse - state.voicing_state
        state.voicing_state = state.pulse
        return synth.spectral_tilt.advance(synth.glottal_pulse.advance(pulse * state.voicing_amp))

    if spkr.SS == SOURCE_NATURAL:
        if state.glottis_open:
            time_s = float(state.voicing_time)
            open_s = state.pulse_freq * state.oq / 100.0
            inv_pulse_freq = 100.0 / state.pulse_freq if state.pulse_freq else 0.0
            temp = (
                state.voicing_amp
                * 0.00055
                * inv_pulse_freq
                * (50.0 / state.oq)
                * (2.0 * time_s - 3.0 * time_s * time_s / open_s)
            )
            return synth.spectral_tilt.advance(temp)
        return synth.spectral_tilt.advance(0.0)

    if spkr.SS == SOURCE_LF:
        # The original C source has a missing-braces bug: the
        # `output = AdvanceResonator(&spectral_tilt, 0.f)` line at the
        # end of the case is at the same indentation as the if but,
        # without braces on the else, falls through unconditionally.
        # That means tilt.advance() is called twice during the open
        # phase: once with the (pulse-shaped) voicing source as input,
        # then once with 0. The second call is what's returned, but it
        # carries the state set up by the first call (tilt is an IIR
        # filter; its output decays from the previous input). We
        # replicate that behaviour to match the reference bit-for-bit.
        if state.glottis_open:
            voiced = synth.glottal_pulse.advance(state.voicing_amp * 0.0795 if state.pulse else 0.0)
            synth.spectral_tilt.advance(voiced)
        else:
            synth.glottal_pulse.clear()
        return synth.spectral_tilt.advance(0.0)

    return 0.0
