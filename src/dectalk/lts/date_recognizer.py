"""Date-pattern recognition from l_us_pr1.c.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_is_date` — return True iff the byte slice spells
  a date in one of the formats ``D-Mon``, ``DD-Mon``, ``D-Mon-YY``,
  ``DD-Mon-YY``, ``D-Mon-YYYY``, ``DD-Mon-YYYY`` (e.g. ``23-Aug-84``,
  ``5-Jan-2025``).
"""

from __future__ import annotations

from dectalk.lts.char_features import is_alpha, is_digit
from dectalk.lts.phoneme_words import months

_MONTH_LEN = 3  # months[] entries are all 3-byte abbreviations


def ls_proc_is_date(word: str | bytes) -> bool:  # noqa: PLR0911, PLR0912 — mirrors the C state machine
    """Return True iff ``word`` spells a date.

    Faithful translation of:

    .. code-block:: c

        int ls_proc_is_date(LETTER *llp, LETTER *rlp) {
            short buf[3];
            int i;

            // First digit.
            if (!IS_DIGIT(llp->l_ch) || ++llp == rlp) return FALSE;
            // Optional second digit.
            if (llp->l_ch != '-') {
                if (!IS_DIGIT(llp->l_ch) || ++llp == rlp) return FALSE;
                if (llp->l_ch != '-') return FALSE;
            }
            // Three alpha characters (month abbreviation).
            if (++llp == rlp || !IS_ALPHA(llp->l_ch)) return FALSE;
            buf[0] = llp->l_ch;
            // ... two more alphas ...
            // Match against months[12].
            // Then optional `-YY` or `-YYYY`.
            // ...
            return TRUE;
        }

    The C source mutates ``llp`` in place; the Python port walks an
    index instead. Behaviour is otherwise identical: case-sensitive
    month match (must match :data:`months` bytes), 1- or 2-digit day,
    optional 2- or 4-digit year.

    Accepted formats (case-sensitive on the month):
    * ``D-Mon`` (e.g. ``5-Jan``)
    * ``DD-Mon`` (e.g. ``23-Aug``)
    * ``D-Mon-YY`` / ``DD-Mon-YY``
    * ``D-Mon-YYYY`` / ``DD-Mon-YYYY``

    Args:
        word: Byte slice to test. ``str`` is Latin-1 encoded.

    Returns:
        ``True`` iff the entire slice matches one of the date forms.
    """
    buf = word.encode("latin-1", errors="replace") if isinstance(word, str) else word
    n = len(buf)
    if n == 0:
        return False

    # First digit (required).
    if not is_digit(buf[0]):
        return False
    i = 1
    if i == n:
        return False

    # Optional second digit, then required '-'.
    if buf[i] != ord("-"):
        if not is_digit(buf[i]):
            return False
        i += 1
        if i == n:
            return False
        if buf[i] != ord("-"):
            return False

    # Three alphabetic characters (month abbreviation).
    i += 1  # past '-'
    if i == n or not is_alpha(buf[i]):
        return False
    month0 = buf[i]
    i += 1
    if i == n or not is_alpha(buf[i]):
        return False
    month1 = buf[i]
    i += 1
    if i == n or not is_alpha(buf[i]):
        return False
    month2 = buf[i]
    i += 1

    # Validate against months[].
    found = any(
        len(m) >= _MONTH_LEN and m[0] == month0 and m[1] == month1 and m[2] == month2
        for m in months
    )
    if not found:
        return False

    # End of input → bare ``D-Mon`` form is valid.
    if i == n:
        return True

    # Must be '-' followed by 2 or 4 digit year.
    if buf[i] != ord("-"):
        return False
    i += 1
    if i == n or not is_digit(buf[i]):
        return False
    i += 1
    if i == n or not is_digit(buf[i]):
        return False
    i += 1
    if i == n:
        return True  # YY form

    # 4-digit year — need 2 more digits.
    if not is_digit(buf[i]):
        return False
    i += 1
    if i == n:
        return False
    if not is_digit(buf[i]):
        return False
    i += 1
    return i == n  # must be exactly 4 digits


__all__ = ["ls_proc_is_date"]
