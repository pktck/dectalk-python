# ruff: noqa: N815 — preserve C-source mixedCase HLSyn field names
"""HLSyn per-voice speaker-definition struct from hlsynapi.h.

Translated from ``src/dapi/src/ph/hlsynapi.h`` lines 148-294.

``HLSpeaker`` is the 107-field per-voice HLSyn parameterisation —
the floating-point voice-definition the HLSyn solver consumes.
Each loaded speaker has one of these, and the engine swaps the
active ``HLSpeaker *`` when ``[:dv <voice>]`` selects a voice.

Field groups:

- Vocal-tract geometry: Val, Lc_al, Lc_ab, Vacd, Lc_acd, ...
- Formant ranges: f1Min, f1Max, f2RetroflexMax, f3RetroflexMax
- Lookup tables: anaTable, anbTable, f1cTable, anK2Table
- Source params: AVPressureThreshold, agm, agMin, OQm, OQMin, OQMax
- Filter coefficients: B1m..B5m, KB3..KB5, F5, F6
- Fricative bypass: alveolar[] grid, A6f, A2/3/4/5/F resonator gains

All float fields default to 0.0; ``TableRow`` / ``FricativeGains``
sub-struct fields default to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HLSpeaker:
    """HLSyn per-voice speaker definition (107 floats + 4 tables + 1 fric vec)."""

    Val: float = 0.0
    Lc_al: float = 0.0
    HelmholtzZeroAreaFrequency: float = 0.0
    Vab: float = 0.0
    Lc_ab: float = 0.0
    f1Min: float = 0.0
    f1Max: float = 0.0
    f2RetroflexMax: float = 0.0
    f3RetroflexMax: float = 0.0
    f2LateralMax: float = 0.0
    f3LateralMin: float = 0.0
    Kacl: float = 0.0
    aclFreq: float = 0.0
    Vacd: float = 0.0
    Lc_acd: float = 0.0
    acdMax: float = 0.0
    acd_f1Break: float = 0.0
    KHi: float = 0.0
    f1HiShift: float = 0.0
    fno: float = 0.0
    fm_f1BreakPoint: float = 0.0
    BNZ_f1BreakPoint: float = 0.0
    BNP_B1_anLow: float = 0.0
    BNP_B1_anHigh: float = 0.0
    anaTable: object | None = None  # TableRow[MAXANA]
    anbTable: object | None = None  # TableRow[MAXANB]
    f1cTable: object | None = None  # TableRow[MAXF1C]
    fp_f2BreakPoint: float = 0.0
    anK2Table: object | None = None  # TableRow[MAXANK2]
    PharangealArea: float = 0.0
    Cwm: float = 0.0
    Rw: float = 0.0
    Psm: float = 0.0
    Cgm: float = 0.0
    Lg: float = 0.0
    NewtonInterpTimeStep: float = 0.0
    UpdateInterval: float = 0.0
    LabialAB: float = 0.0
    PalVelarA2F: float = 0.0
    PalVelarA5F: float = 0.0
    PalVelarA3F: float = 0.0
    PalVelar_f2Offset: float = 0.0
    PalVelar_f2Overf3_Slope: float = 0.0
    RetroflexA3F: float = 0.0
    LateralA3F: float = 0.0
    alveolar: object | None = None  # FricativeGains[ALV_F2_POINTS][ALV_F3_POINTS]
    B2F: float = 0.0
    B3F: float = 0.0
    B4F: float = 0.0
    B5F: float = 0.0
    agm: float = 0.0
    agAVModalOffsetMax: float = 0.0
    agAVModalOffsetOnOff: float = 0.0
    agMin: float = 0.0
    agHiKLSourceCutoff: float = 0.0
    AVPressureThreshold: float = 0.0
    Kv: float = 0.0
    KdAV0: float = 0.0
    KdAV: float = 0.0
    KdAV1: float = 0.0
    Ka: float = 0.0
    Kf: float = 0.0
    AFInterpTimeStep: float = 0.0
    AFThreshold: float = 0.0
    OQm: float = 0.0
    KOQ: float = 0.0
    OQMax: float = 0.0
    OQMin: float = 0.0
    TLBreakArea: float = 0.0
    KTL: float = 0.0
    TLm: float = 0.0
    SFromf4: float = 0.0
    SDefault: float = 0.0
    PctSfordBTL: float = 0.0
    dBTLforPctS: float = 0.0
    TLMax: float = 0.0
    TLMin: float = 0.0
    agDIMin: float = 0.0
    KDI: float = 0.0
    KdF: float = 0.0
    F1T: float = 0.0
    B1m: float = 0.0
    B2m: float = 0.0
    B3m: float = 0.0
    B4m: float = 0.0
    B5m: float = 0.0
    KB3: float = 0.0
    KB4: float = 0.0
    KB5: float = 0.0
    F5: float = 0.0
    A6f: float = 0.0
    F6: float = 0.0
    B6F: float = 0.0
    KCw: float = 0.0
    KCg: float = 0.0
    Kdf0dc: float = 0.0
    Kpd: float = 0.0
    Kf1: float = 0.0
    f1_neutral: float = 0.0
    KdPTdc: float = 0.0
    f0_vowelshift_f1_break: float = 0.0
    Lt: float = 0.0
    At: float = 0.0
    Lvg: float = 0.0
    Lv: float = 0.0
    Av: float = 0.0
    Lhp: float = 0.0


__all__ = ["HLSpeaker"]
