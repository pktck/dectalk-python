"""Klatt-frame parameter array indices from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h`` lines 491-520. Two
parallel index sets share this module:

- **PH/VTM input parameters** (:data:`F0`..:data:`AREAN`):
  offsets into the ``param[]`` array that the PH module fills as
  it walks a phoneme stream. ``F0..FZ`` are the formant freqs,
  ``B1..B3`` the bandwidths, ``AV/AP`` the voicing/aspiration
  amplitudes, ``A2..A6/AB`` the parallel resonator amplitudes,
  ``TILT`` the spectral tilt, and ``AREAB/AREAL/AREAG/AREAN`` the
  HLSyn area parameters.
- **SPC frame data offsets** (:data:`OUT_AP`..:data:`OUT_PH2`):
  parallel order the data takes when packed for transmission to
  the SPC chip. Note ``OUT_F1`` and ``F1`` differ — the SPC frame
  starts with aspiration, not F0.

Both sets are loop-bearing in the C code; "Don't move any of
these or you will be sorry" — the comment from the header
applies to the Python port too.
"""

from __future__ import annotations

from typing import Final

# -- "param[]" array indices (PH side) ------------------------------------

F0: Final[int] = 0
"""Fundamental-frequency index."""
F1: Final[int] = 1
"""First-formant index."""
F2: Final[int] = 2
"""Second-formant index."""
F3: Final[int] = 3
"""Third-formant index."""
FZ: Final[int] = 4
"""Nasal-zero formant index."""
B1: Final[int] = 5
"""First-formant bandwidth index."""
B2: Final[int] = 6
"""Second-formant bandwidth index."""
B3: Final[int] = 7
"""Third-formant bandwidth index."""
AV: Final[int] = 8
"""Voicing amplitude index."""
AP: Final[int] = 9
"""Aspiration amplitude index."""
A2: Final[int] = 10
"""Parallel A2 amplitude index."""
A3: Final[int] = 11
"""Parallel A3 amplitude index."""
A4: Final[int] = 12
"""Parallel A4 amplitude index."""
A5: Final[int] = 13
"""Parallel A5 amplitude index."""
A6: Final[int] = 14
"""Parallel A6 amplitude index."""
AB: Final[int] = 15
"""Bypass amplitude index."""
TILT: Final[int] = 16
"""Spectral tilt index."""
AREAB: Final[int] = 17
"""HLSyn back-cavity area index."""
AREAL: Final[int] = 18
"""HLSyn liquid-contraction area index."""
AREAG: Final[int] = 19
"""HLSyn glottal area index."""
AREAN: Final[int] = 20
"""HLSyn nasal area index."""

# -- "param[]" indices added by NEW_VTM build ------------------------------

PRESS: Final[int] = 21
"""Subglottal pressure (NEW_VTM build)."""
TONGUEBODY: Final[int] = 22
"""Tongue-body cross-sectional area (NEW_VTM build)."""
CHINK: Final[int] = 23
"""Glottal chink area (NEW_VTM build)."""
UEL: Final[int] = 24
"""Velar elevator force (NEW_VTM build)."""
DC: Final[int] = 35
"""DC offset (NEW_VTM build) — non-contiguous with the others."""
OQU: Final[int] = 36
"""Open-quotient utterance scaler (NEW_VTM build)."""
BRST: Final[int] = 37
"""Burst strength (NEW_VTM build)."""

# -- SPC frame output data offsets (OUT_*) --------------------------------

OUT_AP: Final[int] = 0
"""SPC frame offset: aspiration amplitude."""
OUT_F1: Final[int] = 1
"""SPC frame offset: F1."""
OUT_A2: Final[int] = 2
"""SPC frame offset: A2."""
OUT_A3: Final[int] = 3
"""SPC frame offset: A3."""
OUT_A4: Final[int] = 4
"""SPC frame offset: A4."""
OUT_A5: Final[int] = 5
"""SPC frame offset: A5."""
OUT_A6: Final[int] = 6
"""SPC frame offset: A6."""
OUT_AB: Final[int] = 7
"""SPC frame offset: AB (bypass)."""
OUT_TLT: Final[int] = 8
"""SPC frame offset: spectral tilt."""
OUT_T0: Final[int] = 9
"""SPC frame offset: fundamental period."""
OUT_AV: Final[int] = 10
"""SPC frame offset: voicing amplitude."""
OUT_F2: Final[int] = 11
"""SPC frame offset: F2."""
OUT_F3: Final[int] = 12
"""SPC frame offset: F3."""
OUT_FZ: Final[int] = 13
"""SPC frame offset: nasal zero."""
OUT_B1: Final[int] = 14
"""SPC frame offset: B1."""
OUT_B2: Final[int] = 15
"""SPC frame offset: B2."""
OUT_B3: Final[int] = 16
"""SPC frame offset: B3."""
OUT_PH: Final[int] = 17
"""SPC frame offset: current-phoneme code."""
OUT_DU: Final[int] = 18
"""SPC frame offset: duration."""
OUT_PH2: Final[int] = 19
"""SPC frame offset: secondary phoneme code."""

