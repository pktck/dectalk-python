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
- :func:`par_dict_dlook_entry` — main-dictionary entry comparison.
  Takes a single entry's text + the search word and returns
  ``HIT`` / ``ABBREV`` / ``LOOK_HIGHER`` / ``LOOK_LOWER``.
- :func:`par_dict_udlook_entry` — user-dictionary entry comparison
  (case-sensitive for uppercase entry letters).
- :data:`LOOK_HIGHER` / :data:`LOOK_LOWER` — the comparator return
  codes shared by all three.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_lower, ls_upper
from dectalk.lts.dict_codes import ABBREV, HIT

LOOK_HIGHER: Final[int] = 0xFFFF
LOOK_LOWER: Final[int] = 0xFFFE


def _is_lower(b: int) -> bool:
    """Return True iff ``b`` is a lowercase ASCII letter (``a``..``z``)."""
    return ls_lower[b] == b and b != ls_upper[b]


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


def par_dict_dlook_entry(entry_text: bytes, word: bytes) -> int:
    r"""Compare a main-dictionary entry's text against the search word.

    Faithful translation of the per-entry branch in:

    .. code-block:: c

        int par_dict_dlook(long DICT_ENTRY, S32 *DICT_INDEX,
                           unsigned char *DICT_DATA,
                           long index, struct dic_entry far **ppent,
                           unsigned char *word) {
            // ... binary-search bounds ...
            for (i = 0; (*ppent)->text[i] != '\0'; i++) {
                if (word[i] == '\0')                return LOOK_LOWER;
                if (word[i] == (*ppent)->text[i])   continue;
                if (IS_LOWER((*ppent)->text[i]) &&
                    word[i] == par_upper[(*ppent)->text[i]]) continue;
                if (index == 0)      return LOOK_HIGHER;
                if (index == limit)  return LOOK_LOWER;
                return par_dict_where_to_look(*ppent, word);
            }
            if (word[i] == '\0') {
                if (word[i-1] == '.') return ABBREV;
                else                  return HIT;
            }
            return LOOK_HIGHER;
        }

    The Python port omits the index-bounds checks (the caller handles
    the binary-search edges); on a mismatch in the middle of the
    entry it falls through to :func:`par_dict_where_to_look`.

    Args:
        entry_text: Bytes of the dictionary entry's word
            (NUL-terminated or just to the end of the slice).
        word: Search word (NUL-terminated or just bytes).

    Returns:
        :data:`HIT` on a full match, :data:`ABBREV` if the entry was
        a ``"<word>."`` abbreviation, :data:`LOOK_LOWER` if the word
        is shorter than the entry, :data:`LOOK_HIGHER` if longer;
        otherwise the comparator result for the mismatch.
    """
    entry_len = len(entry_text)
    word_len = len(word)
    for i in range(entry_len):
        ec = entry_text[i]
        if ec == 0:
            entry_len = i
            break
        wc = word[i] if i < word_len else 0
        if wc == 0:
            return LOOK_LOWER
        if wc == ec:
            continue
        # Match if entry is lowercase letter and word is its uppercase form.
        if _is_lower(ec) and wc == ls_upper[ec]:
            continue
        return par_dict_where_to_look(entry_text, word)
    # Reached end of entry without mismatch — check word ending.
    wc = word[entry_len] if entry_len < word_len else 0
    if wc == 0:
        # Both ended together. ABBREV when the entry's last char was '.'.
        if entry_len > 0 and entry_text[entry_len - 1] == ord("."):
            return ABBREV
        return HIT
    # Word was longer than entry.
    return LOOK_HIGHER


def par_dict_udlook_entry(entry_text: bytes, word: bytes) -> int:
    r"""Compare a user-dictionary entry against the search word.

    Faithful translation of:

    .. code-block:: c

        int par_dict_udlook(long UDICT_ENTRY, S32 *UDICT_INDEX,
                            unsigned char *UDICT_DATA,
                            long uindex, unsigned char *word) {
            ent = (...->text);
            for (i = 0; ent[i] != '\0'; i++) {
                if (word[i] == ent[i])         continue;
                if (word[i] == '\0')           return LOOK_LOWER;
                if (IS_LOWER(ent[i]) && word[i] == par_upper[ent[i]])
                    continue;
                return par_dict_where_to_ulook(ent, word);
            }
            if (word[i] == '\0') return HIT;
            return LOOK_HIGHER;
        }

    Differs from :func:`par_dict_dlook_entry` by:

    - Always returning :data:`HIT` on full equality (the user
      dictionary never produces ``ABBREV``).
    - Falling through to :func:`ls_dict_where_to_ulook` on a
      mid-string mismatch (so equality returns :data:`LOOK_LOWER`,
      letting the caller find consecutive entries for the same key).

    Args:
        entry_text: Bytes of the user-dictionary entry text.
        word: Search word.

    Returns:
        :data:`HIT` on exact match, :data:`LOOK_LOWER` if the word
        is shorter, :data:`LOOK_HIGHER` if longer; otherwise the
        :func:`ls_dict_where_to_ulook` comparator result.
    """
    entry_len = len(entry_text)
    word_len = len(word)
    for i in range(entry_len):
        ec = entry_text[i]
        if ec == 0:
            entry_len = i
            break
        wc = word[i] if i < word_len else 0
        if wc == ec:
            continue
        if wc == 0:
            return LOOK_LOWER
        if _is_lower(ec) and wc == ls_upper[ec]:
            continue
        return ls_dict_where_to_ulook(entry_text, word)
    wc = word[entry_len] if entry_len < word_len else 0
    if wc == 0:
        return HIT
    return LOOK_HIGHER


__all__ = [
    "LOOK_HIGHER",
    "LOOK_LOWER",
    "ls_dict_where_to_look",
    "ls_dict_where_to_ulook",
    "par_dict_dlook_entry",
    "par_dict_udlook_entry",
    "par_dict_where_to_look",
]
