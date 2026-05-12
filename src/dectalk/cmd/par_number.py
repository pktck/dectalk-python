"""Number-conversion helpers from the parser.

Translated from ``src/dapi/src/cmd/par_pars.c``:

- :func:`par_convert_number_new2` — fast atoi-equivalent that scans
  ASCII digits from the start of a buffer until a non-digit, returning
  the integer value. The C comment claims 10-20% faster than atoi().
"""

from __future__ import annotations


def par_convert_number_new2(string: str | bytes) -> int:
    """Return the leading decimal integer in ``string`` (0 if no digits).

    Faithful translation of:

    .. code-block:: c

        short par_convert_number_new2(unsigned char *string) {
            register int i, total = 0, temp;
            for (i = 0; ; i++) {
                temp = string[i] - '0';
                if ((temp < 0) || (temp > 9))
                    return total;
                total = total * 10 + temp;
            }
        }

    Args:
        string: Buffer to scan. Bytes or str.

    Returns:
        Integer value of the longest leading run of ASCII digits.
        Returns 0 if the buffer is empty or doesn't start with a digit.
    """
    buf = string.encode("latin-1", errors="replace") if isinstance(string, str) else string
    total = 0
    zero = ord("0")
    for byte in buf:
        temp = byte - zero
        if temp < 0 or temp > 9:  # noqa: PLR2004 — digit range constant
            return total
        total = total * 10 + temp
    return total


__all__ = ["par_convert_number_new2"]
