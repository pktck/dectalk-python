"""Top-level Klatt frame synthesis (`LLSynthesize`).

Translated from `src/dapi/src/hlsyn/frame.c`. One call to
:func:`ll_synthesize` produces ``synth.spkr.UI`` samples by:

1. Computing every frame-dependent amplitude (Ah, Af, A2f..A6f, Ab, ANV,
   A1V..A4V, ATV) via :func:`db2amp`.
2. Updating every cascade, parallel, and special-branch resonator to the
   targets implied by the frame's formant/bandwidth fields.
3. Looping ``UI`` times calling :func:`next_sample`, clipping each sample to
   16-bit signed range, and writing it to the caller's int16 buffer.

Returns 1 if any sample was clipped, 0 otherwise — matches the C ``int``
return value.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from numpy.typing import NDArray

from dectalk.hlsyn.llsyn import LLFrame, LLSynth
from dectalk.hlsyn.sample import next_sample
from dectalk.hlsyn.synth import (
    A_A1,
    A_A1V,
    A_A2F,
    A_A2V,
    A_A3F,
    A_A3V,
    A_A4F,
    A_A4V,
    A_A5F,
    A_A6F,
    A_AB,
    A_AF,
    A_AH,
    A_ANV,
    A_ATV,
    db2amp,
)

# Klatt synth has fixed F7/F8 cascade poles to give a high-frequency tail.
_F7_CF_HZ: Final[int] = 6500
_F7_BW_HZ: Final[int] = 500
_F8_CF_HZ: Final[int] = 7500
_F8_BW_HZ: Final[int] = 600

_INT16_MIN: Final[int] = -32768
_INT16_MAX: Final[int] = 32767


def ll_synthesize(synth: LLSynth, frame: LLFrame, wave: NDArray[np.int16]) -> int:
    """Synthesize one frame's worth of samples into ``wave``.

    Equivalent to the C `LLSynthesize`. Updates all amplitude coefficients
    and resonator targets from ``frame``, then loops ``synth.spkr.UI`` times
    invoking :func:`next_sample` and writing the int16-clipped result.

    Args:
        synth: The Klatt synthesizer instance to drive.
        frame: Frame parameters (formants, bandwidths, amplitudes).
        wave: Output int16 buffer; must have at least ``synth.spkr.UI``
            elements. Filled from index 0.

    Returns:
        1 if any sample required clipping to fit int16, else 0.
    """
    _setup_amplitudes(synth, frame)
    _setup_resonators(synth, frame)
    _maybe_reseed_noise(synth, frame)

    return _run_frame(synth, frame, wave)


def _setup_amplitudes(synth: LLSynth, frame: LLFrame) -> None:
    """Compute per-frame amplitude scaling coefficients via :func:`db2amp`."""
    spkr = synth.spkr
    coefs = synth.coefs

    # Aspiration / frication: zero when their dB control is zero.
    coefs.asp_amp = db2amp(spkr.GH + frame.Ah + A_AH) if frame.Ah else 0.0
    coefs.fric_amp = db2amp(spkr.GF + frame.Af + A_AF) if frame.Af else 0.0

    coefs.f1p_amp = db2amp(A_A1)
    coefs.f2p_amp = db2amp(frame.A2f + A_A2F)
    coefs.f3p_amp = db2amp(frame.A3f + A_A3F)
    coefs.f4p_amp = db2amp(frame.A4f + A_A4F)
    coefs.f5p_amp = db2amp(frame.A5f + A_A5F)
    coefs.f6p_amp = db2amp(frame.A6f + A_A6F)
    coefs.bypass_amp = db2amp(frame.Ab + A_AB)

    coefs.npv_amp = db2amp(frame.ANV + A_ANV)
    coefs.f1v_amp = db2amp(frame.A1V + A_A1V)
    coefs.f2v_amp = db2amp(frame.A2V + A_A2V)
    coefs.f3v_amp = db2amp(frame.A3V + A_A3V)
    coefs.f4v_amp = db2amp(frame.A4V + A_A4V)
    coefs.tpv_amp = db2amp(frame.ATV + A_ATV)


def _setup_resonators(synth: LLSynth, frame: LLFrame) -> None:
    """Update all resonator coefficients to the targets implied by ``frame``."""
    sr = synth.spkr.SR
    open_phase = bool(synth.state.glottis_open)
    df1 = frame.DF1 if open_phase else 0
    db1 = frame.DB1 if open_phase else 0

    # Cascade branch
    synth.formant_1_cascade.inter_pole_pair(frame.F1 + df1, frame.B1 + db1, sr)
    synth.formant_2_cascade.inter_pole_pair(frame.F2, frame.B2, sr)
    synth.formant_3_cascade.inter_pole_pair(frame.F3, frame.B3, sr)
    synth.formant_4_cascade.set_pole_pair(frame.F4, frame.B4, sr)
    synth.formant_5_cascade.set_pole_pair(frame.F5, frame.B5, sr)
    synth.formant_6_cascade.set_pole_pair(frame.F6, frame.B6, sr)
    synth.formant_7_cascade.set_pole_pair(_F7_CF_HZ, _F7_BW_HZ, sr)
    synth.formant_8_cascade.set_pole_pair(_F8_CF_HZ, _F8_BW_HZ, sr)
    synth.nasal_pole_cascade.inter_pole_pair(frame.FNP, frame.BNP, sr)
    synth.nasal_zero_cascade.set_zero_pair(frame.FNZ, frame.BNZ, sr)
    synth.trach_pole_cascade.set_pole_pair(frame.FTP, frame.BTP, sr)
    synth.trach_zero_cascade.set_zero_pair(frame.FTZ, frame.BTZ, sr)

    # Parallel branch
    synth.formant_2_parallel.inter_pole_pair(frame.F2, frame.B2F, sr)
    synth.formant_3_parallel.inter_pole_pair(frame.F3, frame.B3F, sr)
    synth.formant_4_parallel.set_pole_pair(frame.F4, frame.B4F, sr)
    synth.formant_5_parallel.set_pole_pair(frame.F5, frame.B5F, sr)
    synth.formant_6_parallel.set_pole_pair(frame.F6, frame.B6F, sr)

    # Special parallel branch (alternative voicing path)
    synth.nasal_pole_special.inter_pole_pair(frame.FNP, frame.BNP, sr)
    synth.formant_1_special.inter_pole_pair(frame.F1 + df1, frame.B1 + db1, sr)
    synth.formant_2_special.inter_pole_pair(frame.F2, frame.B2, sr)
    synth.formant_3_special.inter_pole_pair(frame.F3, frame.B3, sr)
    synth.formant_4_special.set_pole_pair(frame.F4, frame.B4, sr)
    synth.trach_pole_special.set_pole_pair(frame.FTP, frame.BTP, sr)


def _maybe_reseed_noise(synth: LLSynth, frame: LLFrame) -> None:
    """Reset the LCG noise generator at the start of silent intervals.

    The C source reseeds when the speaker has ``SB`` set and both noise
    sources (Af, Ah) are silent — so consecutive silent frames produce
    deterministic output rather than a random walk through the LCG state.
    """
    if synth.spkr.SB and not frame.Af and not frame.Ah:
        synth.state.random = synth.spkr.RS


def _run_frame(synth: LLSynth, frame: LLFrame, wave: NDArray[np.int16]) -> int:
    """Loop ``UI`` samples, clip to int16, and write into ``wave``."""
    clip = 0
    for index in range(synth.spkr.UI):
        sample = next_sample(synth, frame)
        if sample > _INT16_MAX:
            wave[index] = _INT16_MAX
            clip = 1
        elif sample < _INT16_MIN:
            wave[index] = _INT16_MIN
            clip = 1
        else:
            wave[index] = int(sample)  # truncates toward zero, matching C cast
    return clip
