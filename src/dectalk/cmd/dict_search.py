"""Dictionary binary-search helpers from the parser.

Translated from ``src/dapi/src/cmd/par_dict.c``. These helpers
drive the parser's binary-search lookup over the sorted user /
main dictionary entries.

- :func:`par_dict_where_to_look` — case-insensitive 3-way comparator
  that the binary search calls at each step. Returns :data:`LOOK_HIGHER`
  if the target word sorts greater than (or equal to) the current
  entry, :data:`LOOK_LOWER` otherwise.
- :data:`LOOK_HIGHER` / :data:`LOOK_LOWER` — the comparator return
  codes from par_dict.c.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_upper

LOOK_HIGHER: Final[int] = 0xFFFF
LOOK_LOWER: Final[int] = 0xFFFE


def par_dict_where_to_look(entry_text: bytes, word: bytes) -> int:
    r"""Return :data:`LOOK_HIGHER` or :data:`LOOK_LOWER` for the binary search.

    Faithful translation of:

    .. code-block:: c

        int par_dict_where_to_look(struct dic_entry far *pent,
                                   unsigned char *word) {
            int i;
            unsigned char pivot_char = 0;
            for (i = 0; word[i]; i++) {
                pivot_char = par_upper[pent->text[i]];
                if (par_upper[word[i]] != pivot_char)
                    break;
            }
            if ((word[i] == '\0') && (pent->text[i] == '\0'))
                return LOOK_HIGHER;
            if (par_upper[word[i]] > pivot_char)
                return LOOK_HIGHER;
            return LOOK_LOWER;
        }

    The function uses ``par_upper[]`` (= :data:`ls_upper`) to case-fold
    both inputs to upper before comparing. The match-or-greater case
    returns :data:`LOOK_HIGHER` (so an exact match terminates the
    search; LOOK_HIGHER is overloaded to mean "stop ascending").

    Args:
        entry_text: Current dictionary entry's word, NUL-terminated bytes
            (or simply ending the bytes at the right boundary).
        word: Word being searched for. NUL-terminated or just bytes.

    Returns:
        ``LOOK_HIGHER`` if ``word >= entry_text`` (case-insensitive,
        upper-folded); ``LOOK_LOWER`` if strictly less.
    """
    # Walk both strings until a mismatch or until ``word`` ends.
    i = 0
    pivot_char = 0
    word_len = len(word)
    entry_len = len(entry_text)
    while i < word_len and word[i] != 0:
        pivot_char = ls_upper[entry_text[i]] if i < entry_len else 0
        if ls_upper[word[i]] != pivot_char:
            break
        i += 1

    word_byte = word[i] if i < word_len else 0
    entry_byte = entry_text[i] if i < entry_len else 0

    # Both strings ended at the same length — exact match → LOOK_HIGHER
    if word_byte == 0 and entry_byte == 0:
        return LOOK_HIGHER

    if ls_upper[word_byte] > pivot_char:
        return LOOK_HIGHER
    return LOOK_LOWER


__all__ = ["LOOK_HIGHER", "LOOK_LOWER", "par_dict_where_to_look"]
