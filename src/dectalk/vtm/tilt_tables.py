"""Spectral-tilt resonator frequency / bandwidth tables from vtmtable.h.

Translated from ``src/dapi/src/vtm/vtmtable.h`` lines 547-582.

The VTM's 2-pole spectral-tilt resonator is precomputed across a
42-entry grid of (F, BW) pairs that paramaterise the
:func:`scipy.signal.lfilter`-equivalent biquad. The C source notes:

- ``tiltf`` — exact F values assuming exact calculation of the C
  coefficient.
- ``tiltbw`` — corresponding BW values assuming the approximation
  ``C = (2 * BW) - 4096``.

The two arrays are indexed in lock-step by the engine's
``OQ`` / ``TILT`` mapping. A 9-row reference dump of the actual
2-pole tilt-resonator amplitude response (250 Hz through 4 kHz)
appears as a comment in the C source and is mirrored in
:data:`tilt_response_db` for completeness.
"""

from __future__ import annotations

from typing import Final

# fmt: off
tiltf: Final[tuple[int, ...]] = (
    4400, 4330, 3750, 3270, 2850,
    2500, 2394, 2289, 2184, 2080,
    1977, 1875, 1770, 1666, 1562,
    1458, 1354, 1250, 1197, 1145,
    1093, 1041,  989,  937,  885,
     833,  781,  729,  677,  625,
     599,  573,  547,  521,  495,
     469,  442,  416,  390,  364,
     338,  312,
)
"""42-entry tilt-resonator centre-frequency table (Hz)."""

tiltbw: Final[tuple[int, ...]] = (
    1960, 1876, 1800, 1732, 1672,
    1622, 1580, 1538, 1490, 1446,
    1403, 1360, 1318, 1276, 1235,
    1195, 1154, 1114, 1089, 1063,
    1038, 1014,  989,  937,  885,
     833,  781,  729,  677,  625,
     599,  573,  547,  521,  495,
     469,  442,  416,  390,  364,
     338,  312,
)
"""42-entry tilt-resonator bandwidth table (Hz)."""
# fmt: on


# 9-row tilt-resonator amplitude response from the C source comment block:
# columns are A@250 Hz, A@1 kHz, A@2 kHz, A@3 kHz, A@4 kHz; F / BW preceding.
tilt_response_db: Final[tuple[tuple[int, int, int, int, int, int, int], ...]] = (
    (3000, 5000, 42, 42, 43, 44, 44),
    (2250, 3750, 42, 42, 42, 42, 41),
    (1500, 2500, 42, 42, 41, 39, 36),
    (1125, 1875, 42, 42, 39, 33, 30),
    (750, 1250, 42, 41, 32, 27, 23),
    (567, 937, 42, 37, 27, 21, 17),
    (375, 625, 42, 32, 21, 15, 11),
    (283, 469, 42, 27, 16, 9, 5),
    (187, 312, 40, 22, 10, 3, 0),
)
"""Reference response table from the C-source comment (F, BW, then dB @ 5 freq points)."""


__all__ = [
    "tilt_response_db",
    "tiltbw",
    "tiltf",
]
