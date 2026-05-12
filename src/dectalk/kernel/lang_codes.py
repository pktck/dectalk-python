"""Language ID codes from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. These are the
8-bit language identifiers the kernel uses internally — distinct
from the public API ``TTS_AMERICAN_ENGLISH`` etc. codes in
:mod:`dectalk.api.ttsapi_constants`.

- :data:`LANG_english` (0) is the default US English ID.
- :data:`LANG_british` (5) is UK English.
- :data:`LANG_none` (0xFFFF) marks an empty language slot.
- :data:`LANG_lts_ready` (0x1) is a bit flag (not a language ID)
  used by the kernel to signal LTS readiness.
"""

from __future__ import annotations

from typing import Final

LANG_english: Final[int] = 0x0000
"""US English (default)."""

LANG_french: Final[int] = 0x0001
"""French."""

LANG_german: Final[int] = 0x0002
"""German."""

LANG_spanish: Final[int] = 0x0003
"""Spanish (Castilian)."""

LANG_japanese: Final[int] = 0x0004
"""Japanese."""

LANG_british: Final[int] = 0x0005
"""British English."""

LANG_latin_american: Final[int] = 0x0006
"""Latin American Spanish."""

LANG_italian: Final[int] = 0x0007
"""Italian."""

LANG_none: Final[int] = 0xFFFF
"""Sentinel: no language assigned to this slot."""

LANG_lts_ready: Final[int] = 0x1
"""Bit flag (not a language ID): LTS pipeline ready signal."""

LANG_ph_ready: Final[int] = 0x2
"""Bit flag: PH pipeline ready signal."""

LANG_map_ready: Final[int] = 0x4
"""Bit flag: language-map tables ready signal."""

LANG_tables_ready: Final[int] = 0x4
"""Bit flag: language tables ready (alias of :data:`LANG_map_ready`)."""

LANG_both_ready: Final[int] = 0x7
"""Composite flag: all three ready signals set (LTS + PH + map)."""


__all__ = [
    "LANG_both_ready",
    "LANG_british",
    "LANG_english",
    "LANG_french",
    "LANG_german",
    "LANG_italian",
    "LANG_japanese",
    "LANG_latin_american",
    "LANG_lts_ready",
    "LANG_map_ready",
    "LANG_none",
    "LANG_ph_ready",
    "LANG_spanish",
    "LANG_tables_ready",
]
