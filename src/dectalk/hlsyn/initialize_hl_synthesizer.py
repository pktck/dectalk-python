"""Initialize HLSyn speaker-definition constants.

Translated from ``src/dapi/src/hlsyn/inithl.c`` (``InitializeHLSynthesizer``).

Builds a fully-initialized :class:`~dectalk.ph.hl_speaker.HLSpeaker`
for either a male or female voice. The C function mutates all three of
``oldframe``, ``speaker``, and ``oldstate`` in place; here we return a
fresh speaker and freshly-initialized state/oldframe objects, keeping
the Python API side-effect-free.

The lookup tables (``anaTable``, ``anbTable``, ``f1cTable``, ``anK2Table``)
are stored as lists of :class:`~dectalk.ph.hlsyn_structs.TableRow` objects,
matching the C ``HLSpeaker`` struct layout.

``SetAlveolar`` and ``Atf3Setf2Range`` (the ``#if 0`` block in ``inithl.c``
lines 428-662) are not active in the production build and are therefore
not ported; ``speaker.alveolar`` is left as ``None``.
"""

from __future__ import annotations

from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState, TableRow

#: Constant from hlsyn.h: AGHIKLSOURCECUTOFF_VAL when FLAV_AGHISOURCECUTOFF_ON
#: is NOT defined (the default Linux US-English build).
_AGHIKLSOURCECUTOFF_VAL: float = 999999.0


