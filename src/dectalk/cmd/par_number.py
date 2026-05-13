"""Number-conversion helpers from the parser.

Translated from ``src/dapi/src/cmd/par_pars.c``:

- :func:`par_convert_number` — atoi-equivalent with a fixed-length
  scan ceiling.
- :func:`par_convert_number_new` — atoi + reports digits consumed.
- :func:`par_convert_number_new2` — fastest variant, scans until
  the first non-digit. The C comment claims 10-20% faster than atoi().
- :func:`par_convert_hex_number` — parse ``"0x..."`` hex digits.
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


def par_convert_hex_number(string: str | bytes, num: int) -> int:
    """Return the integer value of ``"0x..."`` hex digits, or -1 on error.

    Faithful translation of:

    .. code-block:: c

        short par_convert_hex_number(unsigned char *string, int num) {
            register short total = 0, temp = 0, i = 2;
            if ((*string) != '0')      return -1;
            if (*(string+1) != 'x')    return -1;
            num += 2;
            while (i < num) {
                if (string[i] > '9')   temp = string[i] - 'A' + 10;
                else                   temp = string[i] - '0';
                if ((temp < 0) || (temp > 15)) return -1;
                total = (total << 4) + temp;
                i++;
            }
            return total;
        }

    The C version is upper-case-only (``'A'-'F'`` only — no
    ``'a'-'f'``). It also doesn't bounds-check the hex digit at the
    low end: ``string[i] >= '0' && string[i] <= '9'`` is implied by
    the ``string[i] > '9'`` else-branch, but inputs like ``'/'``
    (0x2F → -1) are filtered out by the ``temp < 0`` check. We
    preserve all of these quirks faithfully.

    Args:
        string: Buffer starting with ``"0x"`` and followed by hex
            digits. Bytes or str.
        num: Number of hex digits to consume after the ``"0x"``
            prefix. The total bytes scanned is ``num + 2``.

    Returns:
        Integer value of the hex digits, or ``-1`` if the prefix
        isn't ``"0x"`` or any byte isn't a valid hex digit.
    """
    buf = _as_bytes(string)
    if not buf or buf[0] != ord("0"):
        return -1
    if len(buf) < 2 or buf[1] != ord("x"):  # noqa: PLR2004 — "0x" prefix
        return -1
    total = 0
    nine = ord("9")
    a_upper = ord("A")
    zero = ord("0")
    end = num + 2
    for i in range(2, end):
        if i >= len(buf):
            return -1
        byte = buf[i]
        temp = byte - a_upper + 10 if byte > nine else byte - zero
        if temp < 0 or temp > 15:  # noqa: PLR2004 — hex digit range
            return -1
        total = (total << 4) + temp
    return total


def par_get_int_length(i: int) -> int:
    """Return the decimal digit-count of a non-negative integer.

    Faithful translation of:

    .. code-block:: c

        int par_get_int_length(register int i) {
            if (i < 10)    return 1;
            else if (i < 100)   return 2;
            else if (i < 1000)  return 3;
            else if (i < 10000) return 4;
            else                return 5;
        }

    Per the C source: ``the number zero has a length of 1`` and
    ``this function only converts positive numbers correctly``.
    The Python port preserves both quirks — values >= 100000 still
    return 5 (the C source caps out at 5 digits), and negative
    inputs are not specially handled.

    Args:
        i: Non-negative integer.

    Returns:
        Number of decimal digits in ``i`` (1..5, capped at 5).
    """
    if i < 10:  # noqa: PLR2004 — digit range constants
        return 1
    if i < 100:  # noqa: PLR2004
        return 2
    if i < 1000:  # noqa: PLR2004
        return 3
    if i < 10000:  # noqa: PLR2004
        return 4
    return 5


__all__ = [
    "par_convert_hex_number",
    "par_convert_number",
    "par_convert_number_new",
    "par_convert_number_new2",
    "par_get_int_length",
]
