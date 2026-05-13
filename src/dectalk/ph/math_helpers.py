"""PH math helper macros from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h`` lines 759-774
(the non-MSDOS branch). The C source defines two scaling macros
used throughout the PH module's timing and prosody arithmetic:

- :func:`muldv` — ``(x * y) / z`` with a 32-bit intermediate.
  Used to scale a base value by a ratio of two 16-bit numbers
  without overflow when ``x * y`` exceeds ``2**15``.
- :func:`mlsh1` — ``(x * y) >> 14`` truncated to ``short``.
  A Q14 fixed-point multiplication; ``16384`` represents 1.0.

Both helpers replicate the C macros' modular arithmetic: the
inputs are sign-extended into 16-bit / 32-bit signed ranges and
the result of :func:`mlsh1` is truncated back to 16-bit signed
just like a C ``short`` cast.
"""

from __future__ import annotations

_INT16_MASK = 0xFFFF
_INT32_MASK = 0xFFFFFFFF
_INT16_SIGN = 0x8000
_INT32_SIGN = 0x80000000


def _to_s16(x: int) -> int:
    """Sign-extend an int into the 16-bit signed range."""
    x &= _INT16_MASK
    return x - (_INT16_MASK + 1) if x & _INT16_SIGN else x


def _to_s32(x: int) -> int:
    """Sign-extend an int into the 32-bit signed range."""
    x &= _INT32_MASK
    return x - (_INT32_MASK + 1) if x & _INT32_SIGN else x


def muldv(x: int, y: int, z: int) -> int:
    """Return ``(x * y) / z`` with C ``S32`` intermediate semantics.

    Faithful translation of:

    .. code-block:: c

        #define muldv(x, y, z) (((S32)(x) * (S32)(y)) / (S32)(z))

    The C macro widens both ``x`` and ``y`` to ``S32`` (long, 32-bit
    signed) before multiplying, which lets the product safely exceed
    ``2**15`` as long as it fits in 32 bits. The Python port uses
    Python's native arbitrary-precision int and divides with C's
    truncate-toward-zero semantics (``int(a / b)``).

    Args:
        x: First factor (16-bit signed in C).
        y: Second factor (16-bit signed in C).
        z: Divisor (16-bit signed in C, non-zero).

    Returns:
        The 32-bit signed value ``(x * y) / z`` (truncated toward
        zero, matching C integer division).
    """
    a = _to_s32(x)
    b = _to_s32(y)
    c = _to_s32(z)
    product = a * b
    # C integer division truncates toward zero, but Python's // floors.
    # Use int(a/b) only when result fits in a float; otherwise fall back
    # to absolute-value divide + sign restore.
    if (product < 0) ^ (c < 0):
        return -(abs(product) // abs(c))
    return abs(product) // abs(c)


def mlsh1(x: int, y: int) -> int:
    """Return ``(short)((x * y) >> 14)`` — Q14 fixed-point multiply.

    Faithful translation of:

    .. code-block:: c

        #define mlsh1(x, y) (S16)(((S32)((S32)(x) * (S32)(y))) >> ((S32)14))

    The C macro casts both operands to 32-bit signed, multiplies,
    shifts the result right by 14, and truncates back to 16-bit
    signed. This is the standard Q14 fixed-point multiplication used
    throughout the PH module (``FRAC_ONE = 16384`` represents 1.0).

    Args:
        x: 16-bit signed multiplicand.
        y: 16-bit signed multiplicand.

    Returns:
        The 16-bit signed result of ``(x * y) >> 14``.
    """
    a = _to_s32(x)
    b = _to_s32(y)
    return _to_s16((a * b) >> 14)


__all__ = ["mlsh1", "muldv"]
