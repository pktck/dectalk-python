"""``par_match_standard`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 5110-5386.

Standard character-class matcher: walks the size descriptors packed
after the operation byte and consumes ``input_array[ipos+...]`` while
``parser_char_types[byte] & new_char_type`` reports a hit (or miss,
when ``BIN_COMPLIMENT`` flips the polarity). The dispatch is
identical to :func:`par_match_digits` modulo the per-character test
function; :func:`par_match_string` chooses between them based on the
``BIN_DIGIT_RANGE`` flag.

Returns ``-2`` for a zero-length successful match,
``-1`` when the input pointer hits NUL, and the byte count otherwise.
Sets ``ret_value->rule`` to one past the consumed descriptor block on
success. The look-ahead helper for the *next* character class is
:func:`par_look_ahead`, which is invoked at every iteration once
``min_range`` is hit so the matcher can stop early when the rest of
the rule would still match.
"""

from __future__ import annotations

import sys

from dectalk.cmd.par_bin_codes import (
    BIN_COMPLIMENT,
    BIN_LARGE_ANY_NUMBER,
    BIN_LARGE_CONTINUE,
    BIN_LARGE_DESC,
    BIN_LOOK_FROM_DISABLE,
    BIN_MAX_LARGE_DESC,
    BIN_MAX_SMALL_DESC,
    BIN_SIZE_DESC_MASK,
    BIN_SMALL_ANY_NUMBER,
    BIN_SMALL_CONTINUE,
)
from dectalk.cmd.par_look_ahead import par_look_ahead
from dectalk.cmd.par_structs import MatchArrays, ReturnValue
from dectalk.cmd.parser_tables import char_type_table, parser_char_types

_INT_MAX = sys.maxsize

# ``-2`` is the C source's "zero-length successful match" sentinel for
# the matcher dispatcher.  Mirrors the comparison in par_match_string.
_ZERO_LENGTH_SUCCESS = -2


def _get_short(buf: bytes, idx: int) -> int:
    """Little-endian 16-bit decode (Linux ``get_short`` macro)."""
    return buf[idx] | (buf[idx + 1] << 8)


