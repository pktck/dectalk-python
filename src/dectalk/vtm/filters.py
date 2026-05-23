"""Fixed-point biquad filter primitives from vtmfunci.h.

Translated from ``src/dapi/src/vtm/vtmfunci.h``. The C macros expand
inline; the Python translations return the new delay-line state as
tuples so the caller can re-bind locals.

All three filters operate in Q12 fixed-point.
"""

from __future__ import annotations

__all__ = ["two_pole_filter", "two_zero_filter", "two_zero_filter_2"]


def two_pole_filter(
    tp_input: int,
    tp_delay_1: int,
    tp_delay_2: int,
    tp_a: int,
    tp_b: int,
    tp_c: int,
) -> tuple[int, int]:
    """Return ``(new_delay_1, new_delay_2)`` after one biquad step.

    Faithful translation of the ``vtmfunci.h`` ``two_pole_filter``
    macro (lines 76-88). ``new_delay_1`` is the resonator's current
    output sample; ``new_delay_2`` is the previous ``tp_delay_1``.

    Args:
        tp_input: Input sample.
        tp_delay_1: Previous output sample.
        tp_delay_2: Second-previous output sample.
        tp_a: Q12 ``a`` coefficient (gain).
        tp_b: Q12 ``b`` coefficient (first-order feedback).
        tp_c: Q12 ``c`` coefficient (second-order feedback).

    Returns:
        ``(new_delay_1, new_delay_2)``.
    """
    temp1 = tp_c * tp_delay_2
    new_delay_2 = tp_delay_1
    temp1 += tp_b * tp_delay_1
    temp1 += tp_a * tp_input
    new_delay_1 = temp1 >> 12
    return new_delay_1, new_delay_2


def two_zero_filter(
    tz_input: int,
    tz_delay_1: int,
    tz_delay_2: int,
    tz_a: int,
    tz_b: int,
    tz_c: int,
) -> tuple[int, int, int]:
    """Return ``(output, new_delay_1, new_delay_2)`` after one FIR step.

    Faithful translation of the ``vtmfunci.h`` ``two_zero_filter``
    macro (lines 40-52). ``new_delay_1`` is the current input;
    ``new_delay_2`` catches the *old* ``delay_1`` (not ``tz_input``).

    Args:
        tz_input: Input sample.
        tz_delay_1: Previous input sample.
        tz_delay_2: Second-previous input sample.
        tz_a: Q12 ``a`` coefficient.
        tz_b: Q12 ``b`` coefficient.
        tz_c: Q12 ``c`` coefficient.

    Returns:
        ``(tz_output, new_delay_1, new_delay_2)``.
    """
    temp1 = tz_c * tz_delay_2
    temp1 += tz_b * tz_delay_1
    temp1 += tz_a * tz_input
    new_delay_2 = tz_delay_1
    new_delay_1 = tz_input
    tz_output = temp1 >> 12
    return tz_output, new_delay_1, new_delay_2


def two_zero_filter_2(
    tz_input: int,
    tz_delay_1: int,
    tz_delay_2: int,
    tz_b: int,
    tz_c: int,
) -> tuple[int, int, int]:
    """Return ``(new_input, new_delay_1, new_delay_2)`` after one step.

    Faithful translation of the ``vtmfunci.h`` ``two_zero_filter_2``
    macro (lines 61-70). Three-zero FIR with the ``a`` coefficient
    hardcoded to 1.0 (= 4096 in Q12). Used by the Pi-rotated
    antiresonator on the noise source.

    Args:
        tz_input: Input sample.
        tz_delay_1: Previous input sample.
        tz_delay_2: Second-previous input sample.
        tz_b: Q12 ``b`` coefficient.
        tz_c: Q12 ``c`` coefficient.

    Returns:
        ``(new_input, new_delay_1, new_delay_2)``.
    """
    temp0 = tz_c * tz_delay_2
    temp0 += tz_b * tz_delay_1
    new_delay_2 = tz_delay_1
    new_delay_1 = tz_input
    new_input = tz_input + (temp0 >> 12)
    return new_input, new_delay_1, new_delay_2
