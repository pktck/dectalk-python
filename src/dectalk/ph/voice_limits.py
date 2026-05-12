"""Voice-parameter range limits from ph_vdefi.c.

Translated from ``src/dapi/src/ph/ph_vdefi.c`` lines 261-302 —
the ``LIMIT limit[]`` table that range-checks user-specified
``[:dv <param> <value>]`` commands. Each entry is a
``(min, max)`` pair indexed by the SPD_* constant from
:mod:`dectalk.include.cmd_codes`.

The C source has 38 entries covering SPD_SEX (0) through
SPD_NM (37). Values use ``ZAPF`` and ``ZAPB`` (both 6000 at the
11 kHz Linux build) as upper bounds for formant frequencies and
bandwidths.

The table is consulted by ``cm_cmd_dv`` when parsing voice-
override commands and by ``ph_vset`` when applying them to the
speaker definition.
"""

from __future__ import annotations

from typing import Final

from dectalk.ph.inton_constants import ZAPB, ZAPF
from dectalk.ph.queue_structs import Limit

limit: Final[tuple[Limit, ...]] = (
    Limit(0, 1),  # SPD_SEX
    Limit(0, 100),  # SPD_SM (smoothness)
    Limit(0, 200),  # SPD_AS (assertiveness)
    Limit(50, 350),  # SPD_AP (average pitch)
    Limit(0, 250),  # SPD_PR (pitch range)
    Limit(0, 72),  # SPD_BR (breathiness)
    Limit(0, 100),  # SPD_RI (richness)
    Limit(0, 100),  # SPD_NF (NS frication)
    Limit(0, 100),  # SPD_LA (laryngealization)
    Limit(65, 145),  # SPD_HS (head size, % of Paul)
    Limit(2000, ZAPF),  # SPD_F4
    Limit(100, ZAPB),  # SPD_B4
    Limit(2500, ZAPF),  # SPD_F5
    Limit(100, ZAPB),  # SPD_B5
    Limit(2500, ZAPF),  # SPD_P4 (parallel 4)
    Limit(2500, ZAPF),  # SPD_P5 (parallel 5)
    Limit(0, 87),  # SPD_GF
    Limit(0, 87),  # SPD_GH
    Limit(0, 87),  # SPD_GV
    Limit(0, 87),  # SPD_GN
    Limit(0, 87),  # SPD_G1
    Limit(0, 87),  # SPD_G2
    Limit(0, 87),  # SPD_G3
    Limit(0, 87),  # SPD_G4
    Limit(0, 87),  # SPD_LO (was G5)
    Limit(0, 100),  # SPD_FT (also SPD_FL — same slot, two names)
    Limit(0, 90),  # SPD_BF
    Limit(0, 100),  # SPD_LX
    Limit(0, 100),  # SPD_QU
    Limit(2, 100),  # SPD_HR
    Limit(1, 100),  # SPD_SR
    Limit(0, 1500),  # SPD_AGO (avg glottal opening)
    Limit(0, 1800),  # SPD_AGVO (voiced obstruent)
    Limit(0, 3000),  # SPD_AGUO (unvoiced obstruent)
    Limit(0, 3000),  # SPD_UNVOW (chink area)
    Limit(1, 100),  # SPD_CHINK
    Limit(-32768, 32767),  # SPD_OS / SPD_OQ (signed 16-bit range)
    Limit(0, 8),  # SPD_NM (Linux build appends this slot)
)
"""38 ``(min, max)`` voice-parameter limits indexed by SPD_* constant."""


__all__ = [
    "limit",
]
