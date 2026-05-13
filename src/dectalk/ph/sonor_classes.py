"""Phoneme sonorant-class constants from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` lines 125-129 and
232-233 — five sonorant-equivalence classes used by the
allophone-substitution rules in ``phsettar``. The
:data:`dectalk.ph.sonor_tables.sonequivindex` table maps each of
these into a small integer used by the smoothing rules.

Also includes :data:`INITIAL` / :data:`FINAL` boundary-position
flags shared by all the language ``*_forw_smooth_rules`` /
``*_back_smooth_rules`` callbacks.
"""

from __future__ import annotations

from typing import Final

FRONT_VOWEL: Final[int] = 1
"""Sonorant class: front vowel (IY, IH, EY, EH, AE)."""

BACK_UNROUNDED_VOWEL: Final[int] = 2
"""Sonorant class: back unrounded vowel (AA, AH, AX)."""

BACK_ROUNDED_VOWEL: Final[int] = 3
"""Sonorant class: back rounded vowel (UH, UW, OW, OY)."""

OBSTRUENT: Final[int] = 4
"""Sonorant class: obstruent — stops + fricatives + affricates."""

ROUNDED_SONOR_CONS: Final[int] = 5
"""Sonorant class: rounded sonorant consonant (W, semivowels)."""

# -- Initial/Final boundary flags ------------------------------------------

INITIAL: Final[bool] = False
"""Boundary-position flag: word/segment initial."""

FINAL: Final[bool] = True
"""Boundary-position flag: word/segment final."""

# -- Spanish-specific aspiration amplitude --------------------------------

ASPIRATION_AMPLITUDE: Final[int] = 42
"""Spanish-build constant: aspiration amplitude after a plosive.

Comment from ph_setar.c: "Used to select boundary values" / "Still
too hot in some places (EAB 05/08/97)". Only referenced in the
``#ifdef SPANISH`` build.
"""


__all__ = [
    "ASPIRATION_AMPLITUDE",
    "BACK_ROUNDED_VOWEL",
    "BACK_UNROUNDED_VOWEL",
    "FINAL",
    "FRONT_VOWEL",
    "INITIAL",
    "OBSTRUENT",
    "ROUNDED_SONOR_CONS",
]
