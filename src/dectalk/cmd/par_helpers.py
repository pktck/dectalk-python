"""Pure helper functions from the CMD parser layer.

Translated from ``src/dapi/src/cmd/par_pars.c``:

- :func:`par_get_int_length` — count the decimal digits in a small
  positive integer. Special-cases 0 → 1. Used by the parser when
  formatting numeric command parameters.
"""

from __future__ import annotations


def par_get_int_length(i: int) -> int:
    """Return the number of decimal digits in ``i``.

    Faithful translation of ``par_get_int_length`` from
    ``src/dapi/src/cmd/par_pars.c``:

    .. code-block:: c

        short par_get_int_length(short i) {
            int j;
            if (i == 0) return 1;
            for (j = 0; i; j++) i /= 10;
            return j;
        }

    The C version is documented to "only [convert] positive numbers
    correctly". Python preserves that contract: negative inputs use
    the same loop, which for Python's arbitrary-precision int still
    converges (unlike C's overflow on INT_MIN/10).

    Args:
        i: Integer to measure. The C source's contract is positive
            inputs; ``0`` is special-cased to return 1.

    Returns:
        Decimal-digit count of ``|i|`` (≥ 1).
    """
    if i == 0:
        return 1
    j = 0
    while i:
        i //= 10
        j += 1
    return j


__all__ = ["par_get_int_length"]
