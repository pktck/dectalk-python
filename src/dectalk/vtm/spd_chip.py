"""US-Paul SPD_CHIP defaults and factory.

Re-exports :class:`~dectalk.ph.spdef_chip.SpdChip` (the dataclass mirror
of the C ``SPD_CHIP`` struct from ``viphdefs.h``) and adds a factory that
returns the US-English Paul-voice defaults extracted from
``p_us_vdf.c`` / ``p_us_vdf1.c``.

SPD_CHIP field mapping from vtm_i.c ``read_speaker_definition()``:

    r4cb  -> B4  (resonator-4 cascade bandwidth)
    r4cc  -> F4  (resonator-4 cascade centre frequency)
    r5cb  -> B5  (resonator-5 cascade bandwidth)
    r5cc  -> F5  (resonator-5 cascade centre frequency)
    r4pb  -> F7  (resonator-4 parallel bandwidth proxy)
    r5pb  -> F8  (resonator-5 parallel bandwidth proxy)
    r5ca  -> G1  (cascade amplitude for resonator 5)
    r4ca  -> G2  (cascade amplitude for resonator 4)
    r3ca  -> G3  (cascade amplitude for resonator 3)
    r2ca  -> G4  (cascade amplitude for resonator 2)
    r1ca  -> LO  (output level)
    afgain  -> GF  (frication gain)
    rnpgain -> GN  (nasal-pole gain)
    azgain  -> GV  (glottal voicing gain)
    apgain  -> GH  (aspiration gain)
    fnscale -> Q12 formant-frequency scale (4096 = unity, HS=100)
    osgain  -> output-stage gain (-1 = auto)
    sex     -> 1 = MALE, 0 = FEMALE

Paul-voice field values are sourced from the ``paul[]`` SPDEF array
in ``p_us_vdf.c`` (11 kHz build) and the HLSYN-variant
``p_us_vdf1.c`` (for open-quotient / chink fields).
"""

from __future__ import annotations

# Re-export the shared dataclass so callers only need this module.
from dectalk.ph.spdef_chip import SpdChip

__all__ = ["SpdChip", "default_us_paul_spd"]

# ---------------------------------------------------------------------------
# US-English Paul-voice constants (from p_us_vdf.c paul[] SPDEF array)
# ---------------------------------------------------------------------------
# SEX = 1 (MALE), HS = 100 (nominal head size -> fnscale = 4096 = Q12 unity)
# F4=3300, B4=260, F5=3650, B5=330, F7=3350, F8=3850
# G1=71 (r5ca), G2=60 (r4ca), G3=50 (r3ca), G4=67 (r2ca), LO=81 (r1ca)
# GF=67 (afgain), GH=67 (apgain), GV=68 (azgain), GN=72 (rnpgain)
# osgain = -1 (pass-through / auto)
#
# nopen1 / nopen2 / aturb / t0jit / notused are 0 in the HLSYN build
# (HLSyn synthesiser handles glottal source; those fields go to the SPC
# chip only in the 11-kHz cascade path).

_PAUL_R4CB: int = 260  # B4
_PAUL_R4CC: int = 3300  # F4
_PAUL_R5CB: int = 330  # B5
_PAUL_R5CC: int = 3650  # F5
_PAUL_R4PB: int = 3350  # F7
_PAUL_R5PB: int = 3850  # F8
_PAUL_R5CA: int = 71  # G1
_PAUL_R4CA: int = 60  # G2
_PAUL_R3CA: int = 50  # G3
_PAUL_R2CA: int = 67  # G4
_PAUL_R1CA: int = 81  # LO
_PAUL_AFGAIN: int = 67  # GF
_PAUL_APGAIN: int = 67  # GH
_PAUL_AZGAIN: int = 68  # GV (voicing)
_PAUL_RNPGAIN: int = 72  # GN (nasal pole)
# fnscale = 4096 because HS = 100 (nominal head size).
# vtm_i.c computes: fnscal = (ZAPF * HS) / 100  where ZAPF = 6000 -> but the
# SPD_CHIP fnscale field itself is set to 4096 for Paul in p_us_vdf.c
# (Q12 integer unity = no frequency shift for a standard-sized head).
_PAUL_FNSCALE: int = 4096
_PAUL_OSGAIN: int = -1  # auto / pass-through
_PAUL_SEX: int = 1  # MALE


def default_us_paul_spd() -> SpdChip:
    """Return a fresh :class:`SpdChip` initialised with US-Paul voice defaults.

    These values are extracted from ``p_us_vdf.c`` (the 11 kHz SPDEF
    array for Paul) and cross-checked against
    ``read_speaker_definition()`` in ``vtm_i.c``.

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
