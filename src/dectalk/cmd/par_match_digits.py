"""``par_match_digits`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 5416-5672.

The digit-range matcher: ``D[min,max]`` and friends. Each descriptor
records a numeric range and the matcher accepts the longest prefix
of digits whose ``int`` value falls in ``[min, max]``. The struct
:class:`RangeValue` records the range across descriptors so the
``<#>`` substitution can later replace one number with another in a
sliding interval.

The digit-length / range-set interplay is delicate:

* ``range_set == 0`` — first descriptor, store ``min_range`` as ``start``.
* ``range_set == 1`` — additional descriptor; bump ``start`` by the
  inter-range gap.
* ``range_set == 2`` — coming back from a multi-section ``par_match_set``
  hit; clear to ``-1`` to flag "no inherited range".

The function uses :func:`par_get_int_length` (in
:mod:`dectalk.cmd.par_number`) to turn the bound integers into byte
lengths once the descriptors are parsed.
"""

from __future__ import annotations

import sys

from dectalk.cmd.par_bin_codes import (
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
from dectalk.cmd.par_number import par_convert_number, par_get_int_length
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.parser_tables import TYPE_digit, parser_char_types

_INT_MAX = sys.maxsize


def _get_short(buf: bytes, idx: int) -> int:
    """Little-endian 16-bit decode (Linux ``get_short`` macro)."""
    return buf[idx] | (buf[idx + 1] << 8)


def par_match_digits(  # noqa: PLR0912, PLR0915 — straight-line port of a 250-line C state machine
    current_rule: bytes,
    input_array: bytes,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    lookahead: int,
    break_on_min_match: int,
) -> int:
    r"""Match a digit range against the input.

    Faithful translation of:

    .. code-block:: c

        int par_match_digits(unsigned char *current_rule,
                             unsigned char *input_array,
                             pmatch_arrays_t match_array,
                             preturn_value_t ret_value,
                             prange_value_t range_value,
                             int lookahead, int break_on_min_match)
        {
            int rule_p = ret_value->rule;
            int in_rule_p = rule_p;
            int ipos = ret_value->input_pos + ret_value->input_offset;
            int length=0, min_range=-1, max_range=-1, match_is_over=0;
            int satisfied_min_cond=-1, satisfied_start=-1, temp_num=0;
            int new_char_type = char_type_table[BIN_DIGIT];
            int i=0, counter=0, temp, next_type=0, num_desc, large_desc=0;

            if (current_rule[rule_p] & BIN_LOOK_FROM_DISABLE)  lookahead = 0;
            rule_p++;
            if (current_rule[rule_p] & BIN_LARGE_DESC)  large_desc = 1;
            num_desc = current_rule[rule_p] & BIN_SIZE_DESC_MASK;
            rule_p++;
            if (lookahead != 0) { next_type = current_rule[rule_p]; rule_p++; }
            while (counter < num_desc && match_is_over == 0) {
                /* decode min_range, max_range */
                ...
                /* update range_value */
                if (range_value->range_set == 0) {
                    range_value->range_set = 1;
                    range_value->start = min_range;
                } else {
                    if (range_value->range_set == 2)  range_value->range_set = -1;
                    if (range_value->range_set == 1)
                        range_value->start += (min_range - range_value->end) - 1;
                }
                range_value->min = min_range;
                range_value->end = max_range;
                min_range = par_get_int_length(min_range);
                max_range = par_get_int_length(max_range);

                for (i=0; (parser_char_types[input_array[ipos+i]] & TYPE_digit) != 0
                        && (temp_num =
                            par_convert_number(input_array+ipos, i+1)) <= range_value->end
                        && i < max_range;
                     i++) {
                    if (temp_num >= range_value->min) {
                        temp = length = i+1;
                        satisfied_min_cond = temp_num;
                        satisfied_start = range_value->start;
                        if (break_on_min_match == 1) { match_is_over = 1; break; }
                        if (lookahead && (counter<num_desc || temp<max_range)) {
                            if (par_look_ahead(...) == 1) { match_is_over=1; break; }
                        }
                    }
                }
                if (temp_num > range_value->end && counter == num_desc)  break;
            }
            if (counter != num_desc) {
                temp = in_rule_p + 2 + (lookahead?1:0) +
                       (large_desc ? num_desc<<1 : num_desc);
                rule_p = temp;
            }
            if (satisfied_min_cond == -1)  return 0;
            if (range_value->start != satisfied_start)  range_value->start = satisfied_start;
            if (input_array[ipos+i] == '\0' && length == 0)  return -1;
            ret_value->rule = rule_p;
            return length;
        }

    Args:
        current_rule: Compiled rule bytes.
        input_array: Input text bytes.
        match_array: Passed through to the look-ahead helper.
        ret_value: Recursion state; ``rule`` is advanced past the
            descriptor block on success.
        range_value: Range tracker; ``start``, ``end``, ``min`` and
            ``range_set`` are mutated to record the matched range.
        lookahead: Pass ``1`` to enable :func:`par_look_ahead` calls.
        break_on_min_match: Stop at the first ``min_range``-satisfying
            position.

    Returns:
        Byte count matched, ``-1`` at end-of-input on a zero-length
        match, or ``0`` on failure. (Unlike
        :func:`par_match_standard`, this function never returns ``-2``.)
    """
    rule_p = ret_value.rule
    in_rule_p = rule_p
    ipos = ret_value.input_pos + ret_value.input_offset

    if current_rule[rule_p] & BIN_LOOK_FROM_DISABLE:
        lookahead = 0
    rule_p += 1
    large_desc = 0
    if current_rule[rule_p] & BIN_LARGE_DESC:
        large_desc = 1
    num_desc = current_rule[rule_p] & BIN_SIZE_DESC_MASK
    counter = 0
    rule_p += 1

    next_type = 0
    if lookahead != 0:
        next_type = current_rule[rule_p]
        rule_p += 1

    length = 0
    min_range = -1
    max_range = -1
    match_is_over = 0
    satisfied_min_cond = -1
    satisfied_start = -1
    temp_num = 0
    i = 0

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

        if range_value.range_set == 0:
            range_value.range_set = 1
            range_value.start = min_range
        else:
            if range_value.range_set == 2:  # noqa: PLR2004 — flag value from par_match_set
                range_value.range_set = -1
            if range_value.range_set == 1:
                range_value.start += (min_range - range_value.end) - 1
        range_value.min = min_range
        range_value.end = max_range
        min_range = par_get_int_length(min_range)
        max_range = par_get_int_length(max_range)

        i = 0
        # Scan the digit prefix.  Loop body skips the increment-and-test
        # rules of the C for-loop literally so the satisfaction tests
        # land on the same indices.
        while True:
            byte = input_array[ipos + i] if 0 <= ipos + i < len(input_array) else 0
            if (parser_char_types[byte] & TYPE_digit) == 0:
                break
            temp_num = par_convert_number(input_array[ipos:], i + 1)
            if temp_num > range_value.end:
                break
            if i >= max_range:
                break

            if temp_num >= range_value.min:
                temp = i + 1
                length = temp
                satisfied_min_cond = temp_num
                satisfied_start = range_value.start
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

        if temp_num > range_value.end and counter == num_desc:
            break

    if counter != num_desc:
        temp = in_rule_p + 2
        if lookahead:
            temp += 1
        if large_desc:
            temp += num_desc << 1
        else:
            temp += num_desc
        rule_p = temp

    if satisfied_min_cond == -1:
        return 0
    if range_value.start != satisfied_start:
        range_value.start = satisfied_start

    sentinel = input_array[ipos + i] if 0 <= ipos + i < len(input_array) else 0
    if sentinel == 0 and length == 0:
        return -1

    ret_value.rule = rule_p
    return length


__all__ = ["par_match_digits"]
