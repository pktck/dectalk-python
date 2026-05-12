"""Miscellaneous kernel-level constants from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. Small constants
the kernel passes around but that don't fit any of the larger
groupings (mode flags, packet codes, language IDs, etc.).

- :data:`VERSIONLEN` — version string buffer size.
- :data:`SPEAKLEN` — input buffer size for one speech segment.
- :data:`TICKS_PER_SECOND` — timer ticks per wall-clock second
  (10ms per tick).
- :data:`ANY_CHANGE` / :data:`LOW_CHANGE` / :data:`HIGH_CHANGE` —
  three-state codes for the volume-change signal.
"""

from __future__ import annotations

from typing import Final

VERSIONLEN: Final[int] = 80
"""Size of the buffer used to hold the engine version string."""

SPEAKLEN: Final[int] = 190
"""Size of the input buffer for one speech segment."""

TICKS_PER_SECOND: Final[int] = 100
"""Timer ticks per second (10ms per tick)."""

ANY_CHANGE: Final[int] = 0
"""Volume-change code: detect any change."""

LOW_CHANGE: Final[int] = 1
"""Volume-change code: detect drops only."""

HIGH_CHANGE: Final[int] = 2
"""Volume-change code: detect rises only."""

__all__ = [
    "ANY_CHANGE",
    "HIGH_CHANGE",
    "LOW_CHANGE",
    "SPEAKLEN",
    "TICKS_PER_SECOND",
    "VERSIONLEN",
]
