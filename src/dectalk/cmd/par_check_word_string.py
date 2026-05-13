"""``par_check_word_string`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 3001-3070.

Tests whether the matched span in ``output_array`` looks like a
word: at least one vowel, at least one consonant, length ≥ 2, and
all alpha. Sets ``ret_value.value = FAIL`` if not.

Used by the ``WORD_STATE`` rule keyword to reject matches that
the engine shouldn't treat as English words.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import ReturnValue
from dectalk.cmd.parser_tables import (
    TYPE_alpha,
    TYPE_consonant,
    TYPE_vowel,
    parser_char_types,
)
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL

_MIN_WORD_LEN = 2


def par_check_word_string(
    output_array: bytes,
    ret_value: ReturnValue,
) -> None:
    """Mark the match as FAIL if it doesn't look like a word.

    Faithful translation of:

    .. code-block:: c

        void par_check_word_string(unsigned char *output_array,
                                   preturn_value_t ret_value) {
            int i, has_cons = 0, has_vowel = 0;
            if (ret_value->optional != -1) {
                i = ret_value->output_pos;
                while (i < (ret_value->output_offset + ret_value->output_pos)
                       && (has_cons == 0 || has_vowel == 0)) {
                    if (parser_char_types[output_array[i]] & TYPE_consonant)
                        has_cons = 1;
                    if (parser_char_types[output_array[i]] & TYPE_vowel)
                        has_vowel = 1;
                    if ((parser_char_types[output_array[i]] & TYPE_alpha) == 0) {
                        ret_value->value = FAIL;
                        return;
                    }
                    i++;
                }
                if (!(has_cons && has_vowel && ret_value->output_offset >= 2))
                    ret_value->value = FAIL;
            }
        }

    Args:
        output_array: Output buffer; the span at
            ``output_pos..output_pos+output_offset`` is checked.
        ret_value: Position tracker; ``ret_value.value`` is set
            to :data:`FAIL` on a non-word, otherwise unchanged.
    """
    if len(output_array) == 0:
        ret_value.value = FATAL_FAIL
        return

    if ret_value.optional == -1:
        return

    has_cons = False
    has_vowel = False
    start = ret_value.output_pos
    end = start + ret_value.output_offset

    i = start
    while i < end and not (has_cons and has_vowel):
        if i >= len(output_array):
            break
        byte = output_array[i]
        char_type = parser_char_types[byte]
        if char_type & TYPE_consonant:
            has_cons = True
        if char_type & TYPE_vowel:
            has_vowel = True
        if (char_type & TYPE_alpha) == 0:
            ret_value.value = FAIL
            return
        i += 1

    if not (has_cons and has_vowel and ret_value.output_offset >= _MIN_WORD_LEN):
        ret_value.value = FAIL


__all__ = ["par_check_word_string"]
