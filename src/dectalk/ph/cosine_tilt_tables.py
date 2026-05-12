"""Cosine-LUT and TILT-linearisation tables from ph_romi.c.

Translated from ``src/dapi/src/ph/ph_romi.c``:

- :data:`getcosine_tab` — 64-entry signed-short cosine lookup
  table. Indexed by an angle 0..63 representing 0..2π; values are
  in -164..+164 (roughly cos times 164). Used by the VTM's pitch
  perturbation / vibrato loops.

  Note: distinct from the :func:`~dectalk.ph.getcosine.getcosine`
  function in :mod:`dectalk.ph.getcosine`, which is a finer-grained
  cosine approximation for a 0..TWOPI=4096 angle range. Both come
  from the same C source family and serve different consumers.

- :data:`lineartilt` — 32-entry table that converts a user-requested
  TILT (dB) into the value the chip expects. The C source comment
  notes: "if you request 3 dB of tilt, must send 12 to chip to get 3".
"""

from __future__ import annotations

from typing import Final

getcosine_tab: Final[tuple[int, ...]] = (
    164, 163, 161, 158, 154, 148, 141, 132,
    123, 112, 100, 86, 72, 56, 38, 20,
    0, -20, -38, -56, -72, -86, -100, -112,
    -123, -132, -141, -148, -154, -158, -161, -163,
    -164, -163, -161, -158, -154, -148, -141, -132,
    -123, -112, -100, -86, -72, -56, -38, -20,
    0, 20, 38, 56, 72, 86, 100, 112,
    123, 132, 141, 148, 154, 158, 161, 163,
)  # fmt: skip
"""64-entry signed-short cosine LUT covering 0..2π."""


lineartilt: Final[tuple[int, ...]] = (
    0, 6, 8, 12, 15, 17, 19, 21, 23, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
    35, 36, 36, 37, 37, 38, 38, 39, 39, 39,
    40, 40,
)  # fmt: skip
"""32-entry table linearising the user-facing TILT dB into chip values."""


__all__ = ["getcosine_tab", "lineartilt"]
