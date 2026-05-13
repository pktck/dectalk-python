"""Max-value-tracking helpers from vtm3.c.

Translated from ``src/dapi/src/vtm/vtm3.c`` lines 2316-2354.

Two tiny inline helpers used by the speech waveform generator's
clip-detection / overflow-tracking path:

- :func:`getmax` — folds ``abs(value)`` into a running maximum.
- :func:`checkmax` — tests whether ``|value| > checkval``
  (returns 1/0).
"""

from __future__ import annotations


def getmax(value: int, maxval: list[int]) -> None:
    """Update ``maxval[0]`` with ``abs(value)`` if larger.

    Faithful translation of:

    .. code-block:: c

        _inline void getmax(S32 value, S32 *maxval) {
            if (value < 0) value = -value;
            if (value > *maxval) *maxval = value;
            return;
        }

    The C signature uses ``S32 *`` for the in-place mutated
    tracker; Python uses the single-element ``list[int]``
    pattern for ABI parity.

    Args:
        value: Sample value to track (signed).
        maxval: Single-element list wrapping the running maximum.
    """
    if value < 0:
        value = -value
    maxval[0] = max(maxval[0], value)


def checkmax(value: int, checkval: int) -> int:
    """Return 1 if ``|value| > checkval``, else 0.

    Faithful translation of:

    .. code-block:: c

        _inline int checkmax(S32 value, S32 checkval) {
            if (value > checkval || value < (-checkval))
                return(1);
            else
                return(0);
        }

    The C source has an alternative ``abs()`` form in an
    ``#if 0`` block; the active code uses two explicit
    comparisons.

    Args:
        value: Sample value to test (signed).
        checkval: Magnitude threshold (non-negative).

    Returns:
        ``1`` if the value's magnitude exceeds the threshold,
        otherwise ``0``.
    """
    if value > checkval or value < -checkval:
        return 1
    return 0


__all__ = ["checkmax", "getmax"]
