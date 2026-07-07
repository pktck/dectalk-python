"""US-Paul SPD_CHIP defaults and factory.

Re-exports :class:`~dectalk.ph.spdef_chip.SpdChip` (the dataclass mirror
of the C ``SPD_CHIP`` struct from ``viphdefs.h``) and adds a factory that
returns the US-English Paul-voice defaults extracted from
``p_us_vdf_dectalk43.c`` ``paul[SPDEF]`` -- the **non-``_8``** DECtalk 4.3
speaker definition the synthesizer actually uses at the default 11025 Hz
sample rate (``ph_vset.c:449-459`` loads ``voidef[voice]`` = ``paul``
when ``uiSampleRate >= 8763``; the ``_8`` rows are the 8 kHz variants).

The C ``SPD_CHIP`` struct (defined in ``vtm/viphdefs.h`` lines 306--331)
is the chip-format 24-field block streamed to the original DECtalk DSP.
The bridge that re-arranges the public ``SPDEF[]`` voice tables into
chip layout is ``setspdef()`` in ``ph_vset.c`` (lines 541--789) -- it
is open source, and its derivations are what this factory hard-codes.
The values below are verified against the actual ``SPC_type_speaker``
packet the oracle's PH stage emits (captured via the patch-0005
``vtm.dump`` hook on ``hello world``; issue #284): all 24 words match.

SPDEF -> SPD_CHIP derivations (``ph_vset.c`` line refs)::

    fnscale <- (200 - HS) * 41            (line 638; HS=100 -> 4100,
                 NOT 4096 -- Q12 "unity" head size is deliberately
                 41*100 in the C, a ~0.1% upward formant scale)
    F4chip  <- (F4 * fnscale) >> 12       (line 648; 3300 -> 3303)
    B4chip  <- B4                         (line 653)
    F5chip  <- (F5 * fnscale) >> 12       (line 670; 3650 -> 3653)
    B5chip  <- B5                         (line 684)
    r4pb    <- F7  (parallel-4 frequency; field name says bandwidth
                    but the value is a frequency -- C quirk)
    r5pb    <- F8  (parallel-5 frequency, same quirk)
    t0jit   <- LA << 3                    (line 701; LA=0 -> 0)
    r5ca    <- G1   (cascade gain into resonator 5, dB)
    r4ca    <- G2   (cascade gain into resonator 4, dB)
    r3ca    <- G3   (cascade gain into resonator 3, dB)
    r2ca    <- G4   (cascade gain into resonator 2, dB)
    r1ca    <- LO   (loudness / gain into resonator 1, dB)
    nopen1  <- 4000 + 160 * (100 - RI)    (line 717; RI=70 -> 8800;
                 the glottal open-phase K1 in ``vtm1.c`` line 915:
                 ``nopen = frac1mul(k1, T0) + k2``)
    nopen2  <- NF * 4                     (line 718; NF=0 -> 0)
    aturb   <- BR + 9                     (line 722, the non-HLSYN /
                 non-CHANGES_AFTER_V43 branch; BR=0 -> 9. The +9 bias
                 lands in ``amptable[9]`` == 0, so Paul still gets no
                 breathiness -- but the chip word itself is 9.)
    afgain  <- GF   (frication source gain, dB)
    apgain  <- GH   (aspiration source gain, dB)
    azgain  <- GV   (glottal / voicing source gain, dB)
    rnpgain <- GN   (cascade nasal-pole pair gain, dB)
    osgain  <- SPD_OS (output gain multiplier; ``ph_vset.c:789`` copies
                 ``curspdef[SPD_OS]`` into ``osgain``). Paul's 4.3 row
                 sets it to 0, and ``paul_tune`` is all-zero, so the
                 effective ``osgain`` is 0 -- i.e. no output-stage dB
                 delta (``vtm_f.c`` reads ``dBtoLinear[87 + osgain]``).
    sex     <- SEX (1 = MALE, 0 = FEMALE)
    speaker <- 0 (Paul is the canonical zero-index voice)

**Field-name convention caveat**: in the true chip layout (and in
``setspdef``/``vtm1.c``) the *frequency* lands in ``r4cb``/``r5cb`` and
the *bandwidth* in ``r4cc``/``r5cc`` (``vtm1.c`` line 1705:
``f4c = chip->r4cb; b4c = chip->r4cc``). The Python :class:`SpdChip`
consumers (:func:`dectalk.vtm.seed_speaker_state.seed_speaker_state`
and ``ph/parstochip_to_frames.py``) adopted the opposite convention --
frequency in ``r4cc``/``r5cc`` -- and this factory follows *them* so
the trio stays internally consistent. Only the VALUES matter for
parity; the swap is compensated at every read site.

The non-``_8`` ``paul`` row is used (not the 8 kHz ``paul_8`` HLSYN row
from ``p_us_vdf1.c``) because ``dectalkf.h`` selects the non-HLSYN
``VDF_DECTALK_43`` build, and the integer (``VTM1``) cascade path runs at
11025 Hz where ``ph_vset.c`` picks ``voidef[voice]``.
"""

from __future__ import annotations

# Re-export the shared dataclass so callers only need this module.
from dectalk.ph.spdef_chip import SpdChip

__all__ = ["SpdChip", "default_us_paul_spd"]

# ---------------------------------------------------------------------------
# US-English Paul-voice constants
#
# Source: ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c`` lines
# 383--423 (``const short paul[SPDEF]``, the active non-``_8`` DECtalk 4.3
# speaker definition).
#
# Every numeric default below corresponds to a single SPDEF slot in
# that array; the SPDEF -> SPD_CHIP mapping is documented in the
# module docstring.  The "C value" annotation lists the literal in
# p_us_vdf_dectalk43.c so the trail back to the source is one ``rg`` away.
# ---------------------------------------------------------------------------

