"""``par_match_sets_with_ranges`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 5702-5959.

Drives the ``[...]{min,max}`` style "set with ranges" matcher. The
function walks each ``<min,max>`` descriptor packed into the rule
just after the ``BIN_SETS`` opcode and calls :func:`par_match_set`
repeatedly until the match either runs out of input, exceeds
``max_range``, or satisfies ``min_range``.

The descriptor encoding mirrors the one used by
:func:`par_match_standard` and :func:`par_match_digits`: a single
byte (or two for ``BIN_LARGE_DESC``) where the low 6 / 14 bits hold
the size and the top bits flag ``BIN_*_ANY_NUMBER`` (use ``INT_MAX``)
or ``BIN_*_CONTINUE`` (read another descriptor for the upper bound).

The Linux build always activates this path via the
``BIN_SETS`` branch of :func:`par_match_string`.
"""

from __future__ import annotations

import sys

from dectalk.cmd.par_bin_codes import (
    BIN_LARGE_ANY_NUMBER,
    BIN_LARGE_CONTINUE,
    BIN_LARGE_DESC,
    BIN_MAX_LARGE_DESC,
    BIN_MAX_SMALL_DESC,
    BIN_SIZE_DESC_MASK,
    BIN_SMALL_ANY_NUMBER,
    BIN_SMALL_CONTINUE,
)
from dectalk.cmd.par_match_set import par_match_set
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FAIL, SUCCESS

_INT_MAX = sys.maxsize

# Mirror of the C source's "zero-length successful match" sentinel.
_ZERO_LENGTH_SUCCESS = -2


def _get_short(buf: bytes, idx: int) -> int:
    """Little-endian 16-bit decode (Linux ``get_short`` macro)."""
    return buf[idx] | (buf[idx + 1] << 8)


