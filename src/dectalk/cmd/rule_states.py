"""Rule-engine state / char-type constants from par_def.h.

Translated from ``src/dapi/src/cmd/par_def.h``.

The CMD rule engine is table-driven: each rule consists of a state
section, a char-type section, an action section and a result. The
parser reads ASCII rule files, where each state and char-type is
encoded as a single delimiter character (e.g. ``'D'`` for digit,
``'c'`` for copy). The lookup functions in :mod:`par_get` convert
those delimiters to the internal numeric codes defined here.

- Action / state codes (:data:`NULL_STATE` .. :data:`STATUS_STATE`)
  and their delimiter characters (:data:`COPY_DELIMITER`,
  :data:`REPLACE_DELIMITER`, …).
- Char-type codes (aliases for :data:`TYPE_*` bit-flags from
  :mod:`parser_tables`, plus the non-bit values for SET, EXACT,
  EXACT_CASE, HEXADECIMAL, SAVE) and their delimiter characters.
"""

from __future__ import annotations

from typing import Final

from dectalk.cmd.parser_tables import (
    TYPE_alpha,
    TYPE_alpha_num,
    TYPE_any_char,
    TYPE_clause,
    TYPE_consonant,
    TYPE_digit,
    TYPE_lower,
    TYPE_non_alpha,
    TYPE_number,
    TYPE_punct,
    TYPE_punct_some,
    TYPE_upper,
    TYPE_vowel,
    TYPE_vowel_non_y,
    TYPE_white,
)

# ---- Rule-engine return codes (par_def.h FAIL/SUCCESS family) ----

FAIL: Final[int] = 0
"""Rule didn't match — try the next alternative."""

SUCCESS: Final[int] = 1
"""Rule matched — apply its action."""

OPT_FAIL: Final[int] = 2
"""Optional sub-match didn't fire (treated as success at the rule level)."""

END_OF_STRING: Final[int] = 3
"""Ran off the end of the input string mid-match."""

FATAL_FAIL: Final[int] = 4
"""Rule contains a syntax error or invariant violation."""

STOP: Final[int] = 5
"""Stop the whole parse — used by the watchdog when total work exceeds
``PAR_ROLLING_STOP_VALUE`` characters."""


# ---- Rule end-of-section markers ----

End_Is_Slash: Final[int] = ord("/")
"""Rule section ends at ``'/'`` — used by the state/char-type/action parser."""

End_Is_Null: Final[int] = 0
"""Rule section ends at NUL — used at the top level."""

End_Is_Paren: Final[int] = ord(")")
"""Rule section ends at ``')'`` — used inside save-state captures."""


# ---- Action / state codes ----

NULL_STATE: Final[int] = 0
COPY_STATE: Final[int] = 1
REPLACE_STATE: Final[int] = 2
DELETE_STATE: Final[int] = 3
INSERT_STATE: Final[int] = 4
INSERT_AFTER_STATE: Final[int] = 5
INSERT_BEFORE_STATE: Final[int] = 6
OPTIONAL_STATE: Final[int] = 7
SAVE_STATE: Final[int] = 8
MACRO_STATE: Final[int] = 9
DICTIONARY_STATE: Final[int] = 10
WORD_STATE: Final[int] = 11
STATUS_STATE: Final[int] = 12

# ---- Action / state delimiter characters (as int byte values) ----

COPY_DELIMITER: Final[int] = ord("c")
REPLACE_DELIMITER: Final[int] = ord("r")
DELETE_DELIMITER: Final[int] = ord("d")
INSERT_DELIMITER: Final[int] = ord("i")
INSERT_AFTER_DELIM: Final[int] = ord("a")
INSERT_BEFORE_DELIM: Final[int] = ord("b")
OPTIONAL_DELIMITER: Final[int] = ord("o")
MACRO_DELIMITER: Final[int] = ord("p")
DICTIONARY_STATE_DELIM: Final[int] = ord("h")
WORD_STATE_DELIM: Final[int] = ord("w")
STATUS_STATE_DELIM: Final[int] = ord("s")
START_SAVE_STATE: Final[int] = ord("(")
SAVE_DELIMITER: Final[int] = ord("$")

# ---- Char-type codes ----
#
# The first 15 are aliases for the TYPE_* bit-flags in parser_tables;
# the last 5 are non-bit-encoded values used as sentinels in
# par_def.h (out-of-range w.r.t. the 16-bit type bitmask).

