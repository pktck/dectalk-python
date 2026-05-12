"""Intonation state codes and tuning constants from ph_inton2.c.

Translated from ``src/dapi/src/ph/ph_inton2.c``. The constants split
into three groups:

- **Hat-rise phase codes** (:data:`BEFORE_HAT_RISE` ..
  :data:`AFTER_NONFINAL_FALL`) — values the intonation engine
  assigns to ``pDph_t->hat_state`` as it walks an utterance.
- **Clause-type codes** (:data:`DONTKNOW` .. :data:`PERIODCLAUSE`) —
  the four clause flavours (unknown / question / verb-phrase /
  period) used to pick the terminal contour.
- **Delta tuning** (:data:`EMPH_FALL` .. :data:`FINAL_FALL`) —
  fixed-point F0 deltas (units of 0.1 Hz scaled by a factor) the
  intonation engine layers onto the declination contour.
"""

from __future__ import annotations

from typing import Final

# -- Hat-rise phase codes ---------------------------------------------------

BEFORE_HAT_RISE: Final[int] = 0
"""Utterance position before the hat-rise gesture has started."""

ON_TOP_OF_HAT: Final[int] = 1
"""On the high-pitch plateau between the hat rise and the final fall."""

AFTER_FINAL_FALL: Final[int] = 2
"""Past the final declination fall — the trailing fade."""

AFTER_NONFINAL_FALL: Final[int] = 3
"""Past a non-final fall (mid-utterance dip before the next stress)."""

# -- Clause-type codes ------------------------------------------------------

DONTKNOW: Final[int] = 0
"""Clause classification not yet determined."""

QUESTCLAUSE: Final[int] = 1
"""Clause is a yes/no question — terminal rise."""

VERBPHRASE: Final[int] = 2
"""Clause is a verb phrase — continuing intonation."""

PERIODCLAUSE: Final[int] = 3
"""Clause ends in a period — terminal fall."""

# -- F0 delta tuning constants (fixed-point) --------------------------------

EMPH_FALL: Final[int] = 1
"""Stress-reduce shift applied to emphatically stressed syllables."""

DELTAEMPH_SPEC: Final[int] = 505
"""Special-case emphatic-stress delta for fast speech."""

DELTAEMPH: Final[int] = 501
"""Normal emphatic-stress F0 delta."""

DELTARISE: Final[int] = 200
"""F0 rise for a continuing-cadence syllable."""

DELTAFINAL: Final[int] = 100
"""F0 delta to remain at the top of a final-cadence rise."""

FINAL_FALL: Final[int] = 1
"""Stress-reduce shift for the syllable at the top of a final fall."""

__all__ = [
    "AFTER_FINAL_FALL",
    "AFTER_NONFINAL_FALL",
    "BEFORE_HAT_RISE",
    "DELTAEMPH",
    "DELTAEMPH_SPEC",
    "DELTAFINAL",
    "DELTARISE",
    "DONTKNOW",
    "EMPH_FALL",
    "FINAL_FALL",
    "ON_TOP_OF_HAT",
    "PERIODCLAUSE",
    "QUESTCLAUSE",
    "VERBPHRASE",
]
