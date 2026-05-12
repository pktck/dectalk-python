"""Math-mode single-character word check from ls_task.c.

Translated from ``src/dapi/src/lts/ls_task.c``:

- :func:`ls_task_math_mode` — return True iff a single-character
  word is a math symbol AND math mode is currently enabled.
"""

from __future__ import annotations

from dectalk.lts.math_mode import do_math


def ls_task_math_mode(word: bytes | list[int], *, math_mode_enabled: bool) -> bool:
    """Return True iff ``word`` is a single math symbol in math mode.

    Faithful translation of:

    .. code-block:: c

        int ls_task_math_mode(PKSD_T pKsd_t, LETTER *llp, LETTER *rlp) {
            if (llp+1 == rlp && (pKsd_t->modeflag & MODE_MATH)) {
                if (ls_math_do_math(pKsd_t, (unsigned char)llp->l_ch) != FALSE)
                    return FINISHED_WORD;
            }
            return KEEP_SEARCHING;
        }

    The C source's ``llp+1 == rlp`` test means the word slice is
    exactly one LETTER long. The MODE_MATH flag comes from
    ``pKsd_t->modeflag``; we expose it as an explicit kwarg.

    Args:
        word: Word as bytes or list of int byte values.
        math_mode_enabled: True iff ``MODE_MATH`` bit is set in
            ``pKsd_t->modeflag``.

    Returns:
        ``True`` iff ``word`` is exactly one byte AND that byte is
        a recognised math symbol AND math mode is enabled.
    """
    if not math_mode_enabled:
        return False
    if len(word) != 1:
        return False
    char = word[0] if isinstance(word, (bytes, list)) else 0  # type: ignore[unreachable]
    return len(do_math(char)) > 0


__all__ = ["ls_task_math_mode"]
