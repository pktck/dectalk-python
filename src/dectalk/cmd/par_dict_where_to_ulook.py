"""``par_dict_where_to_ulook`` from cmd/par_dict.c.

Translated from ``src/dapi/src/cmd/par_dict.c`` lines 676-692.

User-dictionary direction helper: decides whether the search word
sorts higher or lower than the current entry in the case-folded
sort order. The companion of :func:`par_dict_udlook` -- invoked when
the in-place character compare diverges.

Differs from :func:`dectalk.cmd.dict_search.par_dict_where_to_look`
by omitting the exact-match short-circuit: a perfect case-folded
match returns :data:`LOOK_LOWER` here (because ``ls_upper[0] (== 0)
> 0`` is false). That mirrors the C source so the binary search
keeps descending past the matched entry; the user dictionary can
hold multiple entries for the same key at consecutive indices.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_upper

LOOK_HIGHER: Final[int] = 0xFFFF
LOOK_LOWER: Final[int] = 0xFFFE


def par_dict_where_to_ulook(ent: bytes, word: bytes) -> int:
    r"""Return :data:`LOOK_HIGHER` or :data:`LOOK_LOWER` for user-dict bisection.

    Faithful translation of:

    .. code-block:: c

        int par_dict_where_to_ulook(char *ent, unsigned char *word) {
            int i;
            unsigned char pivot_char = 0;
            for (i = 0; word[i]; i++) {
                pivot_char = par_upper[(int)ent[i]];
                if (par_upper[word[i]] != pivot_char)
                    break;
            }
            if (par_upper[word[i]] > pivot_char)
                return LOOK_HIGHER;
            return LOOK_LOWER;
        }

    The loop case-folds both inputs to upper-case (``par_upper`` ==
    :data:`ls_upper`) until ``word`` ends or the folded characters
    diverge. On exit, ``pivot_char`` is the upper-folded ``ent``
    byte at the breaking position (or its trailing position when
    ``word`` ended first); if the folded ``word`` byte exceeds it,
    the word sorts higher.

    Args:
        ent: NUL-terminated entry text (or simply ``bytes`` -- the
            loop also bounds-checks against the slice length).
        word: NUL-terminated search word.

    Returns:
        :data:`LOOK_HIGHER` if the upper-folded ``word`` sorts
        strictly greater than the upper-folded ``ent`` at the
        breaking position, :data:`LOOK_LOWER` otherwise (which
        includes the exact-match case).
    """
    word_len = len(word)
    ent_len = len(ent)

    i = 0
    pivot_char = 0
    while i < word_len and word[i] != 0:
        pivot_char = ls_upper[ent[i]] if i < ent_len else 0
        if ls_upper[word[i]] != pivot_char:
            break
        i += 1

    word_byte = word[i] if i < word_len else 0
    if ls_upper[word_byte] > pivot_char:
        return LOOK_HIGHER
    return LOOK_LOWER


__all__ = ["LOOK_HIGHER", "LOOK_LOWER", "par_dict_where_to_ulook"]
