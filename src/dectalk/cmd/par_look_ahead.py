"""``par_look_ahead`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 4640-4864.

The look-ahead helper the rule engine calls to peek at the *next*
character class without committing to a match. Given a target rule
offset (``find_index``) and current input position (``ipos``), it
dispatches on the operation byte at ``current_rule[find_index]`` and
returns ``1`` when the next character would satisfy that operation,
``0`` otherwise. The match arrays / ``ret_value`` cursor are passed
through but the function builds its own fresh :class:`ReturnValue`
on every call so it never mutates the caller's state on failure.

The Linux active branch uses ``BIN_EXACT`` / ``BIN_DIGIT`` /
``BIN_HEXADECIMAL`` / ``BIN_RESTORE`` / ``BIN_SETS`` / a generic
``standard`` fall-through and dictionary look-ahead. The Python port
late-binds the recursive callers (:func:`par_match_digits`,
:func:`par_match_standard`, :func:`par_match_sets_with_ranges`) so
the matcher family can be loaded without import-cycle headaches.

``par_look_ahead_dictionary`` is not yet ported; that branch is
reachable only through ``BIN_DICTIONARY`` and the C source's own
``#ifdef NEW_PARSER_FILE_LOADING`` paths.  The Python port short-
circuits dictionary look-ahead to ``0`` (no match) so we don't fail
catastrophically; the dictionary work is tracked in the inventory.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import (
    BIN_CASE_INSEN,
    BIN_DIGIT,
    BIN_DIGIT_RANGE,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_OPERATION_MASK,
    BIN_RESTORE,
    BIN_SETS,
)
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import SUCCESS
from dectalk.lts.char_features import ls_lower as par_lower


def par_look_ahead(  # noqa: PLR0911, PLR0912 — mirrors the C source's per-opcode dispatch with explicit early returns
    current_rule: bytes,
    input_array: bytes,
    ipos: int,
    find_index: int,
    match_array: MatchArrays,
    ret_value: ReturnValue,
) -> int:
    r"""Return 1 if the rule at ``find_index`` matches ``input_array[ipos]``.

    Faithful translation of:

    .. code-block:: c

        int par_look_ahead(register unsigned char *current_rule,
                           unsigned char *input_array,
                           register int ipos, int find_index,
                           pmatch_arrays_t match_array,
                           preturn_value_t ret_value)
        {
            return_value_t new_ret = {0,0,0,0,0,0,0,0,NULL};
            range_value_t  range_value = {0,0,0,0};
            int char_length=0, value;
            register int rule_p;
            int char_type;

            rule_p = find_index;
            char_type = current_rule[find_index] & BIN_OPERATION_MASK;

            if (char_type == BIN_EXACT) {
                rule_p++;
                value = current_rule[rule_p] + ipos;
                rule_p++;
                if (current_rule[find_index] & BIN_CASE_INSEN) {
                    if (par_lower[current_rule[rule_p]] != par_lower[input_array[ipos]])
                        return 0;
                    while (ipos < value) {
                        if (par_lower[current_rule[rule_p]] != par_lower[input_array[ipos]])
                            return 0;
                        ipos++; rule_p++;
                    }
                    return 1;
                } else {
                    if (current_rule[rule_p] != input_array[ipos])  return 0;
                    while (ipos < value) {
                        if (current_rule[rule_p] != input_array[ipos]) return 0;
                        ipos++; rule_p++;
                    }
                    return 1;
                }
            } else {
                if (char_type <= BIN_DIGIT) {
                    if (current_rule[find_index] & BIN_DIGIT_RANGE) {
                        new_ret.rule= find_index; new_ret.value=SUCCESS;
                        new_ret.input_pos=ipos;
                        char_length = par_match_digits(current_rule,input_array,
                                          match_array,&new_ret,&range_value,0,1);
                        if (new_ret.value==SUCCESS && char_length>0)
                            return 1;
                        return 0;
                    } else {
                        new_ret.rule= find_index; new_ret.value=SUCCESS;
                        new_ret.input_pos=ipos;
                        char_length = par_match_standard(current_rule,char_type,
                                          input_array,match_array,&new_ret,0,1);
                        if (new_ret.value==SUCCESS && char_length>0)
                            return 1;
                        return 0;
                    }
                } else {
                    if (char_type == BIN_HEXADECIMAL) {
                        rule_p++;
                        return (input_array[ipos] == current_rule[rule_p]) ? 1 : 0;
                    } else if (char_type == BIN_RESTORE) {
                        rule_p++;
                        value = current_rule[rule_p];
                        char_length = match_array->array_lengths[value];
                        if (memcmp(input_array+ipos,
                                   match_array->array[value],char_length) == 0
                            && match_array->array[value][0] != '\0')
                            return 1;
                        return 0;
                    } else if (char_type == BIN_SETS) {
                        new_ret.rule= find_index; new_ret.value=SUCCESS;
                        new_ret.input_pos=ipos;
                        char_length = par_match_sets_with_ranges(current_rule,
                                          input_array,match_array,&new_ret,
                                          &range_value,0,1);
                        if (new_ret.value==SUCCESS && char_length>0)
                            return 1;
                        return 0;
                    } else {
                        /* BIN_DICTIONARY */
                        par_copy_return_value(&new_ret, ret_value);
                        new_ret.input_pos = ipos;
                        if (par_look_ahead_dictionary(current_rule, input_array,
                                                      match_array, &new_ret))
                            return 1;
                        return 0;
                    }
                }
            }
            return 0;
        }

    Args:
        current_rule: Compiled rule bytes (read-only).
        input_array: Input text bytes (read-only).
        ipos: Position in ``input_array`` to peek at.
        find_index: Rule offset of the operation to test.
        match_array: Saved-string buffers for ``BIN_RESTORE`` look-ahead.
        ret_value: Caller's recursion state (for ``BIN_DICTIONARY``).

    Returns:
        ``1`` if the operation at ``find_index`` matches at ``ipos``,
        ``0`` otherwise.
    """
    # Late-bind to avoid an import cycle (the digit / standard / sets
    # matchers recurse back into ``par_look_ahead``).
    # ruff: noqa: PLC0415 -- circular import guard
    from dectalk.cmd.par_match_digits import par_match_digits
    from dectalk.cmd.par_match_sets_with_ranges import par_match_sets_with_ranges
    from dectalk.cmd.par_match_standard import par_match_standard

    rule_p = find_index
    op_byte = current_rule[find_index]
    char_type = op_byte & BIN_OPERATION_MASK

    if char_type == BIN_EXACT:
        rule_p += 1  # skip the single quote
        value = current_rule[rule_p] + ipos
        rule_p += 1
        if op_byte & BIN_CASE_INSEN:
            if par_lower[current_rule[rule_p]] != par_lower[input_array[ipos]]:
                return 0
            while ipos < value:
                if par_lower[current_rule[rule_p]] != par_lower[input_array[ipos]]:
                    return 0
                ipos += 1
                rule_p += 1
            return 1
        if current_rule[rule_p] != input_array[ipos]:
            return 0
        while ipos < value:
            if current_rule[rule_p] != input_array[ipos]:
                return 0
            ipos += 1
            rule_p += 1
        return 1

    if char_type <= BIN_DIGIT:
        new_ret = ReturnValue(rule=find_index, value=SUCCESS, input_pos=ipos)
        range_value = RangeValue()
        if op_byte & BIN_DIGIT_RANGE:
            char_length = par_match_digits(
                current_rule, input_array, match_array, new_ret, range_value, 0, 1
            )
        else:
            char_length = par_match_standard(
                current_rule, char_type, input_array, match_array, new_ret, 0, 1
            )
        if new_ret.value == SUCCESS and char_length > 0:
            return 1
        return 0

    if char_type == BIN_HEXADECIMAL:
        rule_p += 1
        return 1 if input_array[ipos] == current_rule[rule_p] else 0

    if char_type == BIN_RESTORE:
        rule_p += 1
        value = current_rule[rule_p]
        char_length = match_array.array_lengths[value]
        saved = match_array.array[value]
        # memcmp with length 0 always succeeds. The C source bails out
        # when the first byte of the saved array is NUL; we replicate
        # that even for length 0 so empty saves never look-ahead-match.
        if char_length == 0:
            return 0
        if (
            bytes(input_array[ipos : ipos + char_length]) == bytes(saved[:char_length])
            and saved[0] != 0
        ):
            return 1
        return 0

    if char_type == BIN_SETS:
        new_ret = ReturnValue(rule=find_index, value=SUCCESS, input_pos=ipos)
        range_value = RangeValue()
        char_length = par_match_sets_with_ranges(
            current_rule, input_array, match_array, new_ret, range_value, 0, 1
        )
        if new_ret.value == SUCCESS and char_length > 0:
            return 1
        return 0

    # BIN_DICTIONARY fall-through. par_look_ahead_dictionary is not
    # ported yet; the safe answer is "no match" so the engine keeps
    # advancing without faking a hit.
    return 0


__all__ = ["par_look_ahead"]
