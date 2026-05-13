"""HLSyn API constants from hlsynapi.h.

Translated from ``src/dapi/src/ph/hlsynapi.h``. These are atomic
constants that gate the HLSyn (high-level Klatt) tables sourced
from the C source — table-row counts and the alveolar-cluster grid
extents:

- ``MAX*`` — the row count for each of the six HLSyn voice-definition
  TableRow arrays (``anfn``, ``f1lovera``, ``ana``, ``anb``, ``f1c``,
  ``ank2``). Each row is a ``(Column1, Column2)`` float pair (see
  :class:`TableRow`) the HLSyn solver interpolates over.
- ``ALV_*`` — the alveolar (post-coronal cluster) grid resolution
  and bounds the HLSyn `Place` lookup uses.

The original C source aliases each table's Column1/Column2 via
per-table ``#define`` macros (e.g. ``ANFN_AN = Column1``,
``ANFN_FN = Column2``). The Python port models each row as an
explicit dataclass with the alias names spelled out where the
lookup helpers live, so we expose only the row counts here.
"""

from __future__ import annotations

from typing import Final

# -- TableRow row counts (one per HLSyn lookup table) ----------------------

MAXANFN: Final[int] = 9
"""Rows in the ``anfn`` (nasal-area → nasal-formant frequency) table."""

MAXF1LOVERA: Final[int] = 11
"""Rows in the ``f1lovera`` (F1 → L/A ratio) table."""

MAXANA: Final[int] = 6
"""Rows in the ``ana`` (nasal-area → A-coupling) table."""

MAXANB: Final[int] = 6
"""Rows in the ``anb`` (nasal-area → B-coupling) table."""

MAXF1C: Final[int] = 7
"""Rows in the ``f1c`` (F1 → C-coupling) table."""

MAXANK2: Final[int] = 17
"""Rows in the ``ank2`` (nasal-area → second-coupling-coefficient) table."""

# -- Alveolar grid extents (Hz) --------------------------------------------

ALV_RESOLUTION: Final[int] = 50
"""Alveolar grid resolution in Hz."""

ALV_F2_MIN: Final[int] = 800
"""Alveolar grid minimum F2 (Hz)."""

ALV_F2_MAX: Final[int] = 2900
"""Alveolar grid maximum F2 (Hz)."""

ALV_F2_POINTS: Final[int] = (ALV_F2_MAX - ALV_F2_MIN) // ALV_RESOLUTION + 1
"""Number of F2 grid points (= 43)."""

ALV_F3_MIN: Final[int] = 1800
"""Alveolar grid minimum F3 (Hz)."""

ALV_F3_MAX: Final[int] = 3600
"""Alveolar grid maximum F3 (Hz)."""

ALV_F3_POINTS: Final[int] = (ALV_F3_MAX - ALV_F3_MIN) // ALV_RESOLUTION + 1
"""Number of F3 grid points (= 37)."""


__all__ = [
    "ALV_F2_MAX",
    "ALV_F2_MIN",
    "ALV_F2_POINTS",
    "ALV_F3_MAX",
    "ALV_F3_MIN",
    "ALV_F3_POINTS",
    "ALV_RESOLUTION",
    "MAXANA",
    "MAXANB",
    "MAXANFN",
    "MAXANK2",
    "MAXF1C",
    "MAXF1LOVERA",
]
