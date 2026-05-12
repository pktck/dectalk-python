"""Musical-note F0 lookup table from ph_romi.c.

Translated from ``src/dapi/src/ph/ph_romi.c``. ``notetab`` maps a
1-based note index (1..37) to the corresponding F0 frequency in
Hz x 10. The 37 notes cover the C2..C5 chromatic range, with the
voice presets clustered around specific notes:

  - 5 (E2)  — Huge Harry's range floor
  - 8 (G2)  — Perfect Paul's centre
  - 13 (C3) — Frail Frank
  - 18 (F3) — Beautiful Betty
  - 25 (C4) — Uppity Ursula / Kit the Kid
  - 26 (C#4) — Rough Rita

The singing-mode parser indexes into this table via the ``[:t<n>]``
command to produce a fixed-pitch syllable.
"""

from __future__ import annotations

from typing import Final

notetab: Final[tuple[int, ...]] = (
    640,   # 1  = C2
    678,   # 2  = C#
    718,   # 3  = D
    761,   # 4  = D#
    806,   # 5  = E   (HARRY)
    854,   # 6  = F
    905,   # 7  = F#
    959,   # 8  = G   (PAUL)
    1016,  # 9  = G#
    1076,  # 10 = A
    1140,  # 11 = A#
    1208,  # 12 = B
    1280,  # 13 = C3  (FRANK)
    1356,  # 14 = C#
    1437,  # 15 = D
    1522,  # 16 = D#
    1613,  # 17 = E
    1709,  # 18 = F   (BETTY)
    1810,  # 19 = F#
    1918,  # 20 = G
    2032,  # 21 = G#
    2152,  # 22 = A
    2280,  # 23 = A#
    2416,  # 24 = B   (URSULA / KIT)
    2560,  # 25 = C4
    2712,  # 26 = C#  (RITA)
    2874,  # 27 = D
    3044,  # 28 = D#
    3226,  # 29 = E
    3418,  # 30 = F
    3620,  # 31 = F#
    3836,  # 32 = G
    4064,  # 33 = G#
    4304,  # 34 = A
    4560,  # 35 = A#
    4832,  # 36 = B
    5120,  # 37 = C5
)  # fmt: skip
"""37-entry chromatic note table (1-based index → F0 in Hz x 10)."""

NOTETAB_SIZE: Final[int] = 37
"""Number of notes in :data:`notetab` (C2 → C5)."""

__all__ = ["NOTETAB_SIZE", "notetab"]
