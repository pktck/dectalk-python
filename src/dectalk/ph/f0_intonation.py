"""US English F0 intonation tables.

Translated from ``src/dapi/src/ph/ph_inton2.c``. These four tables
drive the C library's F0 contour generation:

- :data:`us_f0_mphrase_position` (male, 8 entries) — F0 rise/fall in
  Hz*10 by accent position within a clause (1st accent gets the
  biggest rise, decaying through 2nd..8th).
- :data:`us_f0_fphrase_position` (female, 8 entries) — same but for
  female voices.
- :data:`us_f0_mstress_level` (male, 4 entries) — F0 rise by stress
  level: ``[unstressed, primary, secondary, emphatic]``.
- :data:`us_f0_fstress_level` (female, 4 entries) — same for female
  voices.

The C source notes: ``f0_stress_level + f0_phrase_pos must add up to
an odd number or you will be creating a step function instead of the
desired IMPULSE function``.

Picks the non-POETRY branch of ``us_f0_mphrase_position`` (POETRY
mode is OFF in the Linux build).
"""

from __future__ import annotations

from typing import Final

# Male F0 rise/fall by phrase position (1st..8th accent in clause).
us_f0_mphrase_position: Final[tuple[int, ...]] = (160, 80, 60, 40, 30, 20, 20, 5)

# Male F0 rise by stress level: [unstressed, primary, secondary, emphatic].
us_f0_mstress_level: Final[tuple[int, ...]] = (1, 81, 61, 161)

# Female F0 rise/fall by phrase position.
us_f0_fphrase_position: Final[tuple[int, ...]] = (180, 80, 70, 60, 50, 40, 34, 30)

# Female F0 rise by stress level.
us_f0_fstress_level: Final[tuple[int, ...]] = (1, 100, 80, 161)


__all__ = [
    "us_f0_fphrase_position",
    "us_f0_fstress_level",
    "us_f0_mphrase_position",
    "us_f0_mstress_level",
]
