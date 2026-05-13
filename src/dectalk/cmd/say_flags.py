"""`SAY_*` granularity + `R2_*` reply-class codes from esc.h.

Translated from ``src/dapi/src/include/esc.h`` lines 142-156.

The ``SAY_*`` flags select the granularity of the
``[:say <mode>]`` inline command — clause / word / letter /
line / syllable / first-letter — and are passed via
``pKsd_t->sayflag``.

The ``R2_*`` constants identify the *flavour* of a
DCS reply: index responses, error responses, etc. They appear
as the second parameter of a DCS reply packet emitted by the
DECtalk back-end to the host.
"""

from __future__ import annotations

from typing import Final

# -- [:say <mode>] granularity bits ----------------------------------------

SAY_CLAUSE: Final[int] = 0x0000
"""``[:say clause]`` — read one clause at a time (default)."""

SAY_WORD: Final[int] = 0x0001
"""``[:say word]`` — pause between every word."""

SAY_LETTER: Final[int] = 0x0002
"""``[:say letter]`` — spell out each letter."""

SAY_LINE: Final[int] = 0x0004
"""``[:say line]`` — pause between every newline-separated line."""

SAY_SYLLABLE: Final[int] = 0x0008
"""``[:say syllable]`` — pause between every syllable."""

SAY_FLETTER: Final[int] = 0x0010
"""``[:say fletter]`` — say each character's first-letter (military-style)."""

# -- DCS reply flavour codes (second parameter of a reply packet) ----------

R2_IX_REPLY: Final[int] = 31
"""DCS reply packet emitted after an ``INDEX_REPLY``."""

R2_IX_QUERY: Final[int] = 32
"""DCS reply packet emitted after an ``INDEX_QUERY``."""

R2_ERROR: Final[int] = 300
"""DCS reply packet emitted when the engine detects a command error."""

# -- DCS framing codes -----------------------------------------------------

DCS_F_DECTALK: Final[int] = ord("z")
"""DECtalk DCS-final byte (122 / 0x7A)."""

P1_DECTALK: Final[int] = 0
"""DECtalk DCS first-parameter value — any non-zero/non-``z`` is rejected."""


__all__ = [
    "DCS_F_DECTALK",
    "P1_DECTALK",
    "R2_ERROR",
    "R2_IX_QUERY",
    "R2_IX_REPLY",
    "SAY_CLAUSE",
    "SAY_FLETTER",
    "SAY_LETTER",
    "SAY_LINE",
    "SAY_SYLLABLE",
    "SAY_WORD",
]
