"""Plosive build-time constants from ph_draw.c.

Translated from ``src/dapi/src/ph/ph_draw.c`` lines 155-156.

Two single-frame-count thresholds the VTM drawing logic uses to
schedule the *plosive build-up* — the brief ramp before the burst
release in a plosive's articulation:

- :data:`LPLOS_BUILD_TIME` — labio-plosive build-up frames (used
  by left-context plosive drawing).
- :data:`BPLOS_BUILD_TIME` — bilabial-plosive build-up frames
  (used by ``ph_draw`` in the burst-trigger pre-ramp arithmetic
  ``pDph_t->tcum >= tspesh - BPLOS_BUILD_TIME``).

Both are 7 frames (≈70 ms at the engine's frame rate). Defined as
``const short`` in the C source rather than ``#define`` so they
have file-scope linkage and a debugger can see them.
"""

from __future__ import annotations

from typing import Final

LPLOS_BUILD_TIME: Final[int] = 7
"""Labio-plosive build-up duration in frames."""

BPLOS_BUILD_TIME: Final[int] = 7
"""Bilabial-plosive build-up duration in frames."""


__all__ = ["BPLOS_BUILD_TIME", "LPLOS_BUILD_TIME"]
