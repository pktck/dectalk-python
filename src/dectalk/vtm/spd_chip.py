"""US-Paul SPD_CHIP defaults and factory.

Re-exports :class:`~dectalk.ph.spdef_chip.SpdChip` (the dataclass mirror
of the C ``SPD_CHIP`` struct from ``viphdefs.h``) and adds a factory that
returns the US-English Paul-voice defaults extracted from
``p_us_vdf1.c`` ``paul_8[SPDEF]`` -- the HLSYN-build 8 kHz speaker
definition that backs the active synthesizer path.

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
  agvo, aguo, unvow, chink, open_quo``).
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
    osgain  <- -1 (auto pass-through; only the ``FP_VTM`` build of
                 ``paul_8`` ships an explicit output-gain
                 multiplier, and the linux build does not define
                 ``FP_VTM``)
    sex     <- SEX (1 = MALE, 0 = FEMALE)
    speaker <- 0 (Paul is the canonical zero-index voice)

The HLSYN-build values (``p_us_vdf1.c`` ``paul_8``) are used because
that is the file the live ``libttsapi.so`` actually links against;
``p_us_vdf_dectalk43.c`` ``paul`` (the 11 kHz cascade-only variant)
is preserved on disk but the cascade signal path is not active when
HLSYN is enabled.

``nopen1`` / ``nopen2`` / ``aturb`` / ``t0jit`` / ``notused`` are
zeroed in the HLSYN build because the HLSyn synthesiser owns the
glottal-source state instead of the SPC chip.
"""

from __future__ import annotations

# Re-export the shared dataclass so callers only need this module.
from dectalk.ph.spdef_chip import SpdChip

__all__ = ["SpdChip", "default_us_paul_spd"]

# ---------------------------------------------------------------------------
# US-English Paul-voice constants
#
# Source: ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf1.c`` lines 123--166
# (``const short paul_8[SPDEF]``, the HLSYN 8 kHz speaker definition).
#
# Every numeric default below corresponds to a single SPDEF slot in
# that array; the SPDEF -> SPD_CHIP mapping is documented in the
# module docstring.  The "C value" annotation lists the literal in
# p_us_vdf1.c so the trail back to the source is one ``rg`` away.
# ---------------------------------------------------------------------------

_PAUL_R4CB: int = 260  # B4 (C value: 260)
_PAUL_R4CC: int = 3400  # F4 (C value: 3400)
_PAUL_R5CB: int = 280  # B5 (C value: 280)
_PAUL_R5CC: int = 4300  # F5 (C value: 4300)
_PAUL_R4PB: int = 3400  # F7 (C value: 3400) -- frequency despite "pb" name
_PAUL_R5PB: int = 4800  # F8 (C value: 4800) -- frequency despite "pb" name
_PAUL_R5CA: int = 71  # G1 (C value: 71)
_PAUL_R4CA: int = 65  # G2 (C value: 65)
_PAUL_R3CA: int = 65  # G3 (C value: 65)
_PAUL_R2CA: int = 66  # G4 (C value: 66)
_PAUL_R1CA: int = 70  # LO (C value: 70)
_PAUL_AFGAIN: int = 55  # GF (C value: 55)
_PAUL_APGAIN: int = 55  # GH (C value: 55)
_PAUL_AZGAIN: int = 60  # GV (C value: 60)
_PAUL_RNPGAIN: int = 71  # GN (C value: 71)
# fnscale = 4096 because HS = 100 (nominal head size).  The chip-side
# ``fnscale`` is derived from HS at setspdef() time; for HS = 100 the
# resulting Q12 scaler is exactly 1.0 = 4096.
_PAUL_FNSCALE: int = 4096
_PAUL_OSGAIN: int = -1  # auto / pass-through (FP_VTM not defined in linux build)
_PAUL_SEX: int = 1  # MALE


def default_us_paul_spd() -> SpdChip:
    """Return a fresh :class:`SpdChip` initialised with US-Paul voice defaults.

    Values are extracted from ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf1.c``
    ``paul_8[SPDEF]`` -- the HLSYN 8 kHz speaker definition that the
    live synthesizer actually links against.

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
