"""Millisecond-to-frame-count constants from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h`` lines 407-426 — the
``NFxxMS`` table converts common millisecond durations into PH
output-frame counts at the canonical 10 kHz / 11.025 kHz frame
rate. The values aren't strictly ``ms / 6.43`` rounds — the C
source picks integers that work well with the PH timing engine's
per-segment budget arithmetic.
"""

from __future__ import annotations

from typing import Final

NF7MS: Final[int] = 1
"""Number of frames in 7 ms."""

NF15MS: Final[int] = 2
"""Number of frames in 15 ms."""

NF20MS: Final[int] = 3
"""Number of frames in 20 ms."""

NF25MS: Final[int] = 4
"""Number of frames in 25 ms."""

NF30MS: Final[int] = 5
"""Number of frames in 30 ms."""

NF40MS: Final[int] = 6
"""Number of frames in 40 ms."""

NF45MS: Final[int] = 7
"""Number of frames in 45 ms."""

NF50MS: Final[int] = 8
"""Number of frames in 50 ms."""

NF60MS: Final[int] = 9
"""Number of frames in 60 ms."""

NF64MS: Final[int] = 10
"""Number of frames in 64 ms — pause-comma / pause-period base
(actual pause is ``NF64MS`` longer than ``compause`` / ``perpause``)."""

NF70MS: Final[int] = 11
"""Number of frames in 70 ms."""

NF75MS: Final[int] = 12
"""Number of frames in 75 ms."""

NF80MS: Final[int] = 13
"""Number of frames in 80 ms."""

NF90MS: Final[int] = 14
"""Number of frames in 90 ms."""

NF100MS: Final[int] = 16
"""Number of frames in 100 ms."""

NF115MS: Final[int] = 18
"""Number of frames in 115 ms."""

NF130MS: Final[int] = 20
"""Number of frames in 130 ms."""

NF160MS: Final[int] = 25
"""Number of frames in 160 ms."""

NF480MS: Final[int] = 75
"""Number of frames in 480 ms."""

NF640MS: Final[int] = 100
"""Number of frames in 640 ms."""


__all__ = [
    "NF7MS",
    "NF15MS",
    "NF20MS",
    "NF25MS",
    "NF30MS",
    "NF40MS",
    "NF45MS",
    "NF50MS",
    "NF60MS",
    "NF64MS",
    "NF70MS",
    "NF75MS",
    "NF80MS",
    "NF90MS",
    "NF100MS",
    "NF115MS",
    "NF130MS",
    "NF160MS",
    "NF480MS",
    "NF640MS",
]