def par_match_standard(  # noqa: PLR0912, PLR0915 — mirrors a 270-line C state machine
    current_rule: bytes,
    char_type: int,
    input_array: bytes,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    lookahead: int,
    break_on_min_match: int,
) -> int:
    r"""Match a standard character-class against the input.

    Faithful translation of:

    .. code-block:: c

        int par_match_standard(unsigned char *current_rule, int char_type,
                               unsigned char *input_array,
                               pmatch_arrays_t match_array,
                               preturn_value_t ret_value,
                               int lookahead, int break_on_min_match)
        {
            int rule_p = ret_value->rule;
            int in_rule_p = rule_p;
            int ipos = ret_value->input_pos + ret_value->input_offset;
            int length=0, min_range=-1, max_range=-1, match_is_over=0;
            int satisfied_min_cond=-1, new_char_type=char_type_table[char_type];
            int i=0, counter=0, match_non_match=1, temp, temp2, large_desc=0;
            int next_type=0, num_desc;

            if (current_rule[rule_p] & BIN_LOOK_FROM_DISABLE)  lookahead = 0;
            rule_p++;
            temp = current_rule[rule_p];
            if (temp & BIN_COMPLIMENT)  match_non_match = 0;
            if (temp & BIN_LARGE_DESC)  large_desc = 1;
            num_desc = temp & BIN_SIZE_DESC_MASK;
            rule_p++;
            if (lookahead != 0) {
                next_type = current_rule[rule_p];
                rule_p++;
            }
            while (counter < num_desc && match_is_over == 0) {
                /* decode min_range, max_range; advance rule_p, counter */
                ...
                if (min_range == 0) {
                    satisfied_min_cond = -2;
                    if (length == 0 && lookahead) {
                        if (par_look_ahead(...) == 1) break;
                    }
                }
                for (i=length; i<max_range; i++) {
                    temp2 = input_array[ipos+i];
                    if (match_non_match)
                        if ((parser_char_types[temp2] & new_char_type)==0 || temp2=='\0')
                            { match_is_over = 1; break; }
                    else
                        if ((parser_char_types[temp2] & new_char_type)!=0 || temp2=='\0')
                            { match_is_over = 1; break; }
                    temp = i+1;
                    if (temp >= min_range) {
                        satisfied_min_cond = length = temp;
                        if (break_on_min_match == 1) { match_is_over=1; break; }
                        if (lookahead && (counter<num_desc || temp<max_range)) {
                            if (par_look_ahead(...) == 1) { match_is_over=1; break; }
                        }
                    }
                }
            }
            if (satisfied_min_cond == -1)  return 0;
            if (satisfied_min_cond == -2 && length == 0)  length = -2;
            else if (input_array[ipos+i]=='\0' && length == 0)  return -1;
            if (counter != num_desc) {
                temp = in_rule_p + 2 + (lookahead?1:0) +
                       (large_desc ? (num_desc<<1) : num_desc);
                rule_p = temp;
            }
            ret_value->rule = rule_p;
            return length;
        }

    Args:
        current_rule: Compiled rule bytes.
        char_type: ``BIN_*`` operation code (low 5 bits of the rule
            byte). Indexes into :data:`char_type_table` to translate
            into a ``TYPE_*`` bit pattern.
        input_array: Input text bytes.
        match_array: Passed through to the look-ahead helper.
        ret_value: Recursion state; ``rule`` is advanced past the
            descriptor block on success.
        lookahead: Pass ``1`` to enable :func:`par_look_ahead` calls;
            cleared automatically when ``BIN_LOOK_FROM_DISABLE`` is set.
        break_on_min_match: Stop at the first ``min_range``-satisfying
            position (used by the dispatcher's look-ahead callers).

    Returns:
        Byte count matched, ``-1`` at end-of-input, ``-2`` for a
        zero-length success, or ``0`` on failure.
    """
    rule_p = ret_value.rule
    in_rule_p = rule_p
    ipos = ret_value.input_pos + ret_value.input_offset

    new_char_type = char_type_table[char_type]
    if current_rule[rule_p] & BIN_LOOK_FROM_DISABLE:
        lookahead = 0
    rule_p += 1  # move past operation byte
    temp = current_rule[rule_p]

    match_non_match = 1
    if temp & BIN_COMPLIMENT:
        match_non_match = 0
    large_desc = 0
    if temp & BIN_LARGE_DESC:
        large_desc = 1
    num_desc = temp & BIN_SIZE_DESC_MASK
    counter = 0
    rule_p += 1  # move past number-of-descriptors

    next_type = 0
    if lookahead != 0:
        next_type = current_rule[rule_p]
        rule_p += 1

    length = 0
    min_range = -1
    max_range = -1
    match_is_over = 0
    satisfied_min_cond = -1
    i = 0  # exposed after the loop for the "ipos+i == NUL" check

    while counter < num_desc and match_is_over == 0:
        if large_desc:
            temp = _get_short(current_rule, rule_p)
            rule_p += 2
            counter += 1
            min_range = temp & BIN_MAX_LARGE_DESC
            max_range = min_range
            if temp & BIN_LARGE_ANY_NUMBER:
                max_range = _INT_MAX
            elif temp & BIN_LARGE_CONTINUE:
                temp = _get_short(current_rule, rule_p)
                rule_p += 2
                counter += 1
                max_range = temp & BIN_MAX_LARGE_DESC
                if temp & BIN_LARGE_ANY_NUMBER:
                    max_range = _INT_MAX
        else:
            temp = current_rule[rule_p]
            rule_p += 1
            counter += 1
            min_range = temp & BIN_MAX_SMALL_DESC
            max_range = min_range
            if temp & BIN_SMALL_ANY_NUMBER:
                max_range = _INT_MAX
            elif temp & BIN_SMALL_CONTINUE:
                temp = current_rule[rule_p]
                rule_p += 1
                counter += 1
                max_range = temp & BIN_MAX_SMALL_DESC
                if temp & BIN_SMALL_ANY_NUMBER:
                    max_range = _INT_MAX

        if min_range == 0:
            satisfied_min_cond = _ZERO_LENGTH_SUCCESS
            if (
                length == 0
                and lookahead
                and par_look_ahead(
                    current_rule, input_array, ipos, next_type, match_array, ret_value
                )
                == 1
            ):
                break

        i = length
        # Read input bytes safely; sentinel-0 takes the place of the
        # C source's reliance on a NUL-terminated buffer.
        while i < max_range:
            temp2 = input_array[ipos + i] if ipos + i < len(input_array) else 0
            if match_non_match == 1:
                fail = (parser_char_types[temp2] & new_char_type) == 0 or temp2 == 0
            else:
                fail = (parser_char_types[temp2] & new_char_type) != 0 or temp2 == 0
            if fail:
                match_is_over = 1
                break
            temp = i + 1
            if temp >= min_range:
                satisfied_min_cond = temp
                length = temp
                if break_on_min_match == 1:
                    match_is_over = 1
                    break
                if (
                    lookahead
                    and (counter < num_desc or temp < max_range)
                    and par_look_ahead(
                        current_rule,
                        input_array,
                        ipos + temp,
                        next_type,
                        match_array,
                        ret_value,
                    )
                    == 1
                ):
                    match_is_over = 1
                    break
            i += 1

    if satisfied_min_cond == -1:
        return 0
    if satisfied_min_cond == _ZERO_LENGTH_SUCCESS:
        if length == 0:
            length = _ZERO_LENGTH_SUCCESS
    else:
        # i is the last loop index; "input_array[ipos+i] == 0" is the
        # NUL-terminator probe the C source uses to flag end-of-input.
        sentinel = input_array[ipos + i] if 0 <= ipos + i < len(input_array) else 0
        if sentinel == 0 and length == 0:
            return -1

    if counter != num_desc:
        temp = in_rule_p + 2
        if lookahead:
            temp += 1
        if large_desc:
            temp += num_desc << 1
        else:
            temp += num_desc
        rule_p = temp

    ret_value.rule = rule_p
    return length


__all__ = ["par_match_standard"]
