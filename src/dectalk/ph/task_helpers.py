"""Pure helper functions from the PH task layer.

Translated from ``src/dapi/src/ph/ph_task.c``:

- :func:`deadstop` — three-argument clamp ``max(low, min(high, value))``.
  Used throughout the PH module to keep computed quantities (F0
  multipliers, gain offsets, etc.) inside a safe range.
- :func:`mstofr` — convert milliseconds to "frames" (multiply by 10,
  then divide by 64 via right shift 6). At 11025 Hz with NSAMP_FRAME=64
  the frame rate is ≈ 172.27 frames/sec; 10/64 = 0.15625 is the
  ms→frame conversion factor.
"""

from __future__ import annotations


def deadstop(value: int, low: int, high: int) -> int:
    """Clamp ``value`` to the interval ``[low, high]``.

    Faithful translation of:

    .. code-block:: c

        int deadstop(int value, int low, int high) {
            if (value < low)  return (low);
            if (value > high) return (high);
            return (value);
        }

    Args:
        value: Value to clamp.
        low: Lower bound.
        high: Upper bound.

    Returns:
        ``low`` if ``value < low``, ``high`` if ``value > high``,
        ``value`` otherwise.
    """
    if value < low:
        return low
    if value > high:
        return high
    return value


def mstofr(nms: int) -> int:
    """Convert milliseconds to PH frame count.

    Faithful translation of:

    .. code-block:: c

        int mstofr(int nms) {
            S32 temp = (S32) nms;
            temp *= 10;
            return ((int) (temp >> 6));
        }

    The fixed point is ``ms * 10 / 64`` — i.e. one frame every
    6.4 ms (≈ 156.25 fps in the C code, the value the PH module's
    duration arithmetic expects).

    Args:
        nms: Duration in milliseconds.

    Returns:
        Equivalent duration in PH frames (integer, truncated toward
        zero for non-negative inputs).
    """
    return (nms * 10) >> 6


__all__ = ["deadstop", "mstofr"]