NULL_TYPE: Final[int] = 0
DIGIT_CHAR_TYPE: Final[int] = TYPE_digit
UPPER_CHAR_TYPE: Final[int] = TYPE_upper
LOWER_CHAR_TYPE: Final[int] = TYPE_lower
ANY_ALPHA_CHAR_TYPE: Final[int] = TYPE_alpha
ANY_CHAR_CHAR_TYPE: Final[int] = TYPE_any_char
WHITE_CHAR_TYPE: Final[int] = TYPE_white
PUNCT_CHAR_TYPE: Final[int] = TYPE_punct
NON_ALPHA_CHAR_TYPE: Final[int] = TYPE_non_alpha
VOWEL_CHAR_TYPE: Final[int] = TYPE_vowel
CONSONANT_CHAR_TYPE: Final[int] = TYPE_consonant
NUMBER_CHAR_TYPE: Final[int] = TYPE_number
CLAUSE_CHAR_TYPE: Final[int] = TYPE_clause
ALPHA_NUM_CHAR_TYPE: Final[int] = TYPE_alpha_num
VOWEL_NON_Y_TYPE: Final[int] = TYPE_vowel_non_y
SOME_PUNCT_TYPE: Final[int] = TYPE_punct_some
SET_CHAR_TYPE: Final[int] = 9911
EXACT_CHAR_TYPE: Final[int] = 9913
EXACT_CASE_TYPE: Final[int] = 9917
HEXADECIMAL_TYPE: Final[int] = 9919
SAVE_CHAR_TYPE: Final[int] = 9923

# ---- Char-type delimiter characters ----

DIGIT_CHAR_DELIM: Final[int] = ord("D")
UPPER_CHAR_DELIM: Final[int] = ord("U")
ANY_ALPHA_CHAR_DELIM: Final[int] = ord("A")
ANY_CHAR_CHAR_DELIM: Final[int] = ord("C")
WHITE_CHAR_DELIM: Final[int] = ord("W")
PUNCT_CHAR_DELIM: Final[int] = ord("P")
LOWER_CHAR_DELIM: Final[int] = ord("L")
NON_ALPHA_CHAR_DELIM: Final[int] = ord("N")
SET_CHAR_DELIM: Final[int] = ord("S")
VOWEL_CHAR_DELIM: Final[int] = ord("V")
CONSONANT_CHAR_DELIM: Final[int] = ord("O")
NUMBER_CHAR_DELIM: Final[int] = ord("B")
CLAUSE_CHAR_DELIM: Final[int] = ord("E")
ALPHA_NUM_DELIM: Final[int] = ord("H")
VOWEL_NON_Y_DELIM: Final[int] = ord("Y")
SOME_PUNCT_DELIM: Final[int] = ord("T")
EXACT_CHAR_DELIM: Final[int] = ord("'")
EXACT_CASE_DELIM: Final[int] = ord("`")
HEXADECIMAL_DELIM: Final[int] = ord("0")
NO_LOOKAHEAD: Final[int] = ord("x")
ESCAPE_DELIM: Final[int] = ord("\\")
CONDITIONAL_DELIM: Final[int] = ord("|")
STATE_PART_DELIM: Final[int] = ord("/")

# ---- TYPE2 codes — zero-based indices for the rule-action table ----
#
# par_convert_to_new() maps each TYPE constant to a 0..19 index so
# rule tables don't waste room on the sparse bit-encoded TYPE_* values.

DIGIT_CHAR_TYPE2: Final[int] = 0
UPPER_CHAR_TYPE2: Final[int] = 1
LOWER_CHAR_TYPE2: Final[int] = 2
ANY_ALPHA_CHAR_TYPE2: Final[int] = 3
ANY_CHAR_CHAR_TYPE2: Final[int] = 4
WHITE_CHAR_TYPE2: Final[int] = 5
PUNCT_CHAR_TYPE2: Final[int] = 6
NON_ALPHA_CHAR_TYPE2: Final[int] = 7
VOWEL_CHAR_TYPE2: Final[int] = 8
CONSONANT_CHAR_TYPE2: Final[int] = 9
NUMBER_CHAR_TYPE2: Final[int] = 10
CLAUSE_CHAR_TYPE2: Final[int] = 11
ALPHA_NUM_CHAR_TYPE2: Final[int] = 12
VOWEL_NON_Y_TYPE2: Final[int] = 13
SOME_PUNCT_TYPE2: Final[int] = 14
SET_CHAR_TYPE2: Final[int] = 15
EXACT_CHAR_TYPE2: Final[int] = 16
EXACT_CASE_TYPE2: Final[int] = 17
HEXADECIMAL_TYPE2: Final[int] = 18
SAVE_CHAR_TYPE2: Final[int] = 19

# ---- Rule special-tag values --------------------------------------------

NORMAL_TAG_VALUE: Final[int] = 0
"""Rule is an ordinary table entry (no special handling)."""

STOP_TAG_VALUE: Final[int] = 1
"""Rule signals "stop processing the input"."""

RETURN_TAG_VALUE: Final[int] = 2
"""Rule signals "return from the current sub-rule"."""

