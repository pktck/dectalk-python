"""Pure helper functions from the PH task layer.

Translated from ``src/dapi/src/ph/ph_task.c`` and ph_defs.h:

- :func:`deadstop` — three-argument clamp ``max(low, min(high, value))``.
  Used throughout the PH module to keep computed quantities (F0
  multipliers, gain offsets, etc.) inside a safe range.
- :func:`mstofr` — convert milliseconds to "frames" (multiply by 10,
  then divide by 64 via right shift 6). The C source's ph_task.c
  ``mstofr()`` function form.
- :func:`mstofr_macro` — the ph_defs.h MSTOFR macro variant,
  ``((ms + 4) * 10) / NSAMP_FRAME``.
- :func:`frtoms` — inverse of MSTOFR: convert frames to milliseconds
  via ``(frames * NSAMP_FRAME + 5) / 10``.
"""

from __future__ import annotations

from dectalk.ph.numeric_constants import NSAMP_FRAME


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


def mstofr_macro(msec: int) -> int:
    """Convert milliseconds to frames using the ph_defs.h MSTOFR macro.

    Faithful translation of:

    .. code-block:: c

        #define MSTOFR(msec)    (((msec+4)*10)/NSAMP_FRAME)

    Differs from :func:`mstofr` (the function form) in two ways:

    1. Rounds the input up by 4 ms before scaling.
    2. Divides by :data:`NSAMP_FRAME` (= 71 at 11 kHz) rather than
       the hardcoded 64 used by ``mstofr()``.

    Args:
        msec: Duration in milliseconds.

    Returns:
        Equivalent duration in PH frames.
    """
    return ((msec + 4) * 10) // NSAMP_FRAME


def frtoms(frames: int) -> int:
    """Convert PH frame count to milliseconds.

    Faithful translation of:

    .. code-block:: c

        #define frtoms(x)       ((((x) * NSAMP_FRAME)+5)/10)

    Inverse of :func:`mstofr_macro` (rounds output up by 0.5 ms).

    Args:
        frames: PH frame count.

    Returns:
        Equivalent duration in milliseconds.
    """
    return (frames * NSAMP_FRAME + 5) // 10


__all__ = ["deadstop", "frtoms", "mstofr", "mstofr_macro"]