def par_match_sets_with_ranges(  # noqa: PLR0912, PLR0915 — mirrors a 250-line C state machine
    current_rule: bytes,
    input_array: bytes,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    lookahead: int,
    break_on_min_match: int,
) -> int:
    r"""Match a ``BIN_SETS`` operation against the input.

    Faithful translation of:

    .. code-block:: c

        int par_match_sets_with_ranges(unsigned char *current_rule,
                                       unsigned char *input_array,
                                       pmatch_arrays_t match_array,
                                       preturn_value_t ret_value,
                                       prange_value_t range_value,
                                       int lookahead,
                                       int break_on_min_match)
        {
            int rule_p, times=0, length=0, ipos, total_length=0;
            int min_range=-1, max_range=-1, match_is_over=0;
            int satisfied_min_cond=-1, i=0, temp, counter;
            int sect_p, section_p, end_of_all_types, num_desc, large_desc;
            return_value_t new_ret = {0,0,0,0,0,0,0,0,NULL};

            rule_p = ret_value->rule;
            ipos   = ret_value->input_pos + ret_value->input_offset;
            rule_p++;
            new_ret.input_pos = ret_value->input_pos + ret_value->input_offset;
            new_ret.output_pos = ret_value->output_pos + ret_value->output_offset;
            new_ret.value = SUCCESS;
            section_p = rule_p;
            end_of_all_types = current_rule[section_p + current_rule[rule_p]] + 1;
            rule_p += current_rule[rule_p] + 1;

            if (current_rule[rule_p] & BIN_LARGE_DESC) {
                large_desc = 1;
                sect_p = rule_p + (current_rule[rule_p] << 1) + 1;
            } else {
                large_desc = 0;
                sect_p = rule_p + current_rule[rule_p] + 1;
            }
            num_desc = current_rule[rule_p] & BIN_SIZE_DESC_MASK;
            counter = 0;
            rule_p++;
            while (counter < num_desc && match_is_over == 0) {
                /* read one (or two) descriptor entries -> min_range,max_range */
                ...
                if (min_range == 0) {
                    satisfied_min_cond = _ZERO_LENGTH_SUCCESS;
                    if (break_on_min_match == 1) break;
                }
                for (i=times; i<max_range; i++) {
                    length = par_match_set(current_rule,input_array,section_p,
                                           sect_p,ipos,match_array,range_value,
                                           &new_ret,lookahead);
                    if (length == -1) {
                        match_is_over = 1;
                        if (satisfied_min_cond > 0)  length = total_length;
                        else                         total_length = -1;
                        break;
                    }
                    if (length == 0 && new_ret.value == SUCCESS) {
                        if (total_length == 0) {
                            satisfied_min_cond = _ZERO_LENGTH_SUCCESS;
                            match_is_over = 1;
                            break;
                        }
                    }
                    if (length > 0) { ipos += length; total_length += length; }
                    if (new_ret.value == FAIL) { match_is_over = 1; break; }
                    if (i+1 >= min_range) {
                        satisfied_min_cond = total_length;
                        times = i+1;
                        if (break_on_min_match == 1) { match_is_over=1; break; }
                    } else {
                        if (length == 0) { match_is_over = 1; break; }
                    }
                }
            }
            rule_p = end_of_all_types;
            if (satisfied_min_cond == -1) return 0;
            if (satisfied_min_cond == -2 && total_length == 0)  total_length = -2;
            else if (input_array[ipos] == '\0' && total_length == 0) return -1;
            ret_value->rule = rule_p;
            return total_length;
        }

    Args:
        current_rule: Compiled rule bytes.
        input_array: Input text bytes.
        match_array: Saved-string buffers.
        ret_value: Caller's recursion state; ``rule`` is advanced past
            the ``BIN_SETS`` block on success.
        range_value: Range tracker (passed through to ``par_match_set``).
        lookahead: Passed through to ``par_match_set``.
        break_on_min_match: Stop processing on first ``min_range`` hit.

    Returns:
        Total bytes matched, ``-1`` at end-of-input, ``-2`` for a
        zero-length success, or ``0`` on a hard failure.
    """
    rule_p = ret_value.rule
    ipos = ret_value.input_pos + ret_value.input_offset

    # Skip past the type delimiter. The C source's SANITY_CHECKING block
    # validates the pointers — Python's type system makes that
    # redundant, so we only carry the FATAL_FAIL constant for the
    # downstream branches that still use it.
    rule_p += 1

    new_ret = ReturnValue(
        input_pos=ret_value.input_pos + ret_value.input_offset,
        output_pos=ret_value.output_pos + ret_value.output_offset,
        value=SUCCESS,
    )

    section_p = rule_p
    end_of_all_types = current_rule[section_p + current_rule[rule_p]] + 1
    rule_p += current_rule[rule_p] + 1

    if current_rule[rule_p] & BIN_LARGE_DESC:
        large_desc = True
        sect_p = rule_p + (current_rule[rule_p] << 1) + 1
    else:
        large_desc = False
        sect_p = rule_p + current_rule[rule_p] + 1

    num_desc = current_rule[rule_p] & BIN_SIZE_DESC_MASK
    counter = 0
    rule_p += 1

    times = 0
    length = 0
    total_length = 0
    min_range = -1
    max_range = -1
    match_is_over = 0
    satisfied_min_cond = -1

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
            if break_on_min_match == 1:
                break

        i = times
        while i < max_range:
            length = par_match_set(
                current_rule,
                input_array,
                section_p,
                sect_p,
                ipos,
                match_array,
                range_value,
                new_ret,
                lookahead,
            )
            if length == -1:
                match_is_over = 1
                if satisfied_min_cond > 0:
                    length = total_length
                else:
                    total_length = -1
                break
            if length == 0 and new_ret.value == SUCCESS and total_length == 0:
                satisfied_min_cond = _ZERO_LENGTH_SUCCESS
                match_is_over = 1
                break
            if length > 0:
                ipos += length
                total_length += length
            if new_ret.value == FAIL:
                match_is_over = 1
                break
            if (i + 1) >= min_range:
                satisfied_min_cond = total_length
                times = i + 1
                if break_on_min_match == 1:
                    match_is_over = 1
                    break
            elif length == 0:
                match_is_over = 1
                break
            i += 1

    rule_p = end_of_all_types

    if satisfied_min_cond == -1:
        return 0
    if satisfied_min_cond == _ZERO_LENGTH_SUCCESS:
        if total_length == 0:
            total_length = _ZERO_LENGTH_SUCCESS
    elif ipos < len(input_array) and input_array[ipos] == 0 and total_length == 0:
        return -1

    ret_value.rule = rule_p
    return total_length


__all__ = ["par_match_sets_with_ranges"]