_PAUL_R4CB: int = 260  # B4 (C value: 260)
# F4 chip word = (F4 * fnscale) >> 12 = (3300 * 4100) >> 12 = 3303
# (``ph_vset.c`` line 648) -- the SPDEF table's 3300 is pre-scaled by
# fnscale before it is streamed to the chip. Verified against the
# oracle's SPC_type_speaker packet (issue #284).
_PAUL_R4CC: int = 3303
_PAUL_R5CB: int = 330  # B5 (C value: 330)
# F5 chip word = (3650 * 4100) >> 12 = 3653 (``ph_vset.c`` line 670).
_PAUL_R5CC: int = 3653
_PAUL_R4PB: int = 3350  # F7 (C value: 3350) -- frequency despite "pb" name
_PAUL_R5PB: int = 3850  # F8 (C value: 3850) -- frequency despite "pb" name
_PAUL_R5CA: int = 68  # G1 (C value: 68)
_PAUL_R4CA: int = 60  # G2 (C value: 60)
_PAUL_R3CA: int = 48  # G3 (C value: 48)
_PAUL_R2CA: int = 64  # G4 (C value: 64)
_PAUL_R1CA: int = 86  # LO (C value: 86)
_PAUL_AFGAIN: int = 70  # GF (C value: 70)
_PAUL_APGAIN: int = 70  # GH (C value: 70)
_PAUL_AZGAIN: int = 65  # GV (C value: 65)
_PAUL_RNPGAIN: int = 74  # GN (C value: 74)
# fnscale = (200 - HS) * 41 (``ph_vset.c`` line 638). HS = 100 gives
# 4100, NOT the Q12-unity 4096 the port previously assumed: the C
# bridge's "unity" head size deliberately over-scales formants by
# 4100/4096 (~0.1%), and ``vtm1.c`` line 446-451 then multiplies
# F1/F2/F3 by this value per frame. Byte parity at voicing onset
# (issue #284) is sensitive to the resulting 1-3 Hz formant shifts.
_PAUL_FNSCALE: int = 4100
# nopen1 = 4000 + 160 * (100 - RI) (``ph_vset.c`` line 717). Paul's
# richness RI = 70 gives 8800. This is K1 of the glottal open-phase
# duration ``nopen = frac1mul(k1, T0) + k2`` (``vtm1.c`` line 915);
# the previous 0 kept the open phase pinned at the 40-tick floor.
_PAUL_NOPEN1: int = 8800
# nopen2 = NF * 4 (``ph_vset.c`` line 718); Paul NF = 0.
_PAUL_NOPEN2: int = 0
# aturb = BR + 9 (``ph_vset.c`` line 722, non-HLSYN branch); Paul
# BR = 0 gives 9. amptable[9] == 0 so the audible effect for Paul is
# nil, but the chip word matches the oracle packet.
_PAUL_ATURB: int = 9
# SPD_OS (output gain multiplier) = 0 in the 4.3 paul row, and the active
# paul_tune delta is 0, so osgain is 0 (no output-stage dB offset). The
# old -1 came from the stale paul_8 / p_us_vdf.c lineage.
_PAUL_OSGAIN: int = 0
_PAUL_SEX: int = 1  # MALE


def default_us_paul_spd() -> SpdChip:
    """Return a fresh :class:`SpdChip` initialised with US-Paul voice defaults.

    Values are the ``setspdef()`` (``ph_vset.c`` lines 541-789) chip
    derivations of ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c``
    ``paul[SPDEF]`` -- the non-``_8`` DECtalk 4.3 speaker definition the
    live synthesizer loads at 11025 Hz. Every word is byte-verified
    against the oracle's captured ``SPC_type_speaker`` packet
    (issue #284): the chip block streamed for ``hello world`` is
    ``[3303, 260, 3653, 330, 3350, 3850, 0, 68, 60, 48, 64, 86, 8800,
    0, 9, 4100, 70, 74, 65, 70, 0, 0, 0, 1]`` in C field order
    ``(r4cb=F4chip, r4cc=B4, r5cb=F5chip, r5cc=B5, ...)``; this factory
    stores the same values under the Python swapped freq/bw field
    convention (see module docstring).

    ``fnscale`` is 4100 = ``(200 - HS) * 41`` for Paul's nominal head
    size HS = 100. Any voice with a non-standard head size would have
    a different fnscale (and different F4/F5 chip words, which are
    pre-scaled by fnscale).

    Returns:
        A new :class:`SpdChip` instance with Paul-voice defaults.
    """
    return SpdChip(
        r4cb=_PAUL_R4CB,
        r4cc=_PAUL_R4CC,
        r5cb=_PAUL_R5CB,
        r5cc=_PAUL_R5CC,
        r4pb=_PAUL_R4PB,
        r5pb=_PAUL_R5PB,
        t0jit=0,
        r5ca=_PAUL_R5CA,
        r4ca=_PAUL_R4CA,
        r3ca=_PAUL_R3CA,
        r2ca=_PAUL_R2CA,
        r1ca=_PAUL_R1CA,
        nopen1=_PAUL_NOPEN1,
        nopen2=_PAUL_NOPEN2,
        aturb=_PAUL_ATURB,
        fnscale=_PAUL_FNSCALE,
        afgain=_PAUL_AFGAIN,
        rnpgain=_PAUL_RNPGAIN,
        azgain=_PAUL_AZGAIN,
        apgain=_PAUL_APGAIN,
        notused=0,
        osgain=_PAUL_OSGAIN,
        speaker=0,  # Paul = speaker index 0
        sex=_PAUL_SEX,
    )
