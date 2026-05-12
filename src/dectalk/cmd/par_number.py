"""Number-conversion helpers from the parser.

Translated from ``src/dapi/src/cmd/par_pars.c``:

- :func:`par_convert_number` — atoi-equivalent with a fixed-length
  scan ceiling.
- :func:`par_convert_number_new` — atoi + reports digits consumed.
- :func:`par_convert_number_new2` — fastest variant, scans until
  the first non-digit. The C comment claims 10-20% faster than atoi().
"""

from __future__ import annotations


def _as_bytes(string: str | bytes) -> bytes:
    return string.encode("latin-1", errors="replace") if isinstance(string, str) else string


def par_convert_number(string: str | bytes, num: int) -> int:
    """Return the integer value of the first ``num`` digits in ``string``.

    Faithful translation of:

    .. code-block:: c

        short par_convert_number(unsigned char *string, short num) {
            register int i, total = 0, temp;
            for (i = 0; i < num; i++) {
                temp = string[i] - '0';
                if ((temp < 0) || (temp > 9))
                    return total;
                total = total * 10 + temp;
            }
            return total;
        }

    Args:
        string: Buffer to scan. Bytes or str.
        num: Maximum number of bytes to consume.

    Returns:
        Integer value of the leading digit run, capped at ``num``
        bytes. Stops early at the first non-digit byte.
    """
    buf = _as_bytes(string)
    total = 0
    zero = ord("0")
    for i in range(num):
        if i >= len(buf):
            break
        temp = buf[i] - zero
        if temp < 0 or temp > 9:  # noqa: PLR2004 — digit range constant
            return total
        total = total * 10 + temp
    return total


def par_convert_number_new(string: str | bytes) -> tuple[int, int]:
    """Return ``(value, length)`` for the leading decimal integer.

    Faithful translation of:

    .. code-block:: c

        short par_convert_number_new(unsigned char *string, short *length) {
            register int i, total = 0, temp;
            for (i = 0; ; i++) {
                temp = string[i] - '0';
                if ((temp < 0) || (temp > 9)) {
                    *length = i;
                    return total;
                }
                total = total * 10 + temp;
            }
        }

    The C function returns the integer through its return value and the
    digit count through ``*length``. The Python version returns the
    pair directly. The C comment claims this is ~40% faster than atoi
    + a separate length probe.

    Args:
        string: Buffer to scan. Bytes or str.

    Returns:
        ``(value, length)`` where ``value`` is the integer value of
        the leading digit run and ``length`` is the number of bytes
        consumed before the first non-digit.
    """
    buf = _as_bytes(string)
    total = 0
    zero = ord("0")
    for i, byte in enumerate(buf):
        temp = byte - zero
        if temp < 0 or temp > 9:  # noqa: PLR2004 — digit range constant
            return total, i
        total = total * 10 + temp
    return total, len(buf)


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
    buf = _as_bytes(string)
    total = 0
    zero = ord("0")
    for byte in buf:
        temp = byte - zero
        if temp < 0 or temp > 9:  # noqa: PLR2004 — digit range constant
            return total
        total = total * 10 + temp
    return total


__all__ = ["par_convert_number", "par_convert_number_new", "par_convert_number_new2"]
