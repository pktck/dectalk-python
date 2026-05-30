"""Intonation state codes and tuning constants for the active F0 engine.

The hat-rise phase and clause-type codes are translated from
``src/dapi/src/ph/ph_inton0.c`` (lines 83-90) — the active
``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` intonation source. The
F0-generation mode codes (:data:`NORMAL` .. :data:`TIME_VALUE_SPECIFIED`)
and the shared ``ZAP`` / ``SAFETY`` constants come from ``viphdefs.h`` /
``ph_defs.h``.

The constants split into:

- **Hat-rise phase codes** (:data:`BEFORE_HAT_RISE` ..
  :data:`AFTER_NONFINAL_FALL`) — values the intonation engine
  assigns to ``pDph_t->hat_state`` as it walks an utterance.
- **Clause-type codes** (:data:`DONTKNOW` .. :data:`PERIODCLAUSE`) —
  the four clause flavours (unknown / question / verb-phrase /
  period) used to pick the terminal contour.

The ``DELTA*`` / ``EMPH_FALL`` tuning constants that ``ph_inton1.c`` /
``ph_inton2.c`` (the NEW-intonation variants) define are *not* part of
the active ``ph_inton0.c`` engine and are intentionally omitted.
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

# -- F0 generation modes (viphdefs.h) --------------------------------------

NORMAL: Final[int] = 1
"""F0 mode: rule-generated F0 (default)."""

HAT_LOCATIONS_SPECIFIED: Final[int] = 2
"""F0 mode: user specified location of hat rise / fall."""

HAT_F0_SIZES_SPECIFIED: Final[int] = 3
"""F0 mode: user attached steps and impulses to hat-rise / hat-fall / stress
phones."""

SINGING: Final[int] = 4
"""F0 mode: user-requested sung notes (each syllable a fixed pitch)."""

PHONE_TARGETS_SPECIFIED: Final[int] = 5
"""F0 mode: user-specified F0 targets per phone."""

TIME_VALUE_SPECIFIED: Final[int] = 6
"""F0 mode: user-spec F0 targets at ``{time, value}`` pairs (ph_defs.h)."""

# -- Speaker-def filter "zap" magic values ---------------------------------

ZAPF: Final[int] = 6000
"""Magic ``f`` value to zap the ``b`` coefficient of the resonator diff-eq
(non-MSDOS / HLSYN build value)."""

ZAPB: Final[int] = 6000
"""Magic ``bw`` value to zap the ``c`` coefficient of the resonator diff-eq."""

# -- Shared-array offset ---------------------------------------------------

SAFETY: Final[int] = 8
"""Offset between shared arrays such as ``phonemes[SAFETY]`` and
``allophons[0]`` — guards against off-by-one reads at the array boundary."""

__all__ = [
    "AFTER_FINAL_FALL",
    "AFTER_NONFINAL_FALL",
    "BEFORE_HAT_RISE",
    "DONTKNOW",
    "HAT_F0_SIZES_SPECIFIED",
    "HAT_LOCATIONS_SPECIFIED",
    "NORMAL",
    "ON_TOP_OF_HAT",
    "PERIODCLAUSE",
    "PHONE_TARGETS_SPECIFIED",
    "QUESTCLAUSE",
    "SAFETY",
    "SINGING",
    "TIME_VALUE_SPECIFIED",
    "VERBPHRASE",
    "ZAPB",
    "ZAPF",
]
