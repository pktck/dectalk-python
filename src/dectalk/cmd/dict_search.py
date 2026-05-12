"""Dictionary binary-search helpers from the parser and LTS.

Translated from ``src/dapi/src/cmd/par_dict.c`` and
``src/dapi/src/lts/ls_dict.c``. These helpers drive the
binary-search lookup over the sorted main / user dictionary entries.

- :func:`par_dict_where_to_look` — parser's case-insensitive 3-way
  comparator (with exact-match short-circuit). Returns
  :data:`LOOK_HIGHER` if the target word sorts greater than (or
  equal to) the current entry, :data:`LOOK_LOWER` otherwise.
- :func:`ls_dict_where_to_look` — LTS-side sibling that walks the
  LTS ``comp_str`` against a ``dic_entry`` text. Same algorithm as
  the parser's version with the exact-match short-circuit.
- :func:`ls_dict_where_to_ulook` — LTS user-dictionary comparator.
  Same structure but omits the exact-match short-circuit (so an
  exact match returns :data:`LOOK_LOWER`).
- :data:`LOOK_HIGHER` / :data:`LOOK_LOWER` — the comparator return
  codes shared by all three.
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


def ls_dict_where_to_look(entry_text: bytes, comp_str: bytes) -> int:
    r"""Return :data:`LOOK_HIGHER` / :data:`LOOK_LOWER` for LTS main-dict search.

    Faithful translation of:

    .. code-block:: c

        int ls_dict_where_to_look(LPTTS_HANDLE_T phTTS,
                                  struct dic_entry far *pent) {
            int i;
            unsigned char pivot_char = '\0';
            for (i = 0; pLts_t->comp_str[i]; i++) {
                pivot_char = ls_upper[pent->text[i]];
                if (ls_upper[pLts_t->comp_str[i]] != pivot_char)
                    break;
            }
            if (pLts_t->comp_str[i]=='\0' && pent->text[i]=='\0')
                return LOOK_HIGHER;        // exact match
            if (ls_upper[pLts_t->comp_str[i]] > pivot_char)
                return LOOK_HIGHER;
            return LOOK_LOWER;
        }

    Algorithm is identical to :func:`par_dict_where_to_look`; only
    the field names differ in the C source. Returns
    :data:`LOOK_HIGHER` on exact match.

    Args:
        entry_text: ``pent->text`` from a dic_entry struct
            (NUL-terminated or end-of-bytes).
        comp_str: ``pLts_t->comp_str``, the LTS-side comparison
            buffer being searched for.

    Returns:
        :data:`LOOK_HIGHER` if ``comp_str >= entry_text``
        (case-insensitive); :data:`LOOK_LOWER` otherwise.
    """
    return par_dict_where_to_look(entry_text, comp_str)


def ls_dict_where_to_ulook(entry_text: bytes, comp_str: bytes) -> int:
    r"""Return :data:`LOOK_HIGHER` / :data:`LOOK_LOWER` for LTS user-dict search.

    Faithful translation of:

    .. code-block:: c

        int ls_dict_where_to_ulook(PLTS_T pLts_t, char far *ent) {
            int i;
            unsigned char pivot_char = '\0';
            for (i = 0; pLts_t->comp_str[i]; i++) {
                pivot_char = ls_upper[ent[i]];
                if (ls_upper[pLts_t->comp_str[i]] != pivot_char)
                    break;
            }
            if (ls_upper[pLts_t->comp_str[i]] > pivot_char)
                return LOOK_HIGHER;
            return LOOK_LOWER;
        }

    Differs from :func:`ls_dict_where_to_look` by **omitting** the
    exact-match short-circuit: a perfect match returns
    :data:`LOOK_LOWER` here (because ``ls_upper[0] (== 0) > 0`` is
    false). This is intentional in the C source so the search keeps
    descending past the matched entry; user dictionaries can hold
    multiple entries for the same word at consecutive positions.

    Args:
        entry_text: User-dictionary entry text (NUL-terminated or
            end-of-bytes).
        comp_str: ``pLts_t->comp_str``, the LTS comparison buffer.

    Returns:
        :data:`LOOK_HIGHER` if ``comp_str`` sorts strictly greater
        than ``entry_text`` (case-insensitive); :data:`LOOK_LOWER`
        if less-than or equal.
    """
    i = 0
    pivot_char = 0
    comp_len = len(comp_str)
    entry_len = len(entry_text)
    while i < comp_len and comp_str[i] != 0:
        pivot_char = ls_upper[entry_text[i]] if i < entry_len else 0
        if ls_upper[comp_str[i]] != pivot_char:
            break
        i += 1

    comp_byte = comp_str[i] if i < comp_len else 0
    if ls_upper[comp_byte] > pivot_char:
        return LOOK_HIGHER
    return LOOK_LOWER


__all__ = [
    "LOOK_HIGHER",
    "LOOK_LOWER",
    "ls_dict_where_to_look",
    "ls_dict_where_to_ulook",
    "par_dict_where_to_look",
]
