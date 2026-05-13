"""Static nasal lookup tables and constants from nasalf1x.c / inithl.c.

The HLSyn nasal-cavity model needs two tables and a few scalar
constants when placing the nasal pole and zero:

- ``ANFN_TABLE`` -- maps the nasal-cavity area ``an`` (mm^2) to the
  nasal-formant centre frequency ``fn`` (Hz) for a 500 Hz-``fno``
  reference speaker. Defined in ``inithl.c`` at lines 108-126 and
  also under ``#ifdef EPSON_ARM7`` in ``hlframe.c`` at lines 94-103.
- ``F1_LOVER_A_TABLE`` -- maps the constriction-modified F1
  (``state.f1c``) to the nasal-mass ratio ``L/A`` (1/cm). Defined in
  ``inithl.c`` at lines 136-158 and under ``#ifdef EPSON_ARM7`` in
  ``hlframe.c`` at lines 79-91.
- ``ANFN_TABLE_FNO`` -- reference ``fno`` (500 Hz) at which the
  ``ANFN_TABLE`` ``fn`` column was tabulated. The actual speaker's
  ``fno`` rescales ``fn`` proportionally.
- ``NASAL_BANDWIDTH`` -- ``#define NasalBandwidth 200.0f`` from
  ``hlsyn.h`` line 248. Used as the floor for the nasal-zero
  bandwidth and as a Hz-per-mm^2 scaling constant for the bandwidth
  contribution of the nasal area.

Table row count constants ``MAX_ANFN`` (= 9) and ``MAX_F1_LOVER_A``
(= 11) come from ``hlsyn.h`` lines 191 and 195. They mirror the
C-side ``MAXANFN`` / ``MAXF1LOVERA`` ``#define``s; nothing in the
Python port consumes them directly (we use ``len()``) but they are
exposed for parity with the C source.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Sizes (``hlsyn.h`` lines 191, 195).
# ---------------------------------------------------------------------------
MAX_ANFN: Final[int] = 9
MAX_F1_LOVER_A: Final[int] = 11

# ---------------------------------------------------------------------------
# ``anfnTable_fno`` (``inithl.c`` line 107, ``hlframe.c`` line 93).
# Reference ``fno`` (500 Hz) for the ``ANFN_TABLE`` ``fn`` column.
# ---------------------------------------------------------------------------
ANFN_TABLE_FNO: Final[float] = 500.0

# ---------------------------------------------------------------------------
# ``NasalBandwidth`` (``hlsyn.h`` line 248).
# Floor / Hz-per-mm^2 scaling constant for nasal-zero bandwidth.
# ---------------------------------------------------------------------------
NASAL_BANDWIDTH: Final[float] = 200.0

# ---------------------------------------------------------------------------
# ``anfnTable[MAXANFN]`` -- (an [mm^2], fn [Hz]) rows.
# Defined in ``inithl.c`` lines 108-126 (initialised piecewise) and
# verbatim under ``#ifdef EPSON_ARM7`` in ``hlframe.c`` lines 94-103.
# ---------------------------------------------------------------------------
ANFN_TABLE: Final[tuple[tuple[float, float], ...]] = (
    (0.0, 500.0),
    (10.0, 580.0),
    (20.0, 660.0),
    (30.0, 730.0),
    (40.0, 780.0),
    (50.0, 810.0),
    (60.0, 840.0),
    (70.0, 870.0),
    (80.0, 900.0),
)

# ---------------------------------------------------------------------------
# ``f1LOverATable[MAXF1LOVERA]`` -- (f1 [Hz], L/A [1/cm]) rows.
# Defined in ``inithl.c`` lines 136-158 and under ``#ifdef EPSON_ARM7``
# in ``hlframe.c`` lines 79-91.
# ---------------------------------------------------------------------------
F1_LOVER_A_TABLE: Final[tuple[tuple[float, float], ...]] = (
    (180.0, 1000.0),
    (200.0, 25.0),
    (250.0, 20.0),
    (300.0, 10.0),
    (350.0, 7.0),
    (400.0, 5.0),
    (450.0, 4.0),
    (500.0, 3.0),
    (600.0, 2.5),
    (700.0, 2.0),
    (800.0, 1.8),
)


__all__ = [
    "ANFN_TABLE",
    "ANFN_TABLE_FNO",
    "F1_LOVER_A_TABLE",
    "MAX_ANFN",
    "MAX_F1_LOVER_A",
    "NASAL_BANDWIDTH",
]
