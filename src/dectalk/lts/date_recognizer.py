"""Pattern recognisers from l_us_pr1.c.

Translated from ``src/dapi/src/lts/l_us_pr1.c``:

- :func:`ls_proc_is_date` — date-pattern recogniser
  (``D-Mon``, ``DD-Mon``, ``D-Mon-YY``, ``DD-Mon-YY``,
  ``D-Mon-YYYY``, ``DD-Mon-YYYY``; e.g. ``23-Aug-84``, ``5-Jan-2025``).
- :func:`ls_proc_is_frac` — fraction-pattern recogniser
  (``D/D``, ``DD/D``, ``D/DD``, ``DD/DD``, ``DD/DDD`` where DDD is
  100; optional trailing ``%``).
- :func:`ls_proc_is_time` — time-pattern recogniser
  (``D:DD``, ``DD:DD``, ``D:DD:DD``, ``DD:DD:DD``, plus optional
  fractional seconds like ``12:34.56`` using the locale's ``fchar``).
- :func:`ls_proc_is_am_pm` — recognise ``am``/``AM``/``pm``/``PM``.
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


_MAX_DENOM_DIGITS = 3


def ls_proc_is_frac(word: str | bytes) -> bool:  # noqa: PLR0911, PLR0912 — mirrors the C state machine
    """Return True iff ``word`` spells a fraction.

    Faithful translation of:

    .. code-block:: c

        int ls_proc_is_frac(LETTER *llp, LETTER *rlp) {
            int n;
            // First digit: non-zero.
            if (!IS_DIGIT(llp->l_ch) || llp->l_ch == '0' || ++llp == rlp)
                return FALSE;
            // Optional second digit, then required '/'.
            if (llp->l_ch != '/') {
                if (!IS_DIGIT(llp->l_ch) || ++llp == rlp) return FALSE;
                if (llp->l_ch != '/') return FALSE;
            }
            // Denominator: 1-3 digits.
            n = 0;
            while (++llp != rlp && IS_DIGIT(llp->l_ch)) {
                if (n == 0 && llp->l_ch == '0') return FALSE;  // no leading zero
                ++n;
            }
            if (n == 0 || n > 3) return FALSE;
            if (n == 3) {
                // 3-digit denominator must be "100".
                if ((llp-1)->l_ch != '0' || (llp-2)->l_ch != '0' || (llp-3)->l_ch != '1')
                    return FALSE;
            }
            // Optional trailing '%'.
            if (llp != rlp) {
                if (llp->l_ch != '%' || llp+1 != rlp) return FALSE;
            }
            return TRUE;
        }

    Accepted forms:
    * ``D/D``  (e.g. ``1/2``)
    * ``D/DD``, ``D/100`` (only 100 is valid as a 3-digit denominator)
    * ``DD/D``, ``DD/DD``, ``DD/100``
    * Any of the above with a trailing ``%``

    The numerator must be 1 or 2 ASCII digits, non-zero. The
    denominator is 1-3 digits with no leading zero; if 3 digits it
    must be exactly ``"100"``.

    Args:
        word: Byte slice to test. ``str`` is Latin-1 encoded.

    Returns:
        ``True`` iff the entire slice matches one of the fraction forms.
    """
    buf = word.encode("latin-1", errors="replace") if isinstance(word, str) else word
    n = len(buf)
    if n == 0:
        return False

    # First digit: must be digit, must be non-zero.
    if not is_digit(buf[0]):
        return False
    if buf[0] == ord("0"):
        return False
    i = 1
    if i == n:
        return False

    # Optional 2nd digit, then '/'.
    if buf[i] != ord("/"):
        if not is_digit(buf[i]):
            return False
        i += 1
        if i == n:
            return False
        if buf[i] != ord("/"):
            return False

    # Denominator: 1..3 digits, no leading zero.
    i += 1  # past '/'
    denom_start = i
    n_digits = 0
    while i < n and is_digit(buf[i]):
        if n_digits == 0 and buf[i] == ord("0"):
            return False
        n_digits += 1
        i += 1
    if n_digits == 0 or n_digits > _MAX_DENOM_DIGITS:
        return False

    # If 3 digits, must be exactly "100".
    if n_digits == _MAX_DENOM_DIGITS:
        denom = buf[denom_start : denom_start + _MAX_DENOM_DIGITS]
        if denom != b"100":
            return False

    # Optional trailing '%'.
    if i != n:
        if buf[i] != ord("%"):
            return False
        i += 1
        if i != n:
            return False

    return True


def ls_proc_is_time(word: str | bytes, fchar: int = ord(".")) -> bool:  # noqa: PLR0911, PLR0912 — mirrors the C state machine
    """Return True iff ``word`` spells a time.

    Faithful translation of:

    .. code-block:: c

        int ls_proc_is_time(PLTS_T pLts_t, LETTER *llp, LETTER *rlp) {
            // 1- or 2-digit hour, ':', 2-digit minute (always).
            // Optionally ':' then 2-digit second.
            // Optionally fchar + 1+ fractional digits.
        }

    Accepted forms:
    * ``D:DD`` / ``DD:DD``
    * ``D:DD:DD`` / ``DD:DD:DD``
    * Any of the above with ``fchar`` + 1 or more fractional digits.

    The fractional separator ``fchar`` defaults to ``'.'`` (the US
    locale value of ``pLts_t->fchar``).

    Args:
        word: Byte slice. ``str`` is Latin-1 encoded.
        fchar: Fractional-second separator (typically ``.`` in US,
            ``,`` in European locales).

    Returns:
        ``True`` iff ``word`` matches one of the time forms.
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

    # Optional 2nd digit, then required ':'.
    if buf[i] != ord(":"):
        if not is_digit(buf[i]):
            return False
        i += 1
        if i == n:
            return False
        if buf[i] != ord(":"):
            return False

    # Past ':' — 2 digits required for minutes.
    i += 1
    if i == n or not is_digit(buf[i]):
        return False
    i += 1
    if i == n or not is_digit(buf[i]):
        return False
    i += 1
    if i == n:
        return True  # DD:DD or D:DD form

    # Optional ':DD' for seconds.
    if buf[i] == ord(":"):
        i += 1
        if i == n or not is_digit(buf[i]):
            return False
        i += 1
        if i == n or not is_digit(buf[i]):
            return False
        i += 1

    # Optional fchar + 1 or more fractional digits.
    if i != n and buf[i] == fchar:
        i += 1
        if i == n or not is_digit(buf[i]):
            return False
        i += 1
        while i < n and is_digit(buf[i]):
            i += 1

    return i == n


