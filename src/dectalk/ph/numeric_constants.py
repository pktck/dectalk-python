"""Numeric tuning constants from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h``. Small numeric helpers
the PH module uses for fixed-point math, voice-block sizing, and
overload guards:

- :data:`FRAC_ONE` / :data:`FRAC_HALF` / :data:`FRAC_3_4THS` /
  :data:`FRAC_3_HALVES` — Q14 fixed-point constants (1.0 = 16384).
- :data:`F0` / :data:`F1` / :data:`F2` / :data:`F3` / :data:`FZ` —
  parameter indices used by ``us_gettar`` to dispatch on
  ``pDphsettar->np`` (0..4 = F0..FZ).
- :data:`F2max` / :data:`F3max` — F2/F3 frequency caps to keep the
  signal-processing chip (SPC) from overloading.
- :data:`MALE` / :data:`FEMALE` — values of ``pDph_t->malfem``.
- :data:`VOICE_PARS` / :data:`SYNC_PARS` — fixed sizes used by
  table-walking loops.
"""

from __future__ import annotations

from typing import Final

# -- Q14 fixed-point constants ----------------------------------------------

FRAC_ONE: Final[int] = 16384
"""Q14 fixed-point representation of 1.0."""

FRAC_HALF: Final[int] = 8192
"""Q14 fixed-point representation of 0.5."""

FRAC_3_4THS: Final[int] = 12288
"""Q14 fixed-point representation of 0.75."""

FRAC_3_HALVES: Final[int] = 24567
"""Q14 fixed-point representation of 1.5 (the C source uses 24567,
not the mathematically-clean 24576 — copied verbatim)."""

# -- Parameter index constants ----------------------------------------------

F0: Final[int] = 0
"""Parameter index for F0 (pitch)."""

F1: Final[int] = 1
"""Parameter index for first formant frequency."""

F2: Final[int] = 2
"""Parameter index for second formant frequency."""

F3: Final[int] = 3
"""Parameter index for third formant frequency."""

FZ: Final[int] = 4
"""Parameter index for the nasal zero frequency."""

# -- Formant overload caps --------------------------------------------------

F2max: Final[int] = 2500
"""F2 frequency cap to keep the SPC from overloading (Hz)."""

F3max: Final[int] = 3500
"""F3 frequency cap (Hz)."""

# -- Voice-sex codes --------------------------------------------------------

MALE: Final[int] = 1
"""Voice sex: male — value of ``pDph_t->malfem``."""

FEMALE: Final[int] = 0
"""Voice sex: female."""

# -- Voice-block parameter counts -------------------------------------------

VOICE_PARS: Final[int] = 40
"""Voice-block parameter count (BATS#667 update; older builds use 21)."""

SYNC_PARS: Final[int] = 0
"""Sync-parameter count — DECtalk has no sync parameters."""

MAX_SPEAKERS: Final[int] = 10
"""Maximum number of voice slots in the per-PH speaker table (ph_data.h)."""

NSAMP_FRAME: Final[int] = 71
"""Samples per Klatt output frame at 11 kHz (the Linux/HLSYN sample rate).
The 10 kHz variant uses 64 samples; the Python port is built for 11 kHz."""

NPHON_MAX: Final[int] = 300
"""Maximum phone-array length (size of ``pDph_t->phonemes[]`` and friends).
Linux build value; the ARM7 build uses 150 and the TOMBUCHLER build 2800."""

INDEX_PARS: Final[int] = 2
"""Number of words in an index-mark block."""

TONE_PARS: Final[int] = 5
"""Number of words in a tone packet."""

SPDEF_PARS: Final[int] = 40  # = SPDEF + 1; SPDEF == 39
"""Number of words in a speaker definition (= SPDEF + 1)."""

MALLINE: Final[int] = 9
"""Number of parameters per line of locus code in ``p_us_rom.c``."""


__all__ = [
    "F0",
    "F1",
    "F2",
    "F3",
    "FEMALE",
    "FRAC_3_4THS",
    "FRAC_3_HALVES",
    "FRAC_HALF",
    "FRAC_ONE",
    "FZ",
    "INDEX_PARS",
    "MALE",
    "MALLINE",
    "MAX_SPEAKERS",
    "NPHON_MAX",
    "NSAMP_FRAME",
    "SPDEF_PARS",
    "SYNC_PARS",
    "TONE_PARS",
    "VOICE_PARS",
    "F2max",
    "F3max",
]
