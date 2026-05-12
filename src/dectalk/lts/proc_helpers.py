"""Pure helper functions from the LTS number/proc pipeline.

Translated from ``src/dapi/src/lts/l_us_pr1.c``. These two helpers
have no TTS-handle dependency and operate purely on their inputs:

- :func:`ls_proc_is_a_part` — return False for digit/separator
  characters (``-``, ``/``, ``0``..``9``), True otherwise. Used by
  number-processing to decide when a character is a "part marker"
  (part of a phone/serial-number sequence).
- :func:`ls_proc_non_zero` — scan the first ``n`` characters of a
  buffer and return True if any is not ASCII ``'0'``. Used by
  number expansion to skip leading zeros.
"""

from __future__ import annotations


def ls_proc_is_a_part(c: int) -> bool:
    """Return True iff ``c`` is **not** one of ``-``, ``/``, or a digit.

    Faithful translation of the C ``ls_proc_is_a_part`` function:

    .. code-block:: c

        int ls_proc_is_a_part(int c)
        {
            if (c == '-' || c == '/' || (c >= '0' && c <= '9'))
                return (FALSE);
            return (TRUE);
        }

    Args:
        c: Single character byte value (0..255).

    Returns:
        ``False`` if ``c`` is ``-``, ``/``, or in ``0``..``9``;
        ``True`` otherwise.
    """
    return not (c == ord("-") or c == ord("/") or (ord("0") <= c <= ord("9")))


def ls_proc_non_zero(p: bytes, n: int) -> bool:
    """Return True iff any of the first ``n`` bytes of ``p`` is not ``'0'``.

    Faithful translation of:

    .. code-block:: c

        int ls_proc_non_zero(char *p, int n)
        {
            while (n--) {
                if (*p != '0')
                    return (TRUE);
                ++p;
            }
            return (FALSE);
        }

    Args:
        p: Byte buffer to scan.
        n: Number of bytes to examine from the start.

    Returns:
        ``True`` if any of the first ``n`` bytes is not ASCII ``'0'``
        (0x30); ``False`` if all are ``'0'`` or ``n <= 0``.
    """
    zero = ord("0")
    return any(p[i] != zero for i in range(n))


__all__ = ["ls_proc_is_a_part", "ls_proc_non_zero"]
