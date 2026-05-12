"""Speaker-definition chip-parameters struct from viphdefs.h.

Translated from ``src/dapi/src/vtm/viphdefs.h``. ``SPD_CHIP`` is
the per-speaker block sent to the original DECtalk signal-processing
chip — 23 ``short`` fields describing resonator 4/5 (cascade and
parallel), nasal pole/zero gains, voicing gain, sex, speaker ID.

In the original C code the first ``SPDEF_PARS`` words of this
struct are streamed to the SPC; the rest are bookkeeping. The
Python port models all fields as a dataclass since the audio
back-end is the bit-accurate hlsyn synthesizer, not a physical chip.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SpdChip:
    """Per-speaker chip parameters (23 fields).

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            short r4cb;    short r4cc;    short r5cb;    short r5cc;
            short r4pb;    short r5pb;    short t0jit;
            short r5ca;    short r4ca;    short r3ca;    short r2ca;
            short r1ca;
            short nopen1;  short nopen2;
            short aturb;   short fnscale;
            short afgain;  short rnpgain; short azgain;  short apgain;
            short notused; // was tltoff
            short osgain;
            short speaker;
            short sex;
        } SPD_CHIP;

    Attributes:
        r4cb / r4cc: Resonator 4 cascade bandwidth / centre frequency.
        r5cb / r5cc: Resonator 5 cascade.
        r4pb / r5pb: Resonators 4 / 5 parallel bandwidths.
        t0jit: Jitter (T0 perturbation).
        r5ca / r4ca / r3ca / r2ca / r1ca: Cascade amplitudes for
            resonators 5 / 4 / 3 / 2 / 1.
        nopen1 / nopen2: Open-quotient parameters.
        aturb: Turbulence noise amplitude.
        fnscale: Nasal-pole frequency scale.
        afgain / rnpgain / azgain / apgain: Frication / nasal-pole /
            nasal-zero / aspiration gains.
        notused: Reserved (was ``tltoff`` — tilt offset, now unused).
        osgain: Output stage gain.
        speaker: Speaker ID (0..8 for Paul..Wendy).
        sex: 1 = male, 0 = female (matches MALE / FEMALE in
            :mod:`dectalk.ph.numeric_constants`).
    """

    r4cb: int = 0
    r4cc: int = 0
    r5cb: int = 0
    r5cc: int = 0
    r4pb: int = 0
    r5pb: int = 0
    t0jit: int = 0
    r5ca: int = 0
    r4ca: int = 0
    r3ca: int = 0
    r2ca: int = 0
    r1ca: int = 0
    nopen1: int = 0
    nopen2: int = 0
    aturb: int = 0
    fnscale: int = 0
    afgain: int = 0
    rnpgain: int = 0
    azgain: int = 0
    apgain: int = 0
    notused: int = 0
    osgain: int = 0
    speaker: int = 0
    sex: int = 0


__all__ = ["SpdChip"]
