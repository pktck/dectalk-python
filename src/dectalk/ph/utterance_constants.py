"""Language-independent prosody / utterance-type constants.

Translated from the top section of ``src/dapi/src/ph/ph_defs.h``
(values applicable to all languages, not gated by ENGLISH_US etc.).
These cover utterance-type codes, F0-command types, formant
bandwidth limits, and the special ``GEN_SIL`` filler.

Used by the PH module's F0 contour generator (phinton et al.) and
formant clipping logic.
"""

from __future__ import annotations

from typing import Final

# General-purpose silence filler (font-shifted PFUSA SIL).
GEN_SIL: Final[int] = 0x01E00


# Utterance-type codes (ph_claus.c).

DECLARATIVE: Final[int] = 0
COMMACLAUSE: Final[int] = 1
EXCLAIMCLAUSE: Final[int] = 2
QUESTION: Final[int] = 3


# F0-command types (ph_inton*.c).

USER: Final[int] = 0
IMPULSE: Final[int] = 1
STEP: Final[int] = 2
F0_RESET: Final[int] = 3
GLOTTAL: Final[int] = 4
GLIDE: Final[int] = 5
SHORTIMPULSE: Final[int] = 6


# Formant frequency upper limits — prevent SPC overload.

F2max: Final[int] = 2500
F3max: Final[int] = 3500


# Nasal-zero zero-frequency targets (anti-resonance).

NON_NASAL_ZERO: Final[int] = 290
NASAL_ZERO_BOUNDARY: Final[int] = 370
NASAL_ZERO_CONS: Final[int] = 400


__all__ = [
    "COMMACLAUSE",
    "DECLARATIVE",
    "EXCLAIMCLAUSE",
    "F0_RESET",
    "GEN_SIL",
    "GLIDE",
    "GLOTTAL",
    "IMPULSE",
    "NASAL_ZERO_BOUNDARY",
    "NASAL_ZERO_CONS",
    "NON_NASAL_ZERO",
    "QUESTION",
    "SHORTIMPULSE",
    "STEP",
    "USER",
    "F2max",
    "F3max",
]
