"""Approximate cosine for F0 contour smoothing.

Translated from ``src/dapi/src/ph/ph_drwt01.c`` — the
``getcosine(time)`` function the PH module's F0 trajectory smoother
uses to interpolate impulse / step / glide F0 gestures over time.

The function uses a 4096-step "time" representation where:

- ``time = 0`` corresponds to angle 0
- ``time = PIOVER2 = 1024`` corresponds to π/2
- ``time = PI = 2048`` corresponds to π
- ``time = TWOPI = 4096`` corresponds to 2π

The cosine is approximated as ``ONE - temptime²`` where
``ONE = PIOVER2² = 1024² = 1048576`` and ``temptime`` is the
folded-into-[0, π/2] argument. Sign flipping handles the four
quadrants. The returned scale is 0..ONE (max), with negative values
for the lower half.

This is a pure integer-arithmetic function — no floating-point
hardware required, ideal for the embedded PH module.
"""

from __future__ import annotations

from typing import Final

TWOPI: Final[int] = 4096
PI: Final[int] = 2048
PIOVER2: Final[int] = 1024
ONE: Final[int] = PIOVER2 * PIOVER2  # = 1048576

DT_ONE: Final[int] = PIOVER2 * PIOVER2
"""C-source alias for :data:`ONE` (named ``DT_ONE`` in ph_drwt02.c)."""

HIGHEST_F0: Final[int] = 5121
"""Maximum F0 in Hz x 10 — the intonation engine clips above this."""

LOWEST_F0: Final[int] = 500
"""Minimum F0 in Hz x 10 — the intonation engine clips below this."""

F_SEG_LOWPASS: Final[int] = 3000
"""Nominal cutoff frequency of the 1-pole segmental low-pass filter."""

DELAY_SEG_LOWPASS: Final[int] = 3
"""Delay in frames to the half-way point of the segmental low-pass step
response."""

F0SHFT: Final[int] = 3
"""Bit shift used to avoid rounding errors in F0 calculations."""


def getcosine(time: int) -> int:
    """Approximate ``cos(angle) * ONE`` where ``angle = time * 2π / TWOPI``.

    Faithful translation of:

    .. code-block:: c

        int getcosine(short time) {
            short temptime;
            int   cosine;

            if (time > PI)         time = TWOPI - time;
            temptime = time;
            if (temptime > PIOVER2) temptime = PI - temptime;
            cosine = (temptime * temptime) - ONE;
            if (time != temptime) return (cosine);
            else                  return (-cosine);
        }

    Args:
        time: Integer in ``[0, 4096)``; values outside the canonical
            range produce undefined-but-deterministic output (the
            C source clamps via wraparound semantics, not range check).

    Returns:
        Integer in roughly ``[-ONE, +ONE]`` — the cosine value scaled
        by ``ONE`` (signed). For example ``getcosine(0) == ONE`` and
        ``getcosine(PI) == -ONE``.
    """
    # Fold time into [0, PI] (the C "pi-reversed" handling).
    if time > PI:
        time = TWOPI - time

    temptime = time
    # Fold temptime into [0, PIOVER2].
    if temptime > PIOVER2:
        temptime = PI - temptime

    # Approximate cosine as -ONE + temptime² when crossing the half-cycle,
    # +ONE - temptime² when on the same half.
    cosine = (temptime * temptime) - ONE
    if time != temptime:
        # Upper half — cosine value is already correctly negated.
        return cosine
    # Lower half — flip the sign.
    return -cosine


__all__ = [
    "DELAY_SEG_LOWPASS",
    "DT_ONE",
    "F0SHFT",
    "F_SEG_LOWPASS",
    "HIGHEST_F0",
    "LOWEST_F0",
    "ONE",
    "PI",
    "PIOVER2",
    "TWOPI",
    "getcosine",
]
