"""Allophone-emission lookup tables from ph_aloph2.c.

Translated from ``src/dapi/src/ph/ph_aloph2.c``. Two tiny tables
indexed by phrase-feature bits when ``phalloph`` decides which
boundary phoneme to insert in the output stream:

- :data:`hphone` — hat-pattern codes selected by intonation phase
  (none / rising / falling / rise-fall).
- :data:`sphone` — stress codes selected by stress phase (none /
  secondary / primary / emphatic).

Both are 4-entry tables. Index 0 is the "no boundary" filler
:data:`~dectalk.ph.utterance_constants.GEN_SIL`.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import HAT_FALL, HAT_RF, HAT_RISE, S1, S2, SEMPH
from dectalk.ph.utterance_constants import GEN_SIL

hphone: Final[tuple[int, ...]] = (
    GEN_SIL,
    HAT_RISE,
    HAT_FALL,
    HAT_RF,
)
"""Hat-pattern phoneme selector (4 entries).

Indexed by the hat-rise phase bits:
0 → ``GEN_SIL`` (no hat), 1 → ``HAT_RISE``, 2 → ``HAT_FALL``,
3 → ``HAT_RF`` (rise-fall).
"""

sphone: Final[tuple[int, ...]] = (
    GEN_SIL,
    S1,
    S2,
    SEMPH,
)
"""Stress-code phoneme selector (4 entries).

Indexed by the stress level bits:
0 → ``GEN_SIL`` (no stress marker), 1 → ``S1`` (primary),
2 → ``S2`` (secondary), 3 → ``SEMPH`` (emphatic).
"""

__all__ = ["hphone", "sphone"]
