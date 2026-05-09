"""Synthesizer state and amplitude constants.

Translated from `src/dapi/src/hlsyn/synth.h`. Provides:

- :data:`TWO_PI` and :func:`db2amp` — basic math helpers used throughout.
- The ``A_*`` amplitude-adjustment constants for each Klatt amplitude
  parameter (AV voicing, AH aspiration, AF frication, parallel-formant amps,
  etc.). They are negative dB offsets the synthesizer applies on top of the
  per-voice base gain.
- :class:`Synthesizer` — running synth state (period counters, glottal
  state, current voicing parameters).
- :class:`Coefficients` — per-frame amplitude scaling coefficients fed to
  the cascade-parallel circuit.
- Index enums (:class:`SpeakerIdx`, :class:`ParamIdx`, :class:`OutputIdx`)
  for the legacy flat-array forms of speaker / frame / output buffers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final

TWO_PI: Final[float] = 6.2831852
"""Single-precision 2π, matching the C `#define`."""


def db2amp(x: float) -> float:
    """Convert a decibel value to a linear amplitude multiplier.

    Args:
        x: Amplitude in decibels.

    Returns:
        ``10**(x/20)``.
    """
    return 10.0 ** (x / 20.0)


# -- Amplitude adjustment constants (negative dB offsets) ------------------
A_AV: Final[float] = -20.5
A_AH: Final[float] = -64.3
A_AF: Final[float] = -43.7
A_AP: Final[float] = -28.0
A_A1: Final[float] = -58.0
A_A2F: Final[float] = -70.0
A_A3F: Final[float] = -77.0
A_A4F: Final[float] = -82.6
A_A5F: Final[float] = -86.7
A_A6F: Final[float] = -87.7
A_AB: Final[float] = -73.5
A_ANV: Final[float] = -68.7
A_A1V: Final[float] = -69.1
A_A2V: Final[float] = -77.5
A_A3V: Final[float] = -84.9
A_A4V: Final[float] = -88.5
A_ATV: Final[float] = -81.5

NUM_OUTPUTS: Final[int] = 21
"""Number of distinct output taps the synthesizer can emit per sample."""


class SpeakerIdx(IntEnum):
    """Offsets into the legacy flat-array speaker description."""

    DU = 0
    UI = 1
    SR = 2
    NF = 3
    SS = 4
    RS = 5
    SB = 6
    CP = 7
    OS = 8
    GV = 9
    GH = 10
    GF = 11


class ParamIdx(IntEnum):
    """Offsets into the legacy flat-array frame parameter description."""

    F0 = 0
    AV = 1
    OQ = 2
    SQ = 3
    TL = 4
    FL = 5
    DI = 6
    AH = 7
    AF = 8
    F1 = 9
    B1 = 10
    DF1 = 11
    DB1 = 12
    F2 = 13
    B2 = 14
    F3 = 15
    B3 = 16
    F4 = 17
    B4 = 18
    F5 = 19
    B5 = 20
    F6 = 21
    B6 = 22
    FNP = 23
    BNP = 24
    FNZ = 25
    BNZ = 26
    FTP = 27
    BTP = 28
    FTZ = 29
    BTZ = 30
    A2F = 31
    A3F = 32
    A4F = 33
    A5F = 34
    A6F = 35
    AB = 36
    B2F = 37
    B3F = 38
    B4F = 39
    B5F = 40
    B6F = 41
    ANV = 42
    A1V = 43
    A2V = 44
    A3V = 45
    A4V = 46
    ATV = 47
    F0NEXT = 48


class OutputIdx(IntEnum):
    """Offsets into the synthesizer's per-sample output tap array.

    The legacy interface returns one of these waveforms depending on
    debugging needs. ``NORMAL`` is the combined speech output.
    """

    NORMAL = 0
    VOICING = 1
    ASPIRATION = 2
    FRICATION = 3
    GLOTTAL = 4
    TRACHEAL_CASC = 5
    NASAL_ZERO_CASC = 6
    NASAL_POLE_CASC = 7
    FORMANT_5_CASC = 8
    FORMANT_4_CASC = 9
    FORMANT_3_CASC = 10
    FORMANT_2_CASC = 11
    FORMANT_1_CASC = 12
    FORMANT_6_PARA = 13
    FORMANT_5_PARA = 14
    FORMANT_4_PARA = 15
    FORMANT_3_PARA = 16
    FORMANT_2_PARA = 17
    FORMANT_1_PARA = 18
    NASAL_PARA = 19
    BYPASS_PARA = 20


@dataclass(slots=True)
class Synthesizer:
    """Running synthesizer state held across samples.

    Mirrors the C `Synthesizer` struct in `synth.h`.

    Attributes:
        parallel_only_flag: Non-zero to mute the cascade branch.
        num_casc_formants: Number of cascade formants currently active (4-8).
        num_samples: Frame size in samples.
        output_select: Which :class:`OutputIdx` tap to emit.
        pulse_freq: Glottal pulse period in samples for the current cycle.
        glottis_open: 1 during the open phase, 0 during closed phase.
        period_ctr: Samples remaining until the next glottal transition.
        voicing_state: 1-sample-delayed value of `pulse` for impulse-source mode.
        pulse: 1 only on the very first sample of an open phase.
        random: Pseudo-random bit used by the noise generator.
        voicing_time: Sample count since the start of the current voicing cycle.
        global_time: Continuously-running sample counter (for flutter).
        voicing_amp: Linear amplitude derived from ``GV + AV + A_AV``.
        glottal_state: Memory cell for the natural-source low-pass filter.
        asp_state: Memory cell for the aspiration noise filter.
        integrator: First-order integrator memory.
        f0: Latched fundamental frequency for the current cycle (Hz x 10).
        fl: Flutter parameter (Klatt's pitch jitter amount).
        oq: Open quotient (% of cycle the glottis is open).
        sq: Speed quotient parameter for the LF source.
        di: Diplophonia parameter.
        av: Voicing amplitude in dB.
        tl: Spectral-tilt parameter (selects from the tilt table).
        close_shortened: Diplophonia bookkeeping flag.
        close_time: Samples in the closed phase of the current cycle.
    """

    parallel_only_flag: int = 0
    num_casc_formants: int = 0
    num_samples: int = 0
    output_select: int = int(OutputIdx.NORMAL)

    pulse_freq: int = 0
    glottis_open: int = 0
    period_ctr: int = 0
    voicing_state: int = 0
    pulse: int = 0
    random: int = 0
    voicing_time: int = 0
    global_time: int = 0
    voicing_amp: float = 0.0
    glottal_state: float = 0.0
    asp_state: float = 0.0
    integrator: float = 0.0

    f0: int = 0
    fl: int = 0
    oq: int = 0
    sq: int = 0
    di: int = 0
    av: int = 0
    tl: int = 0
    close_shortened: int = 0
    close_time: int = 0


@dataclass(slots=True)
class Coefficients:
    """Per-frame amplitude scaling coefficients for the cascade-parallel circuit.

    Mirrors the C `Coefficients` struct in `synth.h`.
    """

    asp_amp: float = 0.0
    fric_amp: float = 0.0
    f1p_amp: float = 0.0
    f2p_amp: float = 0.0
    f3p_amp: float = 0.0
    f4p_amp: float = 0.0
    f5p_amp: float = 0.0
    f6p_amp: float = 0.0
    npv_amp: float = 0.0
    f1v_amp: float = 0.0
    f2v_amp: float = 0.0
    f3v_amp: float = 0.0
    f4v_amp: float = 0.0
    tpv_amp: float = 0.0
    bypass_amp: float = 0.0
