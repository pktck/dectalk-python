"""Rule-engine state / char-type dispatch functions from par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c``:

- :func:`par_get_char_type` — given a delimiter byte from a CMD rule
  file, returns the corresponding numeric char-type code (one of the
  :data:`TYPE_*` bit-flags or one of the non-bit SET/EXACT/HEXADECIMAL
  sentinels). Returns :data:`NULL_TYPE` if the byte isn't recognised.
- :func:`par_get_state` — given a delimiter byte, returns the
  numeric action-state code (COPY / REPLACE / DELETE / INSERT / …)
  or :data:`NULL_STATE` if the byte isn't recognised.
- :func:`par_convert_to_new` — maps a sparse TYPE_* code to a 0..19
  zero-based index used by the compact rule-action table.
"""

from __future__ import annotations

from dectalk.cmd.rule_states import (
    ALPHA_NUM_CHAR_TYPE,
    ALPHA_NUM_CHAR_TYPE2,
    ALPHA_NUM_DELIM,
    ANY_ALPHA_CHAR_DELIM,
    ANY_ALPHA_CHAR_TYPE,
    ANY_ALPHA_CHAR_TYPE2,
    ANY_CHAR_CHAR_DELIM,
    ANY_CHAR_CHAR_TYPE,
    ANY_CHAR_CHAR_TYPE2,
    CLAUSE_CHAR_DELIM,
    CLAUSE_CHAR_TYPE,
    CLAUSE_CHAR_TYPE2,
    CONSONANT_CHAR_DELIM,
    CONSONANT_CHAR_TYPE,
    CONSONANT_CHAR_TYPE2,
    COPY_DELIMITER,
    COPY_STATE,
    DELETE_DELIMITER,
    DELETE_STATE,
    DICTIONARY_STATE,
    DICTIONARY_STATE_DELIM,
    DIGIT_CHAR_DELIM,
    DIGIT_CHAR_TYPE,
    DIGIT_CHAR_TYPE2,
    EXACT_CASE_DELIM,
    EXACT_CASE_TYPE,
    EXACT_CASE_TYPE2,
    EXACT_CHAR_DELIM,
    EXACT_CHAR_TYPE,
    EXACT_CHAR_TYPE2,
    HEXADECIMAL_DELIM,
    HEXADECIMAL_TYPE,
    HEXADECIMAL_TYPE2,
    INSERT_AFTER_DELIM,
    INSERT_AFTER_STATE,
    INSERT_BEFORE_DELIM,
    INSERT_BEFORE_STATE,
    INSERT_DELIMITER,
    INSERT_STATE,
    LOWER_CHAR_DELIM,
    LOWER_CHAR_TYPE,
    LOWER_CHAR_TYPE2,
    MACRO_DELIMITER,
    MACRO_STATE,
    NO_LOOKAHEAD,
    NON_ALPHA_CHAR_DELIM,
    NON_ALPHA_CHAR_TYPE,
    NON_ALPHA_CHAR_TYPE2,
    NULL_STATE,
    NULL_TYPE,
    NUMBER_CHAR_DELIM,
    NUMBER_CHAR_TYPE,
    NUMBER_CHAR_TYPE2,
    OPTIONAL_DELIMITER,
    OPTIONAL_STATE,
    PUNCT_CHAR_DELIM,
    PUNCT_CHAR_TYPE,
    PUNCT_CHAR_TYPE2,
    REPLACE_DELIMITER,
    REPLACE_STATE,
    SAVE_CHAR_TYPE,
    SAVE_CHAR_TYPE2,
    SAVE_DELIMITER,
    SAVE_STATE,
    SET_CHAR_DELIM,
    SET_CHAR_TYPE,
    SET_CHAR_TYPE2,
    SOME_PUNCT_DELIM,
    SOME_PUNCT_TYPE,
    SOME_PUNCT_TYPE2,
    START_SAVE_STATE,
    STATUS_STATE,
    STATUS_STATE_DELIM,
    UPPER_CHAR_DELIM,
    UPPER_CHAR_TYPE,
    UPPER_CHAR_TYPE2,
    VOWEL_CHAR_DELIM,
    VOWEL_CHAR_TYPE,
    VOWEL_CHAR_TYPE2,
    VOWEL_NON_Y_DELIM,
    VOWEL_NON_Y_TYPE,
    VOWEL_NON_Y_TYPE2,
    WHITE_CHAR_DELIM,
    WHITE_CHAR_TYPE,
    WHITE_CHAR_TYPE2,
    WORD_STATE,
    WORD_STATE_DELIM,
)

