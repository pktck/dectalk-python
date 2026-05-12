"""Sonorant-class equivalence table from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c``. ``sonequivindex`` is
a 6-entry mapping from sonorant-class index (0..5) to an equivalence
group index used by the formant-locus computation in ``setloc()``.

  Class                  Group
  ---------------------- -----
  0 Unused                 0
  1 Front vowel            2
  2 Back unrounded         0
  3 Back rounded           4
  4 Obstruent              0  (TODO marker in C: "?? Obstruent")
  5 Rounded sonorant cons  4
"""

from __future__ import annotations

from typing import Final

sonequivindex: Final[tuple[int, ...]] = (
    0,  # Unused
    2,  # Front vowel
    0,  # Back unrounded
    4,  # Back rounded
    0,  # ?? Obstruent (TODO marker in C source)
    4,  # Rounded sonorant consonant
)
"""6-entry sonorant-class → equivalence-group lookup."""


__all__ = ["sonequivindex"]