GOTO_TAG_VALUE: Final[int] = 3
"""Rule signals "goto another rule by number"."""

GORET_TAG_VALUE: Final[int] = 4
"""Rule signals "call (subroutine) another rule, then return"."""

# ---- Dict-hit / dict-miss values used in dict_flag ----------------------

DICT_HIT_VALUE: Final[int] = 1
"""Rule fires only on a dictionary hit."""

DICT_MISS_VALUE: Final[int] = 0
"""Rule fires only on a dictionary miss."""

# ---- Unset sentinel -----------------------------------------------------

UNSET_PARAM: Final[int] = -1
"""Sentinel for "no parameter assigned yet" in rule fields."""

# ---- Rule-format delimiters not in the action/char-type sets ------------

RULE_NUMBER_DELIM: Final[int] = ord("R")
"""Delimiter for rule numbers (also used for macro-state processing)."""

HIT_NUMBER_DELIM: Final[int] = ord("H")
"""Delimiter for the "next rule on hit" field."""

MISS_NUMBER_DELIM: Final[int] = ord("M")
"""Delimiter for the "next rule on miss" field."""

DICTIONARY_DELIM: Final[int] = ord("D")
"""Delimiter for the dictionary-hit-required field."""

DICTIONARY_HIT: Final[int] = ord("H")
"""Indicates the rule needs a dictionary hit (alias of :data:`HIT_NUMBER_DELIM`)."""

DICTIONARY_MISS: Final[int] = ord("M")
"""Indicates the rule needs a dictionary miss (alias of :data:`MISS_NUMBER_DELIM`)."""

NON_MATCH_DELIM: Final[int] = ord("~")
"""Delimiter for the complement (NOT) of a character set."""

GORET_NUMBER_DELIM: Final[int] = ord("G")
"""Delimiter for the GORET (subroutine) rule-number field."""

GORET_HIT_DELIM: Final[int] = ord("H")
"""Delimiter for the GORET-on-hit branch."""

GORET_MISS_DELIM: Final[int] = ord("M")
"""Delimiter for the GORET-on-miss branch."""

# ---- Ambiguous-char table lookup flags ----------------------------------

NORMAL_TO_NORMAL: Final[int] = 0x01
"""Both source and target sets are in normal orientation."""

NORMAL_TO_REVERSE: Final[int] = 0x02
"""Source is normal, target is the complement (NOT) of a set."""

REVERSE_TO_NORMAL: Final[int] = 0x04
"""Source is reversed, target is normal."""

REVERSE_TO_REVERSE: Final[int] = 0x08
"""Both source and target are reversed."""

ALL_TO_ALL: Final[int] = (
    NORMAL_TO_NORMAL | NORMAL_TO_REVERSE | REVERSE_TO_NORMAL | REVERSE_TO_REVERSE
)
"""Match any source/target orientation combination."""

ALL_TO_NORMAL: Final[int] = NORMAL_TO_NORMAL | REVERSE_TO_NORMAL
"""Match any source orientation against a normal-only target."""

# ---- Phoneme-translation output codes -----------------------------------

PAR_OUTPUT_CHARS: Final[int] = 1
"""Parser produces character output."""

PAR_OUTPUT_PHONES: Final[int] = 2
"""Parser produces phoneme output."""

# ---- ASCKY phoneme-stream markers --------------------------------------

PAR_PHONES_ON_D: Final[int] = 0x81
"""Marker: start of phonemes in the rule output stream."""

PAR_PHONES_OFF_D: Final[int] = 0x82
"""Marker: end of phonemes in the rule output stream."""

PAR_INDEX_DUMMY_CHAR: Final[int] = 0x83
"""Placeholder character inserted where an index mark would go."""

# ---- Save-state end marker (paired with START_SAVE_STATE) ---------------

END_SAVE_STATE: Final[int] = ord(")")
"""End of a save-state capture group (paired with :data:`START_SAVE_STATE`)."""