_CHAR_TYPE_MAP: dict[int, int] = {
    DIGIT_CHAR_DELIM: DIGIT_CHAR_TYPE,
    UPPER_CHAR_DELIM: UPPER_CHAR_TYPE,
    ANY_ALPHA_CHAR_DELIM: ANY_ALPHA_CHAR_TYPE,
    ANY_CHAR_CHAR_DELIM: ANY_CHAR_CHAR_TYPE,
    WHITE_CHAR_DELIM: WHITE_CHAR_TYPE,
    PUNCT_CHAR_DELIM: PUNCT_CHAR_TYPE,
    LOWER_CHAR_DELIM: LOWER_CHAR_TYPE,
    NON_ALPHA_CHAR_DELIM: NON_ALPHA_CHAR_TYPE,
    SET_CHAR_DELIM: SET_CHAR_TYPE,
    VOWEL_CHAR_DELIM: VOWEL_CHAR_TYPE,
    CONSONANT_CHAR_DELIM: CONSONANT_CHAR_TYPE,
    NUMBER_CHAR_DELIM: NUMBER_CHAR_TYPE,
    CLAUSE_CHAR_DELIM: CLAUSE_CHAR_TYPE,
    ALPHA_NUM_DELIM: ALPHA_NUM_CHAR_TYPE,
    VOWEL_NON_Y_DELIM: VOWEL_NON_Y_TYPE,
    SOME_PUNCT_DELIM: SOME_PUNCT_TYPE,
    EXACT_CHAR_DELIM: EXACT_CHAR_TYPE,
    EXACT_CASE_DELIM: EXACT_CASE_TYPE,
    HEXADECIMAL_DELIM: HEXADECIMAL_TYPE,
    SAVE_DELIMITER: SAVE_CHAR_TYPE,
    NO_LOOKAHEAD: NO_LOOKAHEAD,
}

_STATE_MAP: dict[int, int] = {
    COPY_DELIMITER: COPY_STATE,
    REPLACE_DELIMITER: REPLACE_STATE,
    DELETE_DELIMITER: DELETE_STATE,
    INSERT_DELIMITER: INSERT_STATE,
    INSERT_AFTER_DELIM: INSERT_AFTER_STATE,
    INSERT_BEFORE_DELIM: INSERT_BEFORE_STATE,
    OPTIONAL_DELIMITER: OPTIONAL_STATE,
    START_SAVE_STATE: SAVE_STATE,
    MACRO_DELIMITER: MACRO_STATE,
    DICTIONARY_STATE_DELIM: DICTIONARY_STATE,
    WORD_STATE_DELIM: WORD_STATE,
    STATUS_STATE_DELIM: STATUS_STATE,
}

