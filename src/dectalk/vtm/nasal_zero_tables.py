"""Nasal-zero filter coefficient tables from vtmtable.h.

Translated from ``src/dapi/src/vtm/vtmtable.h`` lines 165-203.

The VTM uses three parallel 35-entry tables (:data:`azero_tab`,
:data:`bzero_tab`, :data:`czero_tab`) precomputing the filter
coefficients for the nasal zero across the 35-bin nasal-zero
frequency grid. They're derived by the C source at compile time
from the formulas (sampling at 10 kHz, bandwidth 80 Hz):

.. code-block:: c

    Nasal_T      = 1 / 10000
    Nasal_C      = (2 * 80) - 4096   = -3936
    Nasal_B(FZ)  = (8192 - 160) * cos(2 * pi * FZ * 1e-4)
    Nasal_A(FZ)  = 4096 - Nasal_C - Nasal_B(FZ)

    azero[FZ]    = 4096 * ZGAIN / Nasal_A(FZ)
    bzero[FZ]    = -Nasal_B(FZ) * ZGAIN / Nasal_A(FZ)
    czero[FZ]    = -Nasal_C * ZGAIN / Nasal_A(FZ)

Per the header comment, a runtime FZ in Hz is scaled to the table
index via ``(FZ * 10) >> 3`` (i.e. *FZ_kHz scaled by 1.25*),
then looked up.

The values here are byte-for-byte from the C source so the Q14
fixed-point filter coefficient bits stay identical when the VTM
nasal zero runs through Python.
"""

from __future__ import annotations

from typing import Final

NASAL_BW: Final[float] = 80.0
"""Nasal-zero bandwidth in Hz."""

NASAL_T: Final[float] = 1.0 / 10000.0
"""Sampling period in seconds (10 kHz)."""

NASAL_C: Final[int] = -3936
"""``Nasal_C = (2 * NASAL_BW) - 4096`` — precomputed for indexing."""

azero_tab: Final[tuple[int, ...]] = (
    3864,
    3611,
    3405,
    3207,
    3018,
    2861,
    2700,
    2555,
    2434,
    2309,
    2195,
    2093,
    1994,
    1904,
    1822,
    1742,
    1669,
    1598,
    1533,
    1473,
    1415,
    1361,
    1312,
    1263,
    1216,
    1172,
    1131,
    1094,
    1056,
    1020,
    988,
    963,
    926,
    897,
    869,
)
"""35-entry table of ``azero`` coefficients across the FZ grid."""

bzero_tab: Final[tuple[int, ...]] = (
    -7453,
    -6960,
    -6558,
    -6171,
    -5802,
    -5496,
    -5181,
    -4899,
    -4662,
    -4418,
    -4197,
    -3996,
    -3803,
    -3628,
    -3467,
    -3312,
    -3169,
    -3031,
    -2905,
    -2788,
    -2674,
    -2569,
    -2472,
    -2377,
    -2285,
    -2200,
    -2120,
    -2046,
    -1974,
    -1903,
    -1840,
    -1778,
    -1719,
    -1662,
    -1609,
)
"""35-entry table of ``bzero`` coefficients (all negative)."""

czero_tab: Final[tuple[int, ...]] = (
    3677,
    3437,
    3241,
    3052,
    2872,
    2723,
    2569,
    2432,
    2316,
    2197,
    2089,
    1992,
    1897,
    1812,
    1734,
    1658,
    1588,
    1521,
    1459,
    1402,
    1347,
    1296,
    1248,
    1202,
    1157,
    1115,
    1077,
    1041,
    1005,
    971,
    940,
    910,
    881,
    853,
    827,
)
"""35-entry table of ``czero`` coefficients across the FZ grid."""


__all__ = [
    "NASAL_BW",
    "NASAL_C",
    "NASAL_T",
    "azero_tab",
    "bzero_tab",
    "czero_tab",
]