__all__ = [
    "ALL_TO_ALL",
    "ALL_TO_NORMAL",
    "ALPHA_NUM_CHAR_TYPE",
    "ALPHA_NUM_CHAR_TYPE2",
    "ALPHA_NUM_DELIM",
    "ANY_ALPHA_CHAR_DELIM",
    "ANY_ALPHA_CHAR_TYPE",
    "ANY_ALPHA_CHAR_TYPE2",
    "ANY_CHAR_CHAR_DELIM",
    "ANY_CHAR_CHAR_TYPE",
    "ANY_CHAR_CHAR_TYPE2",
    "CLAUSE_CHAR_DELIM",
    "CLAUSE_CHAR_TYPE",
    "CLAUSE_CHAR_TYPE2",
    "CONDITIONAL_DELIM",
    "CONSONANT_CHAR_DELIM",
    "CONSONANT_CHAR_TYPE",
    "CONSONANT_CHAR_TYPE2",
    "COPY_DELIMITER",
    "COPY_STATE",
    "DELETE_DELIMITER",
    "DELETE_STATE",
    "DICTIONARY_DELIM",
    "DICTIONARY_HIT",
    "DICTIONARY_MISS",
    "DICTIONARY_STATE",
    "DICTIONARY_STATE_DELIM",
    "DICT_HIT_VALUE",
    "DICT_MISS_VALUE",
    "DIGIT_CHAR_DELIM",
    "DIGIT_CHAR_TYPE",
    "DIGIT_CHAR_TYPE2",
    "END_OF_STRING",
    "END_SAVE_STATE",
    "ESCAPE_DELIM",
    "EXACT_CASE_DELIM",
    "EXACT_CASE_TYPE",
    "EXACT_CASE_TYPE2",
    "EXACT_CHAR_DELIM",
    "EXACT_CHAR_TYPE",
    "EXACT_CHAR_TYPE2",
    "FAIL",
    "FATAL_FAIL",
    "GORET_HIT_DELIM",
    "GORET_MISS_DELIM",
    "GORET_NUMBER_DELIM",
    "GORET_TAG_VALUE",
    "GOTO_TAG_VALUE",
    "HEXADECIMAL_DELIM",
    "HEXADECIMAL_TYPE",
    "HEXADECIMAL_TYPE2",
    "HIT_NUMBER_DELIM",
    "INSERT_AFTER_DELIM",
    "INSERT_AFTER_STATE",
    "INSERT_BEFORE_DELIM",
    "INSERT_BEFORE_STATE",
    "INSERT_DELIMITER",
    "INSERT_STATE",
    "LOWER_CHAR_DELIM",
    "LOWER_CHAR_TYPE",
    "LOWER_CHAR_TYPE2",
    "MACRO_DELIMITER",
    "MACRO_STATE",
    "MISS_NUMBER_DELIM",
    "NON_ALPHA_CHAR_DELIM",
    "NON_ALPHA_CHAR_TYPE",
    "NON_ALPHA_CHAR_TYPE2",
    "NON_MATCH_DELIM",
    "NORMAL_TAG_VALUE",
    "NORMAL_TO_NORMAL",
    "NORMAL_TO_REVERSE",
    "NO_LOOKAHEAD",
    "NULL_STATE",
    "NULL_TYPE",
    "NUMBER_CHAR_DELIM",
    "NUMBER_CHAR_TYPE",
    "NUMBER_CHAR_TYPE2",
    "OPTIONAL_DELIMITER",
    "OPTIONAL_STATE",
    "OPT_FAIL",
    "PAR_INDEX_DUMMY_CHAR",
    "PAR_OUTPUT_CHARS",
    "PAR_OUTPUT_PHONES",
    "PAR_PHONES_OFF_D",
    "PAR_PHONES_ON_D",
    "PUNCT_CHAR_DELIM",
    "PUNCT_CHAR_TYPE",
    "PUNCT_CHAR_TYPE2",
    "REPLACE_DELIMITER",
    "REPLACE_STATE",
    "RETURN_TAG_VALUE",
    "REVERSE_TO_NORMAL",
    "REVERSE_TO_REVERSE",
    "RULE_NUMBER_DELIM",
    "SAVE_CHAR_TYPE",
    "SAVE_CHAR_TYPE2",
    "SAVE_DELIMITER",
    "SAVE_STATE",
    "SET_CHAR_DELIM",
    "SET_CHAR_TYPE",
    "SET_CHAR_TYPE2",
    "SOME_PUNCT_DELIM",
    "SOME_PUNCT_TYPE",
    "SOME_PUNCT_TYPE2",
    "START_SAVE_STATE",
    "STATE_PART_DELIM",
    "STATUS_STATE",
    "STATUS_STATE_DELIM",
    "STOP",
    "STOP_TAG_VALUE",
    "SUCCESS",
    "UNSET_PARAM",
    "UPPER_CHAR_DELIM",
    "UPPER_CHAR_TYPE",
    "UPPER_CHAR_TYPE2",
    "VOWEL_CHAR_DELIM",
    "VOWEL_CHAR_TYPE",
    "VOWEL_CHAR_TYPE2",
    "VOWEL_NON_Y_DELIM",
    "VOWEL_NON_Y_TYPE",
    "VOWEL_NON_Y_TYPE2",
    "WHITE_CHAR_DELIM",
    "WHITE_CHAR_TYPE",
    "WHITE_CHAR_TYPE2",
    "WORD_STATE",
    "WORD_STATE_DELIM",
    "End_Is_Null",
    "End_Is_Paren",
    "End_Is_Slash",
]
