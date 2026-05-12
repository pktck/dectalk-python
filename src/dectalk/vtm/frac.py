"""Fixed-point multiplication helpers from the VTM Klatt synthesiser.

Translated from ``src/dapi/src/vtm/viphdefs.h``:

- :func:`frac1mul` — Q15 fixed-point multiplication (shift right 15).
  The original C macro is ``#define frac1mul(x,y) (((x)*(S32)(y))>>15)``.
  Used for noise-spectrum lowpass filtering and aspiration modulation.
- :func:`frac4mul` — Q12 fixed-point multiplication (shift right 12).
  The original C macro is ``#define frac4mul(x,y) (((x)*(S32)(y))>>12)``.
  Used throughout the formant resonator setup.

The VTM uses Q12 fixed-point for most formant gains and Q15 for
filter coefficients that need finer resolution. The widening
``S32`` cast prevents overflow when the inputs are near full scale.

These helpers preserve C-style modular arithmetic — Python's
unbounded ints wrap to 16-bit / 32-bit signed via :func:`numpy.int16`
/ :func:`numpy.int32` semantics. Most call sites already pre-clamp
the inputs, so the wraparound is purely defensive.
"""

from __future__ import annotations

_INT16_MASK = 0xFFFF
_INT32_MASK = 0xFFFFFFFF
_INT16_SIGN = 0x8000
_INT32_SIGN = 0x80000000


def _to_s16(x: int) -> int:
    """Sign-extend a 16-bit value: wrap into ``[-32768, 32767]``."""
    x &= _INT16_MASK
    return x - (_INT16_MASK + 1) if x & _INT16_SIGN else x


def _to_s32(x: int) -> int:
    """Sign-extend a 32-bit value: wrap into ``[-2**31, 2**31-1]``."""
    x &= _INT32_MASK
    return x - (_INT32_MASK + 1) if x & _INT32_SIGN else x


def frac4mul(x: int, y: int) -> int:
    """Return ``(x * y) >> 12`` with C ``short * S32`` semantics.

    Faithful translation of the C macro:

    .. code-block:: c

        #define frac4mul(x,y)  (((x)*(S32)(y))>>12)

    Both operands are 16-bit signed in the C source (typically the
    resonator radius ``r`` and a coefficient or another formant
    parameter), but the cast widens the product to 32 bits before
    the arithmetic right-shift to avoid overflow.

    Python's ``>>`` on a negative int is an arithmetic shift, matching
    C on every conventional platform (gcc, clang, MSVC). The Python
    port therefore behaves identically without explicit sign handling
    in the common case.

    Args:
        x: 16-bit signed multiplicand.
        y: 16-bit signed multiplicand.

    Returns:
        The 32-bit signed product ``(x * y) >> 12``.
    """
    # Mirror the C cast pattern: x is short, y is widened to S32.
    a = _to_s16(x)
    b = _to_s32(y)
    return (a * b) >> 12


def frac1mul(x: int, y: int) -> int:
    """Return ``(x * y) >> 15`` with C ``short * S32`` semantics.

    Faithful translation of the C macro:

    .. code-block:: c

        #define frac1mul(x,y)  (((x)*(S32)(y))>>15)

    Same widen-then-shift pattern as :func:`frac4mul` but with a Q15
    scale (32768 represents 1.0 instead of 4096). Used by the
    noise-source lowpass and aspiration-modulation paths in the VTM.

    Args:
        x: 16-bit signed multiplicand.
        y: 16-bit signed multiplicand.

    Returns:
        The 32-bit signed product ``(x * y) >> 15``.
    """
    a = _to_s16(x)
    b = _to_s32(y)
    return (a * b) >> 15


__all__ = ["frac1mul", "frac4mul"]
