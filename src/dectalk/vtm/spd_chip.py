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
It is never instantiated directly in the linkable C sources shipped in
the source release -- ``setspdef()`` (still resident in the closed-
source ``libttsapi.so``) is the bridge that re-arranges the public
``SPDEF[]`` voice tables into chip layout.  The field-by-field mapping
documented below is therefore reconstructed from:

* The ``SPDEF`` input slot ordering in ``p_us_vdf*.c`` voice tables
  (``SEX, SM, AS, AP, PR, BR, RI, NF, LA, HS, F4, B4, F5, B5, F7, F8,
  GF, GH, GV, GN, G1, G2, G3, G4, LO, FT, BF, LX, QU, HR, SR, AGO,
  AGVO, AGUO, UNVOW, CHINK, OQ, OS``).
* The chip-side ``SPD_CHIP`` field comments in ``viphdefs.h``.
* The Python-side annotations on :class:`SpdChip`.

SPDEF -> SPD_CHIP field mapping::

    r4cb  <- B4   (resonator-4 cascade bandwidth, Hz)
    r4cc  <- F4   (resonator-4 cascade centre frequency, Hz)
    r5cb  <- B5   (resonator-5 cascade bandwidth, Hz)
    r5cc  <- F5   (resonator-5 cascade centre frequency, Hz)
    r4pb  <- F7   (parallel-4 frequency -- field name says
                   ``r4pb`` / bandwidth but the SPDEF value is a
                   frequency; this is a longstanding C quirk
                   carried over by SpdChip)
    r5pb  <- F8   (parallel-5 frequency, same quirk)
    r5ca  <- G1   (cascade gain into resonator 5, dB)
    r4ca  <- G2   (cascade gain into resonator 4, dB)
    r3ca  <- G3   (cascade gain into resonator 3, dB)
    r2ca  <- G4   (cascade gain into resonator 2, dB)
    r1ca  <- LO   (loudness / gain into resonator 1, dB)
    afgain  <- GF   (frication source gain, dB)
    apgain  <- GH   (aspiration source gain, dB)
    azgain  <- GV   (glottal / voicing source gain, dB)
    rnpgain <- GN   (cascade nasal-pole pair gain, dB)
    fnscale <- derived from HS (formant-frequency Q12 scaler;
                 HS = 100 -> 4096 = Q12 unity)
    osgain  <- SPD_OS (output gain multiplier; ``ph_vset.c:789`` copies
                 ``curspdef[SPD_OS]`` into ``osgain``). Paul's 4.3 row
                 sets it to 0, and ``paul_tune`` is all-zero, so the
                 effective ``osgain`` is 0 -- i.e. no output-stage dB
                 delta (``vtm_f.c`` reads ``dBtoLinear[87 + osgain]``).
    sex     <- SEX (1 = MALE, 0 = FEMALE)
    speaker <- 0 (Paul is the canonical zero-index voice)

The non-``_8`` ``paul`` row is used (not the 8 kHz ``paul_8`` HLSYN row
from ``p_us_vdf1.c``) because ``dectalkf.h`` selects the non-HLSYN
``VDF_DECTALK_43`` build, and the integer (``VTM1``) cascade path runs at
11025 Hz where ``ph_vset.c`` picks ``voidef[voice]``.

``nopen1`` / ``nopen2`` / ``aturb`` / ``t0jit`` / ``notused`` stay zero:
the 4.3 row carries no open-quotient / turbulence / jitter overrides
(those AGO..OQ slots are all zero), and the HLSyn glottal-source state
is not part of the integer cascade chip block.
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
_PAUL_R4CC: int = 3300  # F4 (C value: 3300)
_PAUL_R5CB: int = 330  # B5 (C value: 330)
_PAUL_R5CC: int = 3650  # F5 (C value: 3650)
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
# fnscale = 4096 because HS = 100 (nominal head size).  The chip-side
# ``fnscale`` is derived from HS at setspdef() time; for HS = 100 the
# resulting Q12 scaler is exactly 1.0 = 4096.
_PAUL_FNSCALE: int = 4096
# SPD_OS (output gain multiplier) = 0 in the 4.3 paul row, and the active
# paul_tune delta is 0, so osgain is 0 (no output-stage dB offset). The
# old -1 came from the stale paul_8 / p_us_vdf.c lineage.
_PAUL_OSGAIN: int = 0
_PAUL_SEX: int = 1  # MALE


def default_us_paul_spd() -> SpdChip:
    """Return a fresh :class:`SpdChip` initialised with US-Paul voice defaults.

    Values are extracted from ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c``
    ``paul[SPDEF]`` -- the non-``_8`` DECtalk 4.3 speaker definition the
    live synthesizer loads at 11025 Hz.

    ``fnscale`` is 4096 (Q12 unity) because Paul's head-size parameter
    (``HS``) is 100 -- the nominal value.  Any voice with a non-standard
    head size would have a different fnscale.

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
        nopen1=0,
        nopen2=0,
        aturb=0,
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
