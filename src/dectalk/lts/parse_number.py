"""Number-pattern scanner from ls_task.c::ls_task_parse_number.

Translated from ``src/dapi/src/lts/ls_task.c``. The scanner walks a
word slice looking for a number pattern:

  - Integer part with optional thousands separator (3-digit groups,
    each separated by ``pLts_t->schar`` which is ``,`` in US mode
    and ``.`` in :data:`~dectalk.kernel.mode_flags.MODE_EUROPE`).
  - Optional Latin-1 fraction byte (``¼`` 0xBC or ``½`` 0xBD) that
    terminates the integer part early.
  - Optional decimal part separated by ``pLts_t->fchar``.
  - Optional exponent (``eN``, ``e+N``, ``e-N``) — only matched
    when :data:`~dectalk.kernel.mode_flags.MODE_MATH` is on.

Returns a populated :class:`~dectalk.lts.structs.Num` (with bounds
expressed as byte offsets into ``word``) plus the offset just past
the consumed bytes.
"""

from __future__ import annotations

from dectalk.lts.char_features import is_digit
from dectalk.lts.structs import Letter, Num

_FRAC_QUARTER: int = 0xBC
_FRAC_HALF: int = 0xBD


def _bounds_to_letters(word: bytes, start: int, end: int) -> Letter | None:
    """Return a sentinel :class:`Letter` at ``word[start]``, or None.

    Returns None when ``start == end`` (no bytes covered).
    Used to populate Num's pointer-like fields without modelling
    actual C pointer arithmetic.
    """
    if start >= end or start < 0 or start >= len(word):
        return None
    return Letter(l_ch=word[start])


def ls_task_parse_number(  # noqa: PLR0912, PLR0915 — mirrors C state machine
    word: bytes,
    schar: int = ord(","),
    fchar: int = ord("."),
    *,
    math_mode: bool = False,
) -> tuple[Num, int]:
    """Scan ``word`` for a number pattern.

    Faithful translation of:

    .. code-block:: c

        LETTER *ls_task_parse_number(LPTTS_HANDLE_T phTTS,
                                     LETTER *llp, LETTER *rlp,
                                     NUM *np) {
            // ... parse integer part (with thousands separator
            //     and Latin-1 fraction terminator) ...
            // ... optional fractional part after fchar ...
            // ... optional exponent (only in MODE_MATH) ...
            return tlp1;  // pointer just past the number
        }

    The Python port replaces the C pointer arithmetic with byte
    offsets into ``word``. The returned :class:`Num` carries
    :class:`Letter` sentinels in the ``n_*`` fields when the
    corresponding part was matched (or ``None`` otherwise).

    Args:
        word: The word to scan as bytes.
        schar: Thousands-separator character (``,`` in US mode,
            ``.`` in MODE_EUROPE).
        fchar: Decimal-point character (``.`` in US, ``,`` in
            MODE_EUROPE).
        math_mode: True to enable exponent matching (``MODE_MATH``).

    Returns:
        ``(num, end)`` where ``num`` is a populated :class:`Num` and
        ``end`` is the offset just past the consumed bytes (or 0 if
        ``word`` doesn't start with a digit or fraction).
    """
    num = Num()
    n = len(word)
    i = 0
    if i < n and (word[i] == _FRAC_QUARTER or word[i] == _FRAC_HALF or is_digit(word[i])):
        int_start = i
        num.n_ilp = _bounds_to_letters(word, i, n)
        while i < n:
            # Standalone Latin-1 fraction terminates the integer part.
            if word[i] == _FRAC_QUARTER or word[i] == _FRAC_HALF:
                i += 1
                num.n_irp = _bounds_to_letters(word, i, n)
                return num, i
            # Thousands separator.
            if word[i] == schar:
                # Look 1..3 chars back; bail if another schar found.
                ncbs = 3
                back = i
                break_flag = False
                while ncbs > 0 and back > int_start:
                    back -= 1
                    if word[back] == schar:
                        break_flag = True
                        break
                    ncbs -= 1
                if break_flag:
                    break
                # Lookahead: next 3 chars must be digits.
                ncbs = 3
                fwd = i + 1
                break_flag = False
                while ncbs > 0:
                    if fwd >= n or not is_digit(word[fwd]):
                        break_flag = True
                        break
                    fwd += 1
                    ncbs -= 1
                if break_flag:
                    break
                # Reject if a fourth digit follows (the C "Kurzweil tweak").
                if fwd < n and is_digit(word[fwd]):
                    break
                i += 1
                continue
            if is_digit(word[i]):
                i += 1
                continue
            break
        num.n_irp = _bounds_to_letters(word, i, n) if i < n else None
    # Fractional part.
    if i < n and word[i] == fchar:
        num.n_flp = _bounds_to_letters(word, i, n)
        i += 1
        while i < n and is_digit(word[i]):
            i += 1
        num.n_frp = _bounds_to_letters(word, i, n) if i < n else None
    # Exponent — only in MODE_MATH.
    if math_mode and i < n and word[i] == ord("e"):
        e_start = i
        i += 1
        if i < n and (word[i] == ord("+") or word[i] == ord("-")):
            i += 1
        if i < n and is_digit(word[i]):
            num.n_elp = _bounds_to_letters(word, e_start, n)
            i += 1
            while i < n and is_digit(word[i]):
                i += 1
            num.n_erp = _bounds_to_letters(word, i, n) if i < n else None
    return num, i


__all__ = ["ls_task_parse_number"]
