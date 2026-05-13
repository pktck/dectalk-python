"""``par_match_string`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 4228-4438.

Top-level dispatcher for the rule-engine matcher family. Given an
operation code (``char_type``) parsed from the rule's opcode byte,
the function decides which specialised matcher to call:

* ``char_type <= BIN_DIGIT`` — dispatches to :func:`par_match_digits`
  when ``BIN_DIGIT_RANGE`` is set, otherwise to
  :func:`par_match_standard`.
* ``BIN_EXACT`` — compares ``value`` bytes literally (case-folded if
  ``BIN_CASE_INSEN``); writes ``ret_value->value = FAIL`` /
  ``OPT_FAIL`` on mismatch.
* ``BIN_HEXADECIMAL`` — single-byte literal compare.
* ``BIN_RESTORE`` — re-emits the bytes previously saved into
  ``match_array.array[value]`` and bails if they don't match.
* fallthrough (``BIN_SETS``) — delegates to
  :func:`par_match_sets_with_ranges`.

After dispatching, ``ret_value.value`` is set to ``OPT_FAIL`` (when
``optional == 1``) or ``FAIL`` if no bytes matched, and ``length =
-2`` -- which the caller treats as a "zero-length success" -- is
collapsed to ``0`` here so the post-dispatch state is uniform.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import (
    BIN_CASE_INSEN,
    BIN_DIGIT,
    BIN_DIGIT_RANGE,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_RESTORE,
)
from dectalk.cmd.par_match_digits import par_match_digits
from dectalk.cmd.par_match_sets_with_ranges import par_match_sets_with_ranges
from dectalk.cmd.par_match_standard import par_match_standard
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FAIL, OPT_FAIL
from dectalk.lts.char_features import ls_lower as par_lower

_ZERO_LENGTH_SUCCESS = -2


def par_match_string(  # noqa: PLR0911, PLR0912, PLR0915 — mirrors the C source's per-opcode dispatch
    current_rule: bytes,
    char_type: int,
    input_array: bytes,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    lookahead: int,
    break_on_min_match: int,
) -> int:
    r"""Dispatch on ``char_type`` to one of the matcher specialisations.

    Faithful translation of:

    .. code-block:: c

        int par_match_string(register unsigned char *current_rule, int char_type,
                             unsigned char *input_array,
                             pmatch_arrays_t match_array,
                             preturn_value_t ret_value,
                             prange_value_t range_value,
                             int lookahead, int break_on_min_match)
        {
            int rule_p = ret_value->rule;
            int ipos = ret_value->input_pos + ret_value->input_offset;
            int length = 0, value;

            if (char_type <= BIN_DIGIT) {
                if (current_rule[rule_p] & BIN_DIGIT_RANGE)
                    length = par_match_digits(current_rule, input_array,
                                              match_array, ret_value, range_value,
                                              lookahead, break_on_min_match);
                else
                    length = par_match_standard(current_rule, char_type, input_array,
                                                match_array, ret_value,
                                                lookahead, break_on_min_match);
                rule_p = ret_value->rule;
            } else if (char_type <= BIN_HEXADECIMAL) {
                if (char_type == BIN_EXACT) {
                    rule_p++;  length = 0;
                    value = current_rule[rule_p];  rule_p++;
                    if (current_rule[ret_value->rule] & BIN_CASE_INSEN) {
                        while (length < value) {
                            if (par_lower[current_rule[rule_p]]
                                != par_lower[input_array[ipos+length]]) {
                                ret_value->value =
                                    (ret_value->optional==1) ? OPT_FAIL : FAIL;
                                return 0;
                            }
                            length++; rule_p++;
                        }
                    } else {
                        if (current_rule[rule_p] != input_array[ipos]) ...FAIL...
                        if (memcmp(input_array+ipos, current_rule+rule_p, value)!=0)
                            ...FAIL...
                        rule_p += value; length = value;
                    }
                } else {  /* BIN_HEXADECIMAL */
                    rule_p++;
                    if (input_array[ipos] != current_rule[rule_p]) ...FAIL...
                    length = 1; rule_p++;
                }
            } else if (char_type == BIN_RESTORE) {
                rule_p++;
                value = current_rule[rule_p];
                length = match_array->array_lengths[value];
                if (memcmp(input_array+ipos, match_array->array[value], length)!=0)
                    ...FAIL...
                rule_p++;
            } else {  /* BIN_SETS */
                length = par_match_sets_with_ranges(current_rule, input_array,
                                                    match_array, ret_value,
                                                    range_value, lookahead,
                                                    break_on_min_match);
                rule_p = ret_value->rule;
            }

            if (length == 0)
                ret_value->value = (ret_value->optional==1) ? OPT_FAIL : FAIL;
            if (length == -2) length = 0;
            ret_value->rule = rule_p;
            return length;
        }

    Args:
        current_rule: Compiled rule bytes.
        char_type: ``BIN_*`` operation code extracted from the
            opcode byte by the caller.
        input_array: Input text bytes.
        match_array: Saved-string buffers (``$N`` slots).
        ret_value: Caller recursion state; mutated in place.
        range_value: Range tracker (used by the digit / sets paths).
        lookahead: Pass ``1`` to enable :func:`par_look_ahead`.
        break_on_min_match: Stop at first ``min_range`` hit.

    Returns:
        Byte count matched. ``-1`` (end-of-input) and the C source's
        ``-2`` (zero-length success) are both collapsed: ``-1`` is
        returned as-is, ``-2`` is rewritten to ``0`` to mirror the C
        post-condition; on a hard failure the function returns ``0``
        and sets ``ret_value.value`` to :data:`FAIL` / :data:`OPT_FAIL`.
    """
    rule_p = ret_value.rule
    ipos = ret_value.input_pos + ret_value.input_offset
    length = 0

    if char_type <= BIN_DIGIT:
        if current_rule[rule_p] & BIN_DIGIT_RANGE:
            length = par_match_digits(
                current_rule,
                input_array,
                match_array,
                ret_value,
                range_value,
                lookahead,
                break_on_min_match,
            )
        else:
            length = par_match_standard(
                current_rule,
                char_type,
                input_array,
                match_array,
                ret_value,
                lookahead,
                break_on_min_match,
            )
        rule_p = ret_value.rule
    elif char_type <= BIN_HEXADECIMAL:
        if char_type == BIN_EXACT:
            rule_p += 1
            length = 0
            value = current_rule[rule_p]
            rule_p += 1
            if current_rule[ret_value.rule] & BIN_CASE_INSEN:
                while length < value:
                    if par_lower[current_rule[rule_p]] != par_lower[input_array[ipos + length]]:
                        ret_value.value = OPT_FAIL if ret_value.optional == 1 else FAIL
                        return 0
                    length += 1
                    rule_p += 1
            else:
                if current_rule[rule_p] != input_array[ipos]:
                    ret_value.value = OPT_FAIL if ret_value.optional == 1 else FAIL
                    return 0
                if bytes(input_array[ipos : ipos + value]) != bytes(
                    current_rule[rule_p : rule_p + value]
                ):
                    ret_value.value = OPT_FAIL if ret_value.optional == 1 else FAIL
                    return 0
                rule_p += value
                length = value
        else:
            # BIN_HEXADECIMAL
            rule_p += 1
            if input_array[ipos] != current_rule[rule_p]:
                ret_value.value = OPT_FAIL if ret_value.optional == 1 else FAIL
                return 0
            length = 1
            rule_p += 1
    elif char_type == BIN_RESTORE:
        rule_p += 1
        value = current_rule[rule_p]
        length = match_array.array_lengths[value]
        if bytes(input_array[ipos : ipos + length]) != bytes(match_array.array[value][:length]):
            if ret_value.optional == 1:
                ret_value.value = OPT_FAIL
                return 0
            ret_value.value = FAIL
            return 0
        rule_p += 1
    else:
        # BIN_SETS
        length = par_match_sets_with_ranges(
            current_rule,
            input_array,
            match_array,
            ret_value,
            range_value,
            lookahead,
            break_on_min_match,
        )
        rule_p = ret_value.rule

    if length == 0:
        ret_value.value = OPT_FAIL if ret_value.optional == 1 else FAIL
    if length == _ZERO_LENGTH_SUCCESS:
        length = 0

    ret_value.rule = rule_p
    return length


__all__ = ["par_match_string"]
