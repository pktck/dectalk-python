"""SenSyn / Klatt synthesizer top-level data types.

Translated from `src/dapi/src/hlsyn/llsyn.h`. Defines:

- :class:`Speaker`: voice/speaker definition (12 short ints — sample rate,
  number of formants, source type, glottal-spectrum tilt parameters, …).
- :class:`LLFrame`: per-frame Klatt synthesis parameters (~50 numeric
  values — F0, formant frequencies & bandwidths, voicing/aspiration/frication
  amplitudes, parallel-formant amps).
- :class:`LLSynth`: the running synthesizer instance — holds the
  :class:`Synthesizer` state, :class:`Coefficients`, :class:`Speaker`, all
  resonators (cascade + parallel + special), and the per-sample output taps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dectalk.hlsyn.reson import Resonator
from dectalk.hlsyn.synth import NUM_OUTPUTS, Coefficients, Synthesizer


@dataclass(slots=True)
class Speaker:
    """Speaker / voice definition (12 short ints).

    Mirrors the C `Speaker` struct.

    Attributes:
        DU: Duration unit / utterance-level scaling.
        UI: Update interval in samples per frame.
        SR: Sample rate in Hz.
        NF: Number of cascade formants (typically 4-8).
        SS: Source-shape selector — 1 impulsive, 2 natural KLGLOT88, 3 LF model.
        RS: Random seed for the noise generator.
        SB: Smoothing of bandwidths, in Hz.
        CP: Cascade/parallel switch.
        OS: Output sampling.
        GV: Voicing gain in dB.
        GH: Aspiration gain in dB.
        GF: Frication gain in dB.
    """

    DU: int = 0
    UI: int = 0
    SR: int = 0
    NF: int = 0
    SS: int = 0
    RS: int = 0
    SB: int = 0
    CP: int = 0
    OS: int = 0
    GV: int = 0
    GH: int = 0
    GF: int = 0


@dataclass(slots=True)
class LLFrame:
    """Per-frame Klatt synthesis parameters.

    Mirrors the C `LLFrame` struct. The original used ``short`` for every
    field; we keep `int` here since Python ints are unbounded and we only
    care about value equivalence.

    Attributes:
        F0: Fundamental frequency x 10 (Hz).
        AV: Voicing amplitude in dB.
        OQ: Open quotient as a percent of the period.
        SQ: Speed quotient (LF source shape control).
        TL: Spectral tilt index.
        FL: Flutter (pitch jitter) parameter.
        DI: Diplophonia parameter.
        Ah: Aspiration amplitude in dB (lower-case `h` matches the C field).
        Af: Frication amplitude in dB.
        F1, B1: First formant frequency and bandwidth.
        DF1, DB1: First-formant deltas applied during the open phase.
        F2..F6, B2..B6: Higher-formant frequency and bandwidth pairs.
        FNP, BNP: Nasal pole frequency and bandwidth.
        FNZ, BNZ: Nasal zero (anti-resonator) frequency and bandwidth.
        FTP, BTP: Tracheal pole frequency and bandwidth.
        FTZ, BTZ: Tracheal zero frequency and bandwidth.
        A2f..A6f: Parallel-formant frication amplitudes.
        Ab: Bypass amplitude.
        B2F..B6F: Parallel-formant frication bandwidths.
        ANV, A1V..A4V, ATV: Nasal-pole, parallel-voicing, tracheal-pole amps.
    """

    F0: int = 0
    AV: int = 0
    OQ: int = 0
    SQ: int = 0
    TL: int = 0
    FL: int = 0
    DI: int = 0
    Ah: int = 0
    Af: int = 0

    # Defaults follow the neutral-vowel resting positions used by the C
    # synthesizer's LLInit. Zero formants would cause set_zero_pair to divide
    # by zero (the C silently produces +inf and continues; we'd rather start
    # from a valid filter state).
    F1: int = 500
    B1: int = 60
    DF1: int = 0
    DB1: int = 0
    F2: int = 1500
    B2: int = 90
    F3: int = 2500
    B3: int = 150
    F4: int = 3500
    B4: int = 200
    F5: int = 4500
    B5: int = 250
    F6: int = 5500
    B6: int = 500

    FNP: int = 270
    BNP: int = 100
    FNZ: int = 270
    BNZ: int = 100
    FTP: int = 2150
    BTP: int = 180
    FTZ: int = 2150
    BTZ: int = 180

    A2f: int = 0
    A3f: int = 0
    A4f: int = 0
    A5f: int = 0
    A6f: int = 0
    Ab: int = 0
    # Parallel-formant bandwidths. The C code populates these from the
    # dictionary; defaulting to 0 here would make the parallel pole pair
    # undamped (infinite Q) and the F4-F6 parallel resonators would ring
    # at their centre frequencies forever once excited by any frication
    # noise. Use the same widths as the cascade as a safe default.
    B2F: int = 250
    B3F: int = 300
    B4F: int = 400
    B5F: int = 500
    B6F: int = 700

    ANV: int = 0
    A1V: int = 0
    A2V: int = 0
    A3V: int = 0
    A4V: int = 0
    ATV: int = 0


@dataclass(slots=True)
class LLSynth:
    """Top-level Klatt synthesizer instance.

    Mirrors the C `LLSynth` struct: state, coefficients, speaker, and the
    full bank of resonators (cascade + parallel + "special" pitch-synchronous
    + anti-resonators), plus the per-sample output tap array.

    Attributes:
        state: Running :class:`Synthesizer` state.
        coefs: Per-frame :class:`Coefficients`.
        spkr: :class:`Speaker` definition.
        glottal_pulse: Resonator shaping the glottal source.
        spectral_tilt: One-pole spectral-tilt resonator on the source.
        nasal_pole_cascade: Nasal pole in the cascade branch.
        formant_1_cascade .. formant_8_cascade: Cascade-branch formants.
        formant_2_parallel .. formant_6_parallel: Parallel-branch formants.
        trach_pole_cascade: Tracheal pole resonator.
        formant_1_special .. formant_4_special: Pitch-synchronous "special"
            resonators used for the open-phase F1 transition.
        nasal_pole_special, trach_pole_special: Pitch-synchronous nasal and
            tracheal pole resonators.
        nasal_zero_cascade, trach_zero_cascade: Anti-resonators for the
            cascade nasal and tracheal zeros.
        out: NUM_OUTPUTS-element list of the per-sample output taps.
    """

    state: Synthesizer = field(default_factory=Synthesizer)
    coefs: Coefficients = field(default_factory=Coefficients)
    spkr: Speaker = field(default_factory=Speaker)

    glottal_pulse: Resonator = field(default_factory=Resonator)
    spectral_tilt: Resonator = field(default_factory=Resonator)

    nasal_pole_cascade: Resonator = field(default_factory=Resonator)
    formant_1_cascade: Resonator = field(default_factory=Resonator)
    formant_2_cascade: Resonator = field(default_factory=Resonator)
    formant_3_cascade: Resonator = field(default_factory=Resonator)
    formant_4_cascade: Resonator = field(default_factory=Resonator)
    formant_5_cascade: Resonator = field(default_factory=Resonator)
    formant_6_cascade: Resonator = field(default_factory=Resonator)
    formant_7_cascade: Resonator = field(default_factory=Resonator)
    formant_8_cascade: Resonator = field(default_factory=Resonator)

    formant_2_parallel: Resonator = field(default_factory=Resonator)
    formant_3_parallel: Resonator = field(default_factory=Resonator)
    formant_4_parallel: Resonator = field(default_factory=Resonator)
    formant_5_parallel: Resonator = field(default_factory=Resonator)
    formant_6_parallel: Resonator = field(default_factory=Resonator)

    trach_pole_cascade: Resonator = field(default_factory=Resonator)

    formant_1_special: Resonator = field(default_factory=Resonator)
    formant_2_special: Resonator = field(default_factory=Resonator)
    formant_3_special: Resonator = field(default_factory=Resonator)
    formant_4_special: Resonator = field(default_factory=Resonator)
    nasal_pole_special: Resonator = field(default_factory=Resonator)
    trach_pole_special: Resonator = field(default_factory=Resonator)

    nasal_zero_cascade: Resonator = field(default_factory=Resonator)
    trach_zero_cascade: Resonator = field(default_factory=Resonator)

    out: list[float] = field(default_factory=lambda: [0.0] * NUM_OUTPUTS)
