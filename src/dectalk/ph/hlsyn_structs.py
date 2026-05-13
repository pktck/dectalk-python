"""HLSyn frame / state / lookup structs from hlsynapi.h.

Translated from ``src/dapi/src/ph/hlsynapi.h`` lines 31-119.

Four small floating-point structs the HLSyn (high-level Klatt)
front-end uses:

- :class:`HLFrame` — one frame's worth of HLSyn parameters (areas,
  flows, formants, pressures). The HLSyn solver reads these as
  inputs and outputs a corresponding :class:`HLState`.
- :class:`HLState` — running-state quantities the solver maintains
  cycle-to-cycle (mouth pressure, glottal flow, F1-with-constriction).
- :class:`TableRow` — two-float lookup row used by the six HLSyn
  voice-definition tables (``anfn``, ``f1lovera``, ``ana``, ``anb``,
  ``f1c``, ``ank2``). The C source documents: *the known element
  is Column1, the unknown is Column2* — table search starts from
  Column1 and interpolates Column2.
- :class:`FricativeGains` — 5-component gain vector applied to the
  five parallel fricative resonators (A2f, A3f, A4f, A5f, Ab).

All fields are floats (Q14/Q15 fixed-point in the C inner loops
becomes plain Python float for parity).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HLFrame:
    """One HLSyn frame — areas / flows / formants / pressures."""

    atb: float = 0.0
    """Tongue-body area in mm^2 (NEW_VTM only — present unconditionally here)."""

    place: int = 0
    """Place-of-articulation marker (mm^2 scale)."""

    ag: float = 0.0
    """Glottal area in mm^2."""

    al: float = 0.0
    """Liquid-contraction area in mm^2."""

    ab: float = 0.0
    """Lip-bypass area in mm^2."""

    an: float = 0.0
    """Nasal area in mm^2."""

    ue: float = 0.0
    """Velar elevator force in cm^3/s."""

    f0: float = 0.0
    """Fundamental frequency in deciHz (Hz times 10)."""

    f1: float = 0.0
    """First formant frequency in Hz."""

    f2: float = 0.0
    """Second formant frequency in Hz."""

    f3: float = 0.0
    """Third formant frequency in Hz."""

    f4: float = 0.0
    """Fourth formant frequency in Hz."""

    ps: float = 0.0
    """Subglottal pressure in cm H2O."""

    dc: float = 0.0
    """DC duty cycle in %."""

    ap: float = 0.0
    """Aspiration area in mm^2."""


@dataclass(slots=True)
class HLState:
    """HLSyn running-state quantities the solver maintains cycle-to-cycle."""

    acl: float = 0.0
    """Area of liquid contraction (mm^2)."""

    acd: float = 0.0
    """Area of dorsum contraction (mm^2)."""

    loc: int = 0
    """Location of smallest contraction."""

    acx: float = 0.0
    """Area of smallest contraction (mm^2)."""

    agx: float = 0.0
    """Area of tracheal-adjusted glottal contraction (mm^2)."""

    Pm: float = 0.0
    """Pressure in the mouth (dynes/cm^2)."""

    Pcw: float = 0.0
    """Pressure across the wall capacitance (dynes/cm^2)."""

    Ug: float = 0.0
    """Glottal flow (cm^3/s)."""

    Uacx: float = 0.0
    """Flow across constriction acx (cm^3/s)."""

    Un: float = 0.0
    """Flow into the nose (cm^3/s)."""

    Uw: float = 0.0
    """Flow into the parallel Rw, Cw branch (wall, cm^3/s)."""

    f1c: float = 0.0
    """F1 adjusted by constrictions (Hz)."""

    f1x: float = 0.0
    """F1 adjusted by constrictions and nose (Hz)."""

    b1x: float = 0.0
    """B1 adjusted by nose (Hz)."""

    Cw: float = 0.0
    """Compliance of the pharyngeal walls."""

    Cg: float = 0.0
    """Compliance of the glottis."""

    agf: float = 0.0
    """Area of the glottis for calculating flow."""


@dataclass(slots=True)
class TableRow:
    """Two-float lookup row for HLSyn voice-definition tables.

    Per the C source's note: ``Column1`` is the known (key) value,
    ``Column2`` is the unknown (interpolated) value. Table search
    walks Column1 and the matching row's Column2 is returned (or
    interpolated between neighbouring rows).
    """

    Column1: float = 0.0
    """The known / key value to search by."""

    Column2: float = 0.0
    """The unknown / interpolated value."""


@dataclass(slots=True)
class FricativeGains:
    """5-component gain vector applied to parallel fricative resonators."""

    A2f: float = 0.0
    """Gain on parallel-formant 2 fricative resonator."""

    A3f: float = 0.0
    """Gain on parallel-formant 3 fricative resonator."""

    A4f: float = 0.0
    """Gain on parallel-formant 4 fricative resonator."""

    A5f: float = 0.0
    """Gain on parallel-formant 5 fricative resonator."""

    Ab: float = 0.0
    """Bypass gain."""


__all__ = [
    "FricativeGains",
    "HLFrame",
    "HLState",
    "TableRow",
]
