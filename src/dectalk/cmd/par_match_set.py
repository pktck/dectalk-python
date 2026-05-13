"""``par_match_set`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 5991-6137.

Walks one ``[...] {sect-1, sect-2, ...}`` rule section at a time
calling :func:`par_match_string` for each character-class in the
section. The section table is laid out as:

* ``current_rule[rule_p]`` — section count.
* ``current_rule[rule_p + 1 .. rule_p + count]`` — end-offsets, one
  per section. Each end-offset points just past the section's last
  byte; the section starts at ``sect_p`` for section 0 and at the
  prior section's end-offset for sections ``1..count-1``.

The function returns the byte length of the first section that
matches, ``-1`` when the end of the input is reached, ``-2`` when a
zero-length section succeeded, and ``0`` on a hard failure (with
``ret_value->value`` set to FAIL / FATAL_FAIL).

``range_value->range_set`` is mutated to track which section matched
so the surrounding ``par_match_sets_with_ranges`` can emit a
multi-section ``<#>`` range record.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_OPERATION_MASK
from dectalk.cmd.par_copy_return_value import par_copy_return_value
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL, SUCCESS


def par_match_set(
    current_rule: bytes,
    input_array: bytes,
    rule_p: int,
    sect_p: int,
    ipos: int,
    match_array: MatchArrays,
    range_value: RangeValue,
    ret_value: ReturnValue,
    lookahead: int,
) -> int:
    r"""Match one ``{sect-1, sect-2, ...}`` set against ``input_array``.

    Faithful translation of:

    .. code-block:: c

        int par_match_set(unsigned char *current_rule,
                          unsigned char *input_array,
                          int rule_p, int sect_p, int ipos,
                          pmatch_arrays_t match_array,
                          prange_value_t range_value,
                          preturn_value_t ret_value, int lookahead)
        {
            return_value_t new_ret = {0}, save_ret = {0};
            int length=0, a_success=FAIL, this_success=0;
            int num_chars_matched=0, num_match=0, new_char_type;
            int num_sections, end_of_all_sections;

            new_ret.rule=sect_p;
            new_ret.input_pos=ipos;
            new_ret.optional=ret_value->optional;
            new_ret.value=SUCCESS;
            par_copy_return_value(&save_ret,&new_ret);

            num_sections        = current_rule[rule_p];
            end_of_all_sections = current_rule[rule_p+num_sections];

            while ((new_ret.rule<=end_of_all_sections) && (a_success==FAIL)) {
                this_success=SUCCESS;
                length=0;
                rule_p++;                       /* go to the next section */
                while ((new_ret.rule<=current_rule[rule_p]) && (a_success==FAIL)) {
                    if ((new_char_type = current_rule[new_ret.rule] & BIN_OPERATION_MASK)) {
                        num_chars_matched = par_match_string(current_rule,new_char_type,
                                                input_array,match_array,&new_ret,
                                                range_value,0,0);
                        length += num_chars_matched;
                        new_ret.input_pos += num_chars_matched;
                        if (num_chars_matched == -1) return -1;
                    } else {
                        ret_value->value = FATAL_FAIL;
                        return 0;
                    }
                    if (new_ret.value == FAIL) {
                        this_success = FAIL;
                        new_ret.rule = current_rule[rule_p]+1;
                    }
                }
                if (this_success == SUCCESS) {
                    a_success = SUCCESS;
                    if (range_value->range_set == 0) {
                        range_value->range_set = 2;
                        range_value->start = num_match;
                    } else {
                        range_value->range_set = -1;
                    }
                } else {
                    if (num_match != num_sections) {
                        par_copy_return_value(&new_ret,&save_ret);
                        num_match++;
                        new_ret.rule = current_rule[rule_p]+1;
                    }
                }
            }
            if (a_success == FAIL)  ret_value->value = FAIL;
            return length;
        }

    Args:
        current_rule: Compiled rule bytes.
        input_array: Input text bytes.
        rule_p: Index of the section-count byte (also the running
            "current section boundary" cursor).
        sect_p: Index of the first section's body.
        ipos: Current position in ``input_array``.
        match_array: Saved-string buffers (passed through to the
            recursive ``par_match_string`` calls).
        range_value: Range tracker; ``range_set`` and ``start`` are
            mutated to record which section matched.
        ret_value: Caller's recursion state; ``value`` is set to
            FAIL / FATAL_FAIL on failure paths.
        lookahead: Passed only so debug prints can decide whether to
            dump; not used to gate behaviour beyond that.

    Returns:
        Length matched (``>=0``), ``-1`` at end-of-input, or ``0`` on
        failure with ``ret_value.value`` updated.
    """
    # Late-bind the cross-recursive caller (par_match_string is the
    # entry point for *all* matchers including this one).
    from dectalk.cmd.par_match_string import par_match_string  # noqa: PLC0415

    _ = lookahead  # only used for diagnostic prints in the C source.

    new_ret = ReturnValue(
        rule=sect_p,
        input_pos=ipos,
        optional=ret_value.optional,
        value=SUCCESS,
    )
    save_ret = ReturnValue()
    par_copy_return_value(save_ret, new_ret)

    length = 0
    a_success = FAIL
    num_match = 0

    num_sections = current_rule[rule_p]
    end_of_all_sections = current_rule[rule_p + num_sections]

    while new_ret.rule <= end_of_all_sections and a_success == FAIL:
        this_success = SUCCESS
        length = 0
        rule_p += 1  # go to the next section's end-offset

        while new_ret.rule <= current_rule[rule_p] and a_success == FAIL:
            new_char_type = current_rule[new_ret.rule] & BIN_OPERATION_MASK
            if new_char_type:
                num_chars_matched = par_match_string(
                    current_rule,
                    new_char_type,
                    input_array,
                    match_array,
                    new_ret,
                    range_value,
                    0,
                    0,
                )
                length += num_chars_matched
                new_ret.input_pos += num_chars_matched
                if num_chars_matched == -1:
                    return -1
            else:
                ret_value.value = FATAL_FAIL
                return 0

            if new_ret.value == FAIL:
                this_success = FAIL
                new_ret.rule = current_rule[rule_p] + 1

        if this_success == SUCCESS:
            a_success = SUCCESS
            if range_value.range_set == 0:
                range_value.range_set = 2
                range_value.start = num_match
            else:
                range_value.range_set = -1
        elif num_match != num_sections:
            par_copy_return_value(new_ret, save_ret)
            num_match += 1
            new_ret.rule = current_rule[rule_p] + 1

    if a_success == FAIL:
        ret_value.value = FAIL

    return length


__all__ = ["par_match_set"]