# -- SPC frame offsets added by NEW_VTM build ------------------------------

OUT_FNP: Final[int] = 20
"""SPC frame offset: nasal-pole frequency (NEW_VTM)."""
OUT_GF: Final[int] = 21
"""SPC frame offset: glottal force (NEW_VTM)."""
OUT_F4: Final[int] = 22
"""SPC frame offset: F4 (NEW_VTM)."""
OUT_SEX: Final[int] = 23
"""SPC frame offset: speaker sex (NEW_VTM)."""
OUT_DP: Final[int] = 24
"""SPC frame offset: differential pressure (NEW_VTM)."""
OUT_AG: Final[int] = 25
"""SPC frame offset: glottal area (NEW_VTM)."""
OUT_AL: Final[int] = 26
"""SPC frame offset: liquid contraction area (NEW_VTM)."""
OUT_AN: Final[int] = 27
"""SPC frame offset: nasal area (NEW_VTM)."""
OUT_ABLADE: Final[int] = 28
"""SPC frame offset: tongue-blade area (NEW_VTM)."""
OUT_PS: Final[int] = 29
"""SPC frame offset: subglottal pressure (NEW_VTM)."""
OUT_CNK: Final[int] = 30
"""SPC frame offset: glottal chink (NEW_VTM)."""
OUT_DC: Final[int] = 31
"""SPC frame offset: DC offset (NEW_VTM)."""
OUT_UE: Final[int] = 32
"""SPC frame offset: velar elevator (NEW_VTM)."""
OUT_OQ: Final[int] = 33
"""SPC frame offset: open quotient (NEW_VTM)."""
OUT_BNP: Final[int] = 34
"""SPC frame offset: nasal-pole bandwidth (NEW_VTM)."""
OUT_BRST: Final[int] = 35
"""SPC frame offset: burst strength (NEW_VTM)."""
OUT_ATB: Final[int] = 36
"""SPC frame offset: tongue-body area (NEW_VTM)."""
OUT_PLACE: Final[int] = 37
"""SPC frame offset: place-of-articulation marker (NEW_VTM)."""


__all__ = [
    "A2",
    "A3",
    "A4",
    "A5",
    "A6",
    "AB",
    "AP",
    "AREAB",
    "AREAG",
    "AREAL",
    "AREAN",
    "AV",
    "B1",
    "B2",
    "B3",
    "BRST",
    "CHINK",
    "DC",
    "F0",
    "F1",
    "F2",
    "F3",
    "FZ",
    "OQU",
    "OUT_A2",
    "OUT_A3",
    "OUT_A4",
    "OUT_A5",
    "OUT_A6",
    "OUT_AB",
    "OUT_ABLADE",
    "OUT_AG",
    "OUT_AL",
    "OUT_AN",
    "OUT_AP",
    "OUT_ATB",
    "OUT_AV",
    "OUT_B1",
    "OUT_B2",
    "OUT_B3",
    "OUT_BNP",
    "OUT_BRST",
    "OUT_CNK",
    "OUT_DC",
    "OUT_DP",
    "OUT_DU",
    "OUT_F1",
    "OUT_F2",
    "OUT_F3",
    "OUT_F4",
    "OUT_FNP",
    "OUT_FZ",
    "OUT_GF",
    "OUT_OQ",
    "OUT_PH",
    "OUT_PH2",
    "OUT_PLACE",
    "OUT_PS",
    "OUT_SEX",
    "OUT_T0",
    "OUT_TLT",
    "OUT_UE",
    "PRESS",
    "TILT",
    "TONGUEBODY",
    "UEL",
]
