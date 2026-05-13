"""Sample-rate constants from samprate.h + vismprat.h.

Translated from ``src/dapi/src/include/samprate.h`` and
``src/dapi/src/vtm/vismprat.h``.

Two sample-rate constants the engine uses to size its output:

- :data:`PC_SAMPLE_RATE` (11025 Hz) — DECtalk's native output
  sample rate for PC-resolution audio. The VTM resamples to this
  via :mod:`dectalk.vtm`. Defined in vismprat.h line 42.
- :data:`MULAW_SAMPLE_RATE` (8000 Hz) — the lower-rate mu-law
  variant used for telephone-quality output. Defined in
  samprate.h line 12.
"""

from __future__ import annotations

from typing import Final

PC_SAMPLE_RATE: Final[int] = 11025
"""DECtalk's native output sample rate (11.025 kHz)."""

MULAW_SAMPLE_RATE: Final[int] = 8000
"""Telephone-quality mu-law output rate (8 kHz)."""


__all__ = ["MULAW_SAMPLE_RATE", "PC_SAMPLE_RATE"]