_AM_PM_LENGTH = 2


def ls_proc_is_am_pm(word: str | bytes) -> bool:
    """Return True iff ``word`` is ``am`` or ``pm`` (any case).

    Faithful translation of:

    .. code-block:: c

        int ls_proc_is_am_pm(LETTER *llp, LETTER *rlp) {
            if (llp->l_ch!='a' && llp->l_ch!='A'
            &&  llp->l_ch!='p' && llp->l_ch!='P')
                return FALSE;
            ++llp;
            if (llp->l_ch!='m' && llp->l_ch!='M')
                return FALSE;
            ++llp;
            if (llp != rlp) return FALSE;
            return TRUE;
        }

    Args:
        word: Byte slice. ``str`` is Latin-1 encoded.

    Returns:
        ``True`` iff ``word`` is exactly 2 characters: ``a``/``A``/
        ``p``/``P`` followed by ``m``/``M``.
    """
    buf = word.encode("latin-1", errors="replace") if isinstance(word, str) else word
    if len(buf) != _AM_PM_LENGTH:
        return False
    first = buf[0]
    if first not in (ord("a"), ord("A"), ord("p"), ord("P")):
        return False
    second = buf[1]
    return second in (ord("m"), ord("M"))


__all__ = [
    "ls_proc_is_am_pm",
    "ls_proc_is_date",
    "ls_proc_is_frac",
    "ls_proc_is_time",
]
