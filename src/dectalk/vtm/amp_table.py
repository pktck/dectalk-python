"""Amplitude-in-dB to linear Q15 lookup table from vtmtable.h.

Translated from ``src/dapi/src/vtm/vtmtable.h`` lines 222-235.

The VTM converts per-formant amplitudes (expressed in dB by the
voice tables) to linear Q15 multipliers via this 88-entry table.
Each step is 1 dB:

- ``amptable[0]..amptable[12]`` = 0 (silent floor — below the
  -75 dB noise threshold).
- ``amptable[81]`` = 16384 — -6 dB (one octave down from full).
- ``amptable[87]`` = 32767 — full scale (=1.0 in Q15).

The 1-dB quantisation matches the empirical just-noticeable
difference for vowel amplitude perception. Values are byte-
identical to the C source.
"""

from __future__ import annotations

from typing import Final

# fmt: off
amptable: Final[tuple[int, ...]] = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 7, 8,
    9, 10, 11, 13, 14, 16, 18, 20, 22, 25, 28, 32,
    35, 40, 45, 51, 57, 64, 71, 80, 90, 101, 114, 128,
    142, 159, 179, 202, 227, 256, 284, 318, 359, 405, 455, 512,
    568, 638, 719, 811, 911, 1024,
    1137, 1276, 1438, 1622, 1823, 2048,
    2273, 2552, 2875, 3244, 3645, 4096,
    4547, 5104, 5751, 6488, 7291, 8192,
    9093, 10207, 11502, 12976, 14582, 16384,
    18350, 20644, 23429, 26214, 29491, 32767,
)
"""88-entry dB-to-Q15-linear amplitude table (each step = 1 dB)."""
# fmt: on


__all__ = ["amptable"]
