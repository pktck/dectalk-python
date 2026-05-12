"""Dictionary-lookup context flags and result codes from ls_dict.h.

Translated from ``src/dapi/src/lts/ls_dict.h``. The C source declares
these as eight ``#define`` constants in two overlapping namespaces:

- **Probe-context flags** (passed to ``ls_util_lookup`` / ``ls_dict_*``
  as the ``context`` argument): :data:`FIRST`, :data:`FABBREV`,
  :data:`SECOND`, :data:`SNOPARS`, :data:`SINGLE_CHAR`.
- **Result codes** (returned from ``ls_dict_blook`` / ``ls_util_lookup``):
  :data:`MISS`, :data:`HIT`, :data:`ABBREV`.

The two namespaces share numerical values (``MISS=0=FIRST``,
``HIT=1=FABBREV``, ``ABBREV=2=SECOND``) but the C source treats them
as logically distinct — argument vs return value. The Python port
preserves the C names so call sites read identically.
"""

from __future__ import annotations

from typing import Final

# -- Probe-context flags (3rd argument to ls_util_lookup) -------------------

FIRST: Final[int] = 0
"""First probe of a word (no abbreviation context, no preprocessing)."""

FABBREV: Final[int] = 1
"""First probe, but treat the word as a candidate abbreviation."""

SECOND: Final[int] = 2
"""Additional probe — the word has already been preprocessed once."""

SNOPARS: Final[int] = 3
"""Additional probe with a trailing ``)`` stripped before lookup."""

SINGLE_CHAR: Final[int] = 4
"""Quick single-character lookup (1-letter words)."""

# -- Result codes (returned from ls_dict_blook / ls_util_lookup) ------------

MISS: Final[int] = 0
"""Word was not found in the dictionary."""

HIT: Final[int] = 1
"""Word was found and matched as a full pronunciation."""

ABBREV: Final[int] = 2
"""Word was found but matched as an abbreviation (e.g. ``"Dr."`` →
``"doctor"``); the caller decides whether to use the abbreviation
expansion based on context."""

__all__ = [
    "ABBREV",
    "FABBREV",
    "FIRST",
    "HIT",
    "MISS",
    "SECOND",
    "SINGLE_CHAR",
    "SNOPARS",
]
