"""15x20 ambiguous character-type transition table.

Translated from ``src/dapi/src/cmd/par_ambi.tab`` (included by
``par_ambi.c`` into the CMD inline-command parser). Each entry tells
the parser how to handle a transition between two character types
(digit→letter, letter→punct, etc.) — the value is a hint code the
state machine uses to decide whether to break a token, continue, or
emit a special marker.

Row types (15) and column types (20) are the same TYPE_* values
exposed in :mod:`dectalk.cmd.parser_tables`, with the first 15
matching exactly and the last 5 columns covering extra TYPE_ codes
the parser tracks separately.

Layout, taken verbatim from the auto-generated tab file:

    rows:  DIGIT, UPPER, LOWER, ANY_ALPHA, ANY_CHAR, WHITE, PUNCT,
           NON_ALPHA, VOWEL, CONSONANT, NUMBER, CLAUSE, ALPHA_NUM,
           VOWEL_NON_Y, SOME_PUNCT  (15 rows)
    cols:  the same 15 plus 5 extras (NON_Y, UNCT, CHAR, ACSEM, ICAL,
           CHARS / see par_ambi.tab header column-key)

Used in cm_pars.c::cm_pars_proc_char to look up
``ambiguous_char[prev_type][next_type]`` and choose the parser action.
"""

from __future__ import annotations

from typing import Final

ambiguous_char: Final[tuple[tuple[int, ...], ...]] = (
    # DIGIT_CHAR_TYPE
    (9, 14, 14, 14, 5, 14, 14, 13, 14, 14, 14, 14, 13, 14, 14, 0, 5, 5, 5, 5),
    # UPPER_CHAR_TYPE
    (14, 9, 14, 15, 5, 14, 14, 14, 15, 15, 14, 14, 15, 15, 14, 0, 5, 5, 5, 5),
    # LOWER_CHAR_TYPE
    (14, 14, 9, 15, 5, 14, 14, 14, 15, 15, 14, 14, 15, 15, 14, 0, 5, 5, 5, 5),
    # ANY_ALPHA_CHAR_TYPE
    (14, 15, 15, 9, 5, 14, 14, 14, 11, 11, 14, 14, 13, 11, 14, 0, 5, 5, 5, 5),
    # ANY_CHAR_CHAR_TYPE
    (3, 3, 3, 3, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 1, 1, 1, 1),
    # WHITE_CHAR_TYPE
    (14, 14, 14, 14, 5, 9, 14, 14, 14, 14, 14, 15, 14, 14, 14, 0, 5, 5, 5, 5),
    # PUNCT_CHAR_TYPE
    (14, 14, 14, 14, 5, 14, 9, 13, 14, 14, 15, 15, 14, 14, 11, 0, 5, 5, 5, 5),
    # NON_ALPHA_CHAR_TYPE
    (11, 14, 14, 14, 5, 14, 11, 9, 14, 14, 15, 15, 15, 14, 11, 0, 5, 5, 5, 5),
    # VOWEL_CHAR_TYPE
    (14, 15, 15, 13, 5, 14, 14, 14, 9, 15, 14, 14, 13, 11, 14, 0, 5, 5, 5, 5),
    # CONSONANT_CHAR_TYPE
    (14, 15, 15, 13, 5, 14, 14, 14, 15, 9, 14, 14, 13, 14, 14, 0, 5, 5, 5, 5),
    # NUMBER_CHAR_TYPE
    (14, 14, 14, 14, 5, 14, 15, 15, 14, 14, 9, 14, 14, 14, 15, 0, 5, 5, 5, 5),
    # CLAUSE_CHAR_TYPE
    (14, 14, 14, 14, 5, 15, 15, 15, 14, 14, 14, 9, 14, 14, 14, 0, 5, 5, 5, 5),
    # ALPHA_NUM_CHAR_TYPE
    (11, 15, 15, 11, 5, 14, 14, 15, 11, 11, 14, 14, 9, 11, 14, 0, 5, 5, 5, 5),
    # VOWEL_NON_Y_TYPE
    (14, 15, 15, 13, 5, 14, 14, 14, 13, 14, 14, 14, 13, 9, 14, 0, 5, 5, 5, 5),
    # SOME_PUNCT_TYPE
    (14, 14, 14, 14, 5, 14, 13, 13, 14, 14, 15, 14, 14, 14, 9, 0, 5, 5, 5, 5),
)


def par_lookup_ambiguous(
    cur_type: int,
    from_reverse: int,
    new_type: int,
    to_reverse: int,
) -> int:
    """Look up an ambiguity bit from :data:`ambiguous_char`.

    Faithful translation of:

    .. code-block:: c

        short par_lookup_ambiguous(int cur_type, int from_reverse,
                                    int new_type, int to_reverse) {
            char bit_to_check = 0x01;
            if (!from_reverse) bit_to_check <<= 2;
            if (!to_reverse)   bit_to_check <<= 1;
            return ambiguous_char[cur_type][new_type] & bit_to_check;
        }

    Encodes the bit lookup in a single byte where 4 bits represent
    each combination of (from_reverse, to_reverse) ∈ {0,1}^2:

    * ``from_reverse=1, to_reverse=1`` → bit 0 (0x01)
    * ``from_reverse=1, to_reverse=0`` → bit 1 (0x02)
    * ``from_reverse=0, to_reverse=1`` → bit 2 (0x04)
    * ``from_reverse=0, to_reverse=0`` → bit 3 (0x08)

    Args:
        cur_type: Current character type (row index, 0..14).
        from_reverse: ``1`` for reverse, ``0`` for forward direction.
        new_type: Next character type (column index, 0..19).
        to_reverse: ``1`` for reverse, ``0`` for forward direction.

    Returns:
        The masked bit (``0``, ``0x01``, ``0x02``, ``0x04``, or
        ``0x08``); non-zero is truthy.
    """
    bit_to_check = 0x01
    if not from_reverse:
        bit_to_check <<= 2
    if not to_reverse:
        bit_to_check <<= 1
    return ambiguous_char[cur_type][new_type] & bit_to_check


__all__ = ["ambiguous_char", "par_lookup_ambiguous"]