_TYPE_TO_TYPE2_MAP: dict[int, int] = {
    DIGIT_CHAR_TYPE: DIGIT_CHAR_TYPE2,
    UPPER_CHAR_TYPE: UPPER_CHAR_TYPE2,
    LOWER_CHAR_TYPE: LOWER_CHAR_TYPE2,
    ANY_ALPHA_CHAR_TYPE: ANY_ALPHA_CHAR_TYPE2,
    ANY_CHAR_CHAR_TYPE: ANY_CHAR_CHAR_TYPE2,
    WHITE_CHAR_TYPE: WHITE_CHAR_TYPE2,
    PUNCT_CHAR_TYPE: PUNCT_CHAR_TYPE2,
    NON_ALPHA_CHAR_TYPE: NON_ALPHA_CHAR_TYPE2,
    VOWEL_CHAR_TYPE: VOWEL_CHAR_TYPE2,
    CONSONANT_CHAR_TYPE: CONSONANT_CHAR_TYPE2,
    NUMBER_CHAR_TYPE: NUMBER_CHAR_TYPE2,
    CLAUSE_CHAR_TYPE: CLAUSE_CHAR_TYPE2,
    ALPHA_NUM_CHAR_TYPE: ALPHA_NUM_CHAR_TYPE2,
    VOWEL_NON_Y_TYPE: VOWEL_NON_Y_TYPE2,
    SOME_PUNCT_TYPE: SOME_PUNCT_TYPE2,
    SET_CHAR_TYPE: SET_CHAR_TYPE2,
    EXACT_CHAR_TYPE: EXACT_CHAR_TYPE2,
    EXACT_CASE_TYPE: EXACT_CASE_TYPE2,
    HEXADECIMAL_TYPE: HEXADECIMAL_TYPE2,
    SAVE_CHAR_TYPE: SAVE_CHAR_TYPE2,
}


def par_get_char_type(c: int) -> int:
    """Return the char-type code for a CMD-rule delimiter byte.

    Faithful translation of:

    .. code-block:: c

        int par_get_char_type(unsigned char c) {
            switch (c) {
                case DIGIT_CHAR_DELIM:        return DIGIT_CHAR_TYPE;
                case UPPER_CHAR_DELIM:        return UPPER_CHAR_TYPE;
                // ... 20 more cases ...
                case NO_LOOKAHEAD:            return NO_LOOKAHEAD;
                default:                       return NULL_TYPE;
            }
        }

    The mapping covers all 20 CMD char-type delimiters plus the
    sentinel ``NO_LOOKAHEAD``. Any other byte returns
    :data:`NULL_TYPE`.

    Args:
        c: A single byte (0..255) from the rule file.

    Returns:
        The numeric char-type code (a TYPE_* bit-flag, one of the
        non-bit SET/EXACT/CASE/HEX/SAVE sentinels, or
        :data:`NO_LOOKAHEAD`) or :data:`NULL_TYPE` for unknown bytes.
    """
    return _CHAR_TYPE_MAP.get(c, NULL_TYPE)


def par_get_state(c: int) -> int:
    """Return the action-state code for a CMD-rule delimiter byte.

    Faithful translation of:

    .. code-block:: c

        int par_get_state(unsigned char c) {
            switch (c) {
                case COPY_DELIMITER:           return COPY_STATE;
                case REPLACE_DELIMITER:        return REPLACE_STATE;
                // ... 11 cases total ...
                default:                        return NULL_STATE;
            }
        }

    Args:
        c: A single byte (0..255) from the rule file.

    Returns:
        The numeric action-state code (COPY, REPLACE, DELETE,
        INSERT, INSERT_AFTER, INSERT_BEFORE, OPTIONAL, SAVE, MACRO,
        DICTIONARY, WORD, STATUS) or :data:`NULL_STATE` for unknown
        bytes.
    """
    return _STATE_MAP.get(c, NULL_STATE)


def par_convert_to_new(i: int) -> int:
    """Map a sparse TYPE_* code to its zero-based TYPE2 index.

    Faithful translation of:

    .. code-block:: c

        short par_convert_to_new(unsigned short i) {
            switch (i) {
                case DIGIT_CHAR_TYPE:   return DIGIT_CHAR_TYPE2;
                // ... 19 more cases ...
                default:                 return -1;
            }
        }

    The C ``short`` return preserves the ``-1`` sentinel; in Python
    we keep it as a plain ``int``.

    Args:
        i: A TYPE_* char-type code as returned by
            :func:`par_get_char_type`.

    Returns:
        Zero-based 0..19 index for use in compact rule-action
        tables, or ``-1`` if ``i`` isn't a recognised TYPE_* code.
    """
    return _TYPE_TO_TYPE2_MAP.get(i, -1)


__all__ = ["par_convert_to_new", "par_get_char_type", "par_get_state"]
