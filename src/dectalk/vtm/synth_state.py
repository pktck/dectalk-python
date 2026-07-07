"""Per-handle synthesizer state for the integer Klatt VTM.

Translated from ``src/dapi/src/vtm/vtminst.h`` lines 136-687 (the
``VTM_T`` struct, ``#else // FP_VTM`` branch). The Python port
captures only the fields the active ``vtm1.c`` synthesizer path
reads or writes.

The full ``VTM_T`` struct is 400+ fields covering every conditional
compile (HLSYN, FP_VTM, NEW_VTM, COMPRESSION, UPGRADES1999,
HLSYN_NEWPOLE, ...). The active linux build
(``dectalkf_klsyn.h`` + ``vtm/Makefile``) compiles with ``VTM1``
defined and none of those, so the actual field set is much smaller.
This module enumerates *only* the fields touched by the active
``vtm1.c::speech_waveform_generator``, ``read_speaker_definition``,
and ``InitializeVTM`` paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 71 samples/frame at 11025 Hz (10/11 kHz path); see
# ``vtm1.c::SetSampleRate`` lines 2024-2044. The 8 kHz path uses
# 51 samples/frame but the active build targets PC_SAMPLE_RATE=11025.
DEFAULT_FRAMES_PER_BUFFER: int = 71

#: ``DT_PIPE_T parambuff[41];`` from ``vtminst.h`` line 168.
#: PH writes index 0 as the packet header; OUT_* starts at index 1.
PARAMBUFF_SIZE: int = 41

#: ``S16 iwave[MAXIMUM_FRAME_SIZE];`` — output buffer.
#: ``MAXIMUM_FRAME_SIZE = 710`` covers ``:spf 500@22kHz``.
MAXIMUM_FRAME_SIZE: int = 710

#: Random-number-generator constants seeded by
#: ``read_speaker_definition`` at lines 1571-1572 of vtm1.c.
RANMUL: int = 20077
RANADD: int = 12345

#: Pi-rotated antiresonator ``c`` coefficient, seeded at lines
#: 1584/1592/1600 of vtm1.c (same across all sample-rate cases).
NOISEC: int = 1499  # Q4.12 -> 0.365966796875


@dataclass(slots=True)
class SynthState:
    """Per-handle state for ``vtm1.c::speech_waveform_generator``.

    Field names match the C source verbatim so the per-line port is
    line-by-line greppable. The dataclass is mutable; the synth
    pipeline updates filter delays and the per-period bookkeeping
    in place across frames.
    """

    parambuff: list[int] = field(default_factory=lambda: [0] * PARAMBUFF_SIZE)
    iwave: list[int] = field(default_factory=lambda: [0] * MAXIMUM_FRAME_SIZE)

    # Sample-rate calibration -------------------------------------------------
    uiSampleRateChange: int = 0  # noqa: N815
    rate_scale: int = 18063  # Q14 (=1.1025) at 11 kHz
    inv_rate_scale: int = 29722  # Q15 (=0.909) at 11 kHz
    uiNumberOfSamplesPerFrame: int = DEFAULT_FRAMES_PER_BUFFER  # noqa: N815
    SampleRate: float = 11025.0
    bEightKHz: bool = False  # noqa: N815

    # Speaker-definition parameters (loaded by read_speaker_definition) -------
    fnscal: int = 4096
    t0jitr: int = 0
    Aturb: int = 0
    avgain: int = 0
    APgain: int = 0
    AFgain: int = 0
    AFcgain: int = 0
    r1cg: int = 0
    r2cg: int = 0
    r3cg: int = 0
    R4ca: int = 0
    R4cb: int = 0
    R4cc: int = 0
    R5ca: int = 0
    R5cb: int = 0
    R5cc: int = 0
    R4pb: int = 0
    r4pc: int = 0
    R5pb: int = 0
    r5pc: int = 0
    r6pb: int = -5702  # vtm1.c line 1759
    r6pc: int = -1995  # vtm1.c line 1760
    rnpa: int = 0
    rnpb: int = 0
    rnpc: int = 0
    rnza: int = 0
    rnzb: int = 0
    rnzc: int = 0
    rlpa: int = 0
    rlpb: int = 0
    rlpc: int = 0
    k1: int = 0
    k2: int = 0
    noiseb: int = -2913  # Q4.12 at 11 kHz (SAMPLE_RATE_INCREASE branch)
    SpeakerGain: int = 0

    # Resonator delays --------------------------------------------------------
    r2pd1: int = 0
    r2pd2: int = 0
    r3pd1: int = 0
    r3pd2: int = 0
    r4pd1: int = 0
    r4pd2: int = 0
    r5pd1: int = 0
    r5pd2: int = 0
    r6pd1: int = 0
    r6pd2: int = 0
    r1cd1: int = 0
    r1cd2: int = 0
    R1ca: int = 0
    r1cb: int = 0
    r1cc: int = 0
    r2cd1: int = 0
    r2cd2: int = 0
    R2ca: int = 0
    r2cb: int = 0
    r2cc: int = 0
    r3cd1: int = 0
    r3cd2: int = 0
    R3ca: int = 0
    r3cb: int = 0
    r3cc: int = 0
    r4cd1: int = 0
    r4cd2: int = 0
    r5cd1: int = 0
    r5cd2: int = 0
    rnpd1: int = 0
    rnpd2: int = 0
    rnzd1: int = 0
    rnzd2: int = 0
    rlpd1: int = 0
    rlpd2: int = 0
    ablas1: int = 0
    ablas2: int = 0
    vlast: int = 0

    # Glottal-pulse / per-frame state -----------------------------------------
    randomx: int = 0
    ldspdef: int = 0
    voice0: int = 0
    a: int = 0
    b: int = 0
    avlin: int = 0
    avlind: int = 0
    aturb1: int = 0
    nper: int = 0
    # T0 / nopen start at 0, matching the C ``calloc(1, sizeof(VTM_T))``
    # zero-init in the VTM bring-up (``vtmiont.c``). This is load-bearing
    # for byte parity (issue #284): with ``T0 == nper == 0`` the very
    # first inner tick of the first frame trips the pitch-synchronous
    # ``nper == T0`` update, loading T0 / nopen / decay and all cascade
    # coefficients from frame 0's packet before any sample is filtered.
    # A non-zero default (the port used to say 100/40) free-runs the
    # glottal source for T0 ticks on fabricated values instead, skewing
    # every later pitch-period boundary — the sample-214 onset residual.
    T0: int = 0
    nopen: int = 0
    nmod: int = 0
    nolast: int = 0
    decay: int = 0
    one_minus_decay: int = 0
    rampdown: int = 0
    temp: int = 0

    # Misc bookkeeping --------------------------------------------------------
    bDoTuning: bool = False  # noqa: N815


__all__ = [
    "DEFAULT_FRAMES_PER_BUFFER",
    "MAXIMUM_FRAME_SIZE",
    "NOISEC",
    "PARAMBUFF_SIZE",
    "RANADD",
    "RANMUL",
    "SynthState",
]
