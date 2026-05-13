"""``par_dict_udlook`` from cmd/par_dict.c.

Translated from ``src/dapi/src/cmd/par_dict.c`` lines 583-612.

User-dictionary bisection helper: compares the entry at index
``uindex`` against the search word and returns one of :data:`HIT`,
:data:`LOOK_LOWER`, or :data:`LOOK_HIGHER`. Called from
``par_dict_ufind_word`` (the user-dict binary search driver).

The C function pokes into the user-dictionary blob via the
``UDICT_INDEX`` offset table and reinterprets the bytes at that
offset as a ``struct dic_entry``. In Python we mirror that layout by
walking ``UDICT_DATA[UDICT_INDEX[uindex] + DIC_ENTRY_TEXT_OFFSET]``
as the entry text (``fc`` is 4 bytes, so text starts at +4 with the
non-CHEESY_DICT_COMPRESSION layout that the Linux build uses).
"""

from __future__ import annotations

from typing import Final

from dectalk.cmd.par_dict_where_to_ulook import par_dict_where_to_ulook
from dectalk.cmd.parser_tables import TYPE_lower, parser_char_types
from dectalk.lts.char_features import ls_upper
from dectalk.lts.dict_codes import HIT

LOOK_HIGHER: Final[int] = 0xFFFF
LOOK_LOWER: Final[int] = 0xFFFE

# Offset of the ``text`` field inside ``struct dic_entry``. With
# CHEESY_DICT_COMPRESSION undefined (Linux build), the struct is
# ``U32 fc; unsigned char text[128];`` so the text begins at byte 4.
DIC_ENTRY_TEXT_OFFSET: Final[int] = 4


def _is_lower(c: int) -> bool:
    """C macro ``IS_LOWER(c)`` from par_def.h.

    Defined as ``parser_char_types[(c)&0xff] & TYPE_lower`` -- True
    when ``c`` is a lower-case ASCII letter (or its latin-1
    equivalent).
    """
    return bool(parser_char_types[c & 0xFF] & TYPE_lower)


def par_dict_udlook(
    udict_entry: int,
    udict_index: list[int] | tuple[int, ...],
    udict_data: bytes,
    uindex: int,
    word: bytes,
) -> int:
    r"""Compare the user-dict entry at ``uindex`` against ``word``.

    Faithful translation of:

    .. code-block:: c

        int par_dict_udlook(long UDICT_ENTRY, S32 *UDICT_INDEX,
                            unsigned char *UDICT_DATA,
                            long uindex, unsigned char *word) {
            unsigned char *ent;
            int i;
            ent = ((struct dic_entry *)
                   &(UDICT_DATA[UDICT_INDEX[uindex]]))->text;
            for (i = 0; ent[i] != '\0'; i++) {
                if (word[i] == ent[i])             continue;
                if (word[i] == '\0')               return LOOK_LOWER;
                if (IS_LOWER(ent[i]) &&
                    word[i] == par_upper[ent[i]])  continue;
                return par_dict_where_to_ulook(ent, word);
            }
            if (word[i] == '\0')                   return HIT;
            return LOOK_HIGHER;
        }

    The ``IS_LOWER`` short-circuit means an uppercase ``word`` byte
    matches a lowercase ``ent`` byte (the canonical entry form), but
    an uppercase ``ent`` byte requires the word to match exactly --
    the user dict can therefore distinguish case-sensitive entries.

    Args:
        udict_entry: Total number of entries in the user dict
            (unused here -- carried for signature parity with the C
            source).
        udict_index: Per-entry offset table; ``udict_index[uindex]``
            gives the byte offset of the entry's ``dic_entry`` struct
            within ``udict_data``.
        udict_data: Raw bytes of the user-dictionary blob. The byte
            at ``udict_data[udict_index[uindex] + 4]`` is the first
            byte of the entry's NUL-terminated text.
        uindex: Index of the entry to compare against.
        word: NUL-terminated bytes of the search word (or simply
            ``bytes`` without a trailing NUL -- the loop also
            terminates at end-of-buffer).

    Returns:
        :data:`HIT` on full case-folded match,
        :data:`LOOK_LOWER` if the word is shorter than the entry,
        :data:`LOOK_HIGHER` if the word is longer; otherwise the
        :func:`par_dict_where_to_ulook` result for the mismatching
        character.
    """
    # The C dereference ``((struct dic_entry *)&UDICT_DATA[off])->text``
    # is equivalent to the byte slice starting at off + 4 (sizeof fc).
    _ = udict_entry  # Carried for signature parity; not consulted.
    base = udict_index[uindex] + DIC_ENTRY_TEXT_OFFSET
    data_len = len(udict_data)
    word_len = len(word)

    i = 0
    while True:
        ent_pos = base + i
        ent_byte = udict_data[ent_pos] if ent_pos < data_len else 0
        if ent_byte == 0:
            # End of entry text.
            word_byte = word[i] if i < word_len else 0
            if word_byte == 0:
                return HIT
            return LOOK_HIGHER

        word_byte = word[i] if i < word_len else 0
        if word_byte == ent_byte:
            i += 1
            continue
        if word_byte == 0:
            return LOOK_LOWER
        if _is_lower(ent_byte) and word_byte == ls_upper[ent_byte]:
            i += 1
            continue
        # ``ent`` argument to par_dict_where_to_ulook is the slice of
        # UDICT_DATA starting at the entry's text byte (matches the
        # C ``unsigned char *ent`` pointer).
        ent_slice = udict_data[base : base + 128]
        return par_dict_where_to_ulook(ent_slice, word)


__all__ = ["DIC_ENTRY_TEXT_OFFSET", "LOOK_HIGHER", "LOOK_LOWER", "par_dict_udlook"]
