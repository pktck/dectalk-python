"""Per-language allophone counts from l_all_ph.h.

Translated from ``src/dapi/src/include/l_all_ph.h`` lines 339-361
— the ``*_TOT_ALLOPHONES`` and ``MAX_PHONES`` / ``NOVALID``
constants that bound each language's phoneme inventory.

US English has multiple values depending on which voice-ROM
build is in scope:

- ``VOICE_ROM_DTC_03_03JAN89`` / ``VOICE_ROM_DECTALK_41``: 56
- ``VOICE_ROM_DECTALK_43`` / ``VOICE_ROM_DECTALK_1996M_43F``: 57
- ``VOICE_ROM_1996`` / ``_1997`` / ``BETA5``: 71

The Python port uses 71 (the modern Linux build), which already
appears in :mod:`dectalk.include.phoneme_codes` as
:data:`US_TOT_ALLOPHONES`.
"""

from __future__ import annotations

from typing import Final

UK_TOT_ALLOPHONES: Final[int] = 57
"""Number of UK English allophones."""

GR_TOT_ALLOPHONES: Final[int] = 62
"""Number of German allophones."""

LA_TOT_ALLOPHONES: Final[int] = 39
"""Number of Latin American Spanish allophones (last allophone + 1)."""

SP_TOT_ALLOPHONES: Final[int] = 39
"""Number of Castilian Spanish allophones (last allophone + 1)."""

FR_TOT_ALLOPHONES: Final[int] = 40
"""Number of French allophones."""

NOVALID: Final[int] = 39
"""Sentinel used by the LTS parser meaning "no valid phoneme" —
equals :data:`SP_TOT_ALLOPHONES`."""

MAX_PHONES: Final[int] = 99
"""Maximum phone slot index — total room for phones in the worst-case
language (forces the upper bound across builds)."""


__all__ = [
    "FR_TOT_ALLOPHONES",
    "GR_TOT_ALLOPHONES",
    "LA_TOT_ALLOPHONES",
    "MAX_PHONES",
    "NOVALID",
    "SP_TOT_ALLOPHONES",
    "UK_TOT_ALLOPHONES",
]
