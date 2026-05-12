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


__all__ = ["ambiguous_char"]
