"""US English prosody constants from ph_defs.h.

Translated from the ``#ifdef ENGLISH_US`` block of
``src/dapi/src/ph/ph_defs.h``. These constants drive specific
prosody behaviours in the PH module's F0 contour generation:

- :data:`F0_QGesture1` / :data:`F0_QGesture2` — F0 step amounts for
  question-mode terminal rise (1st and 2nd accent).
- :data:`F0_CGesture1` / :data:`F0_CGesture2` — comma gesture
  step amounts.
- :data:`F0_FINAL_FALL` — Hz*10 declination on the final stressed
  syllable.
- :data:`F0_NON_FINAL_FALL` — same, for non-final syllables.
- :data:`F0_COMMA_FALL` — F0 fall amount at a comma break.
- :data:`F0_QSYLL_FALL` — F0 fall on the final syllable when in
  question mode.
- :data:`F0_GLOTTALIZE` — F0 drop per cycle during glottalisation
  (BATS#796).
- :data:`GEST_SHIFT` — gesture timing-shift constant.
- :data:`MAX_NRISES` — max number of stress-rises per phrase
  (depends on active VOICE_ROM; VOICE_ROM_BETA5 build uses 7).
- :data:`Reduce_last` — reduction factor for the last syllable.
"""

from __future__ import annotations

from typing import Final

# F0 step amounts for question-mode terminal rise.
F0_QGesture1: Final[int] = 351
F0_QGesture2: Final[int] = 451

# F0 step amounts for comma gestures.
F0_CGesture1: Final[int] = 171
F0_CGesture2: Final[int] = 250

# Gesture timing shift constant.
GEST_SHIFT: Final[int] = 1

# Max number of stress-rises per phrase. VOICE_ROM_BETA5 (the modern
# Linux build uses p_us_rom.c) sets this to 7. Other ROM variants
# (DECTALK_43, DTC_03_03Jan89, etc.) use 4.
MAX_NRISES: Final[int] = 7

# F0 fall amounts in Hz*10.
F0_FINAL_FALL: Final[int] = 180
F0_NON_FINAL_FALL: Final[int] = 150
F0_COMMA_FALL: Final[int] = 120
F0_QSYLL_FALL: Final[int] = 80

# F0 drop per cycle during glottalisation.
F0_GLOTTALIZE: Final[int] = -60

# Reduction factor for final syllable.
Reduce_last: Final[int] = 50

# F0 step at a clause boundary (US value).
F0_CBOUND_PULSE: Final[int] = 700

# ---- F0 command-type codes (from ph_defs.h) ----

USER: Final[int] = 0
"""F0 command type: user-supplied F0 value."""

IMPULSE: Final[int] = 1
"""F0 command type: an impulse (instant rise)."""

STEP: Final[int] = 2
"""F0 command type: step (sudden change to new level)."""

F0_RESET: Final[int] = 3
"""F0 command type: reset to baseline."""

GLOTTAL: Final[int] = 4
"""F0 command type: glottalised drop."""

GLIDE: Final[int] = 5
"""F0 command type: smooth glide between targets."""

SHORTIMPULSE: Final[int] = 6
"""F0 command type: short impulse (gestures shorter than normal)."""

# ---- Clause-type codes (from ph_defs.h) ----

DECLARATIVE: Final[int] = 0
"""Clause type: declarative (period)."""

COMMACLAUSE: Final[int] = 1
"""Clause type: clause break (comma)."""

EXCLAIMCLAUSE: Final[int] = 2
"""Clause type: exclamation."""

QUESTION: Final[int] = 3
"""Clause type: yes/no question."""

# ---- Nasal-zero target defaults ----

NON_NASAL_ZERO: Final[int] = 290
"""F0 of the nasal zero for non-nasalised segments."""

NASAL_ZERO_BOUNDARY: Final[int] = 370
"""F0 of the nasal zero at a nasal boundary."""

NASAL_ZERO_CONS: Final[int] = 400
"""F0 of the nasal zero during a nasal consonant."""


__all__ = [
    "COMMACLAUSE",
    "DECLARATIVE",
    "EXCLAIMCLAUSE",
    "F0_CBOUND_PULSE",
    "F0_COMMA_FALL",
    "F0_FINAL_FALL",
    "F0_GLOTTALIZE",
    "F0_NON_FINAL_FALL",
    "F0_QSYLL_FALL",
    "F0_RESET",
    "GEST_SHIFT",
    "GLIDE",
    "GLOTTAL",
    "IMPULSE",
    "MAX_NRISES",
    "NASAL_ZERO_BOUNDARY",
    "NASAL_ZERO_CONS",
    "NON_NASAL_ZERO",
    "QUESTION",
    "SHORTIMPULSE",
    "STEP",
    "USER",
    "F0_CGesture1",
    "F0_CGesture2",
    "F0_QGesture1",
    "F0_QGesture2",
    "Reduce_last",
]
