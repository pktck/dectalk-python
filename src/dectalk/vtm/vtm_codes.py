"""VTM (vocal-tract model) constants from vtm.h / viport.h.

Translated from ``src/dapi/src/vtm/vtm.h`` and ``viport.h``. The
VTM module converts Klatt frame plans into audio samples; these
constants govern its sample-rate management and frame sizing.

- :data:`MAXIMUM_FRAME_SIZE` — upper bound on samples per Klatt
  frame.
- :data:`SAMPLE_RATE_INCREASE` / :data:`SAMPLE_RATE_DECREASE` /
  :data:`NO_SAMPLE_RATE_CHANGE` — codes for the sample-rate change
  request a frame can carry.
"""

from __future__ import annotations

from typing import Final

MAXIMUM_FRAME_SIZE: Final[int] = 100
"""Maximum samples per Klatt frame (10ms @ 10kHz)."""

SAMPLE_RATE_INCREASE: Final[int] = 0
"""Sample-rate change code: bump rate up."""

SAMPLE_RATE_DECREASE: Final[int] = 1
"""Sample-rate change code: drop rate down."""

NO_SAMPLE_RATE_CHANGE: Final[int] = 2
"""Sample-rate change code: keep rate as-is."""

__all__ = [
    "MAXIMUM_FRAME_SIZE",
    "NO_SAMPLE_RATE_CHANGE",
    "SAMPLE_RATE_DECREASE",
    "SAMPLE_RATE_INCREASE",
]
