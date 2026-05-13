"""Integer volume-attenuation lookup table from vtm3.c.

Translated from ``src/dapi/src/vtm/vtm3.c`` lines 183-323 (also
mirrored in ``vtm2.c`` line 272). The kernel writes
``pKsd_t->vol_att`` (0..140) and the VTM looks it up here to get
a 32-bit integer multiplier the synthesis loop applies to each
output sample.

Index meaning:

- ``int_volume_table[0]`` = 0   — full mute.
- ``int_volume_table[100]`` = 32767 — unity gain in Q15.
- ``int_volume_table[140]`` = 131071 — about +12 dB above unity.

The curve is exponential: each step is roughly +0.5 dB. The C
source generates the values offline; we copy them verbatim for
bit-parity.
"""

from __future__ import annotations

from typing import Final

# fmt: off
int_volume_table: Final[tuple[int, ...]] = (
    0,
    1071, 1110, 1149, 1189, 1231, 1274, 1319, 1365, 1413, 1463,
    1515, 1568, 1623, 1680, 1739, 1800, 1863, 1929, 1997, 2067,
    2140, 2215, 2293, 2373, 2457, 2543, 2632, 2725, 2821, 2920,
    3023, 3129, 3239, 3353, 3470, 3592, 3719, 3849, 3985, 4125,
    4270, 4420, 4575, 4736, 4902, 5075, 5253, 5438, 5629, 5826,
    6031, 6243, 6463, 6690, 6925, 7168, 7420, 7681, 7951, 8230,
    8520, 8819, 9129, 9450, 9782, 10126, 10481, 10850, 11231, 11626,
    12034, 12457, 12895, 13348, 13817, 14303, 14806, 15326, 15865, 16422,
    16999, 17597, 18215, 18855, 19518, 20204, 20914, 21649, 22410, 23197,
    24012, 24856, 25730, 26634, 27570, 28539, 29542, 30580, 31655, 32767,
    33917, 35107, 36339, 37615, 38935, 40302, 41716, 43181, 44696, 46265,
    47889, 49570, 51310, 53111, 54975, 56905, 58902, 60970, 63110, 65535,
    67618, 69991, 72448, 74991, 77623, 80348, 83168, 86087, 89109, 92237,
    95474, 98825, 102294, 105885, 109601, 113448, 117430, 121552, 125819, 131071,
)
"""141-entry exponential volume-attenuation curve (each step ~+0.5 dB)."""
# fmt: on


__all__ = ["int_volume_table"]