def initialize_hl_synthesizer(  # noqa: PLR0915
    is_male: bool = True,
) -> tuple[HLSpeaker, HLFrame, HLState]:
    """Build and return fully-initialized HLSyn objects for one voice.

    Faithful translation of ``InitializeHLSynthesizer`` from
    ``src/dapi/src/hlsyn/inithl.c``.

    Args:
        is_male: ``True`` for a male voice (Perfect Paul defaults),
            ``False`` for a female voice (Betty defaults).

    Returns:
        A 3-tuple ``(speaker, oldframe, oldstate)``:

        - ``speaker``: :class:`~dectalk.ph.hl_speaker.HLSpeaker` with all
          constants initialized.
        - ``oldframe``: :class:`~dectalk.ph.hlsyn_structs.HLFrame` reset
          to zero (the "previous" frame sentinel).
        - ``oldstate``: :class:`~dectalk.ph.hlsyn_structs.HLState` reset
          to initial values.
    """
    speaker = HLSpeaker()

    # inithl.c lines 75-98: vocal-tract geometry.
    speaker.Val = 60.0 if is_male else 45.0
    speaker.Lc_al = 0.5
    speaker.HelmholtzZeroAreaFrequency = 180.0
    speaker.Vab = 60.0 if is_male else 45.0
    speaker.Lc_ab = 1.0
    speaker.f1Min = 300.0
    speaker.f1Max = 500.0 if is_male else 650.0
    speaker.f2RetroflexMax = 1400.0 if is_male else 1600.0
    speaker.f3RetroflexMax = 1800.0 if is_male else 2200.0
    speaker.f2LateralMax = 1300.0 if is_male else 1400.0
    speaker.f3LateralMin = 2600.0 if is_male else 2800.0
    speaker.Kacl = 25.0
    speaker.aclFreq = 400.0 if is_male else 450.0
    speaker.Vacd = 50.0 if is_male else 40.0
    speaker.Lc_acd = 4.0 if is_male else 3.5
    speaker.acdMax = 100.0
    speaker.acd_f1Break = 540.0 if is_male else 650.0
    speaker.KHi = 12.5 if is_male else 8.8
    speaker.f1HiShift = 1180.0 if is_male else 1280.0
    speaker.fno = 500.0 if is_male else 550.0

    # inithl.c lines 132-133: formant breakpoints.
    speaker.fm_f1BreakPoint = 250.0
    speaker.BNZ_f1BreakPoint = 700.0

    # inithl.c lines 162-163: nasal bandwidth thresholds.
    speaker.BNP_B1_anLow = 10.0
    speaker.BNP_B1_anHigh = 20.0

    # inithl.c lines 168-181: an,a table.
    speaker.anaTable = [
        TableRow(Column1=10.0, Column2=0.00200),
        TableRow(Column1=15.0, Column2=0.00045),
        TableRow(Column1=20.0, Column2=0.00032),
        TableRow(Column1=30.0, Column2=0.00025),
        TableRow(Column1=50.0, Column2=0.00020),
        TableRow(Column1=80.0, Column2=0.00014),
    ]

    # inithl.c lines 186-199: an,b table.
    speaker.anbTable = [
        TableRow(Column1=10.0, Column2=0.00006),
        TableRow(Column1=15.0, Column2=0.00008),
        TableRow(Column1=20.0, Column2=0.00010),
        TableRow(Column1=30.0, Column2=0.00015),
        TableRow(Column1=50.0, Column2=0.00020),
        TableRow(Column1=80.0, Column2=0.00014),
    ]

    # inithl.c lines 203-219: f1,c table.
    speaker.f1cTable = [
        TableRow(Column1=180.0, Column2=0.00040),
        TableRow(Column1=200.0, Column2=0.00032),
        TableRow(Column1=300.0, Column2=0.00026),
        TableRow(Column1=400.0, Column2=0.00024),
        TableRow(Column1=500.0, Column2=0.00022),
        TableRow(Column1=600.0, Column2=0.00021),
        TableRow(Column1=700.0, Column2=0.00021),
    ]

    # inithl.c line 221: palatal break.
    speaker.fp_f2BreakPoint = 1000.0 if is_male else 1100.0

    # inithl.c lines 226-261: an,K2 table (17 rows).
    _ank2_an = [
        0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0,
        40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0,
    ]
    _ank2_k2 = [
        0.0, 1.8, 3.5, 4.8, 6.0, 7.3, 8.5, 9.7,
        10.8, 11.7, 12.5, 13.8, 14.0, 14.6, 15.1, 15.6, 16.1,
    ]
    speaker.anK2Table = [
        TableRow(Column1=an, Column2=k2)
        for an, k2 in zip(_ank2_an, _ank2_k2, strict=True)
    ]

    # inithl.c line 263.
    speaker.PharangealArea = 3.0

    # inithl.c lines 265-282.
    speaker.Cwm = 0.001
    speaker.Rw = 10.0
    speaker.Psm = 8.0 if is_male else 6.5
    speaker.Cgm = 8.0e-6
    speaker.Lg = 1.0 if is_male else 0.7
    speaker.KCw = 1.0
    speaker.KCg = 0.34
    speaker.NewtonInterpTimeStep = 100.0e-6
    speaker.UpdateInterval = 5.0e-3

    # inithl.c lines 281-290: fricative filter parameters.
    speaker.LabialAB = 55.0
    speaker.PalVelarA2F = 50.0
    speaker.PalVelarA5F = 45.0
    speaker.PalVelarA3F = 50.0
    speaker.PalVelar_f2Offset = 1950.0 if is_male else 2200.0
    speaker.PalVelar_f2Overf3_Slope = 0.0
    speaker.LateralA3F = 45.0
    speaker.RetroflexA3F = 50.0

    # inithl.c lines 300-304: parallel fricative bandwidths.
    speaker.B2F = 250.0
    speaker.B3F = 320.0
    speaker.B4F = 350.0
    speaker.B5F = 500.0

    # inithl.c lines 306-319: glottal-area source parameters.
    speaker.agm = 4.0 if is_male else 3.0
    speaker.agAVModalOffsetMax = 11.0 if is_male else 9.0
    speaker.agAVModalOffsetOnOff = 7.0 if is_male else 6.0
    speaker.agMin = 1.0
    speaker.agHiKLSourceCutoff = _AGHIKLSOURCECUTOFF_VAL
    speaker.AVPressureThreshold = 3.5
    speaker.KdPTdc = 0.03
    speaker.Kv = 33.0
    speaker.KdAV0 = 200.0 if is_male else 220.0
    speaker.KdAV = 100.0 if is_male else 120.0
    speaker.KdAV1 = 400.0 if is_male else 420.0
    speaker.Ka = 42.0
    speaker.Kf = 40.0
    speaker.AFInterpTimeStep = 0.001
    speaker.AFThreshold = 35.0

    # inithl.c lines 321-336: source shape / spectral tilt.
    speaker.OQm = 50.0 if is_male else 65.0
    speaker.KOQ = 3.3 if is_male else 3.96
    speaker.OQMax = 99.0
    speaker.OQMin = 0.0
    speaker.TLBreakArea = 20.0
    speaker.KTL = 1.5 if is_male else 1.8
    speaker.TLm = 5.0 if is_male else 10.0
    speaker.SFromf4 = 0.29
    speaker.SDefault = 1000.0 if is_male else 1150.0
    speaker.PctSfordBTL = 0.10
    speaker.dBTLforPctS = 4.0
    speaker.TLMax = 41.0
    speaker.TLMin = 0.0

    # inithl.c lines 337-341.
    speaker.KDI = 15.0
    speaker.agDIMin = 1.0

    # inithl.c lines 340-341.
    speaker.KdF = 20.0
    speaker.F1T = 600.0

    # inithl.c lines 348-357: modal bandwidths.
    speaker.B1m = 80.0
    speaker.B2m = 90.0
    speaker.B3m = 150.0
    speaker.B4m = 350.0 if is_male else 400.0
    speaker.B5m = 500.0 if is_male else 600.0
    speaker.KB3 = 4.0
    speaker.KB4 = 2.0
    speaker.KB5 = 2.0

    speaker.F5 = 4500.0 if is_male else 5200.0

    # inithl.c lines 366-370.
    speaker.A6f = 0.0
    speaker.F6 = 4990.0
    speaker.B6F = 1500.0

    # inithl.c lines 371-381.
    speaker.Kdf0dc = 3.0
    speaker.Kpd = 30.0
    speaker.Kf1 = 5.0e-4 if is_male else 4.6e-4
    speaker.f1_neutral = 500.0 if is_male else 590.0
    speaker.f0_vowelshift_f1_break = 250.0
    speaker.Lt = 12.0 if is_male else 11.0
    speaker.At = 2.5 if is_male else 2.0
    speaker.Lvg = 0.4 if is_male else 0.3
    speaker.Lv = 17.0 if is_male else 15.0
    speaker.Av = 3.5 if is_male else 3.0
    speaker.Lhp = 0.3 if is_male else 0.2

    # inithl.c lines 387-425: initialize oldstate.
    oldstate = HLState()
    oldstate.acl = 0.0
    oldstate.acd = 0.0
    oldstate.loc = 0
    oldstate.acx = 0.0
    oldstate.agx = 0.0
    oldstate.Pm = 0.0
    oldstate.Pcw = 0.0
    oldstate.Ug = 0.0
    oldstate.Uacx = 0.0
    oldstate.Un = 0.0
    oldstate.Uw = 0.0
    oldstate.f1c = 0.0
    oldstate.f1x = 0.0
    oldstate.b1x = 0.0
    oldstate.Cw = speaker.Cwm
    oldstate.Cg = speaker.Cgm
    oldstate.agf = 0.0

    # inithl.c lines 412-425: initialize oldframe.
    oldframe = HLFrame()
    oldframe.ag = 0.0
    oldframe.al = 0.0
    oldframe.ab = 0.0
    oldframe.an = 0.0
    oldframe.ue = 0.0
    oldframe.f0 = 0.0
    oldframe.f1 = 0.0
    oldframe.f2 = 0.0
    oldframe.f3 = 0.0
    oldframe.f4 = 0.0
    oldframe.ps = 0.0
    oldframe.dc = 0.0
    oldframe.ap = 0.0

    return speaker, oldframe, oldstate


# Module-level singleton for the most common case (US-English male voice).
_DEFAULT_MALE_SPEAKER, _DEFAULT_MALE_OLDFRAME, _DEFAULT_MALE_OLDSTATE = (
    initialize_hl_synthesizer(is_male=True)
)


def default_male_speaker() -> HLSpeaker:
    """Return the singleton default male :class:`~dectalk.ph.hl_speaker.HLSpeaker`.

    Constructed once at import time from the same constants as
    ``InitializeHLSynthesizer(..., IsMale=1)`` in ``inithl.c``.
    Callers that need fresh state (e.g. tests) should call
    :func:`initialize_hl_synthesizer` instead.
    """
    return _DEFAULT_MALE_SPEAKER


__all__ = [
    "default_male_speaker",
    "initialize_hl_synthesizer",
]
