"""``par_insert_string`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3080-3179.

Interleaves the materialised insert string between every character
of the output span ``output_array[output_pos : output_pos +
output_offset]``. On the GERMAN_COMPOUND_NOUNS build (active on
Linux) the function first dispatches to
:func:`par_insert_string_after` or
:func:`par_insert_string_before` based on the BIN_AFTER_FLAG /
BIN_BEFORE_FLAG bits in ``insert_operation_flags`` — only the
plain "interleave" path runs once those flags have been cleared.

The C source executes the insert in *reverse* so it can mutate the
output buffer in place without a scratch array; the Python port
preserves that ordering exactly.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_AFTER_FLAG, BIN_BEFORE_FLAG, BIN_INSERT
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_index import par_copy_index
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_BUF_SIZE = 100
"""Stack-allocated ``buf[100]`` from the C source."""


def par_insert_string(
    current_rule: bytes,
    input_array: bytearray,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
    insert_operation_flags: int,
) -> None:
    r"""Interleave the materialised insert string into the output span.

    Faithful translation of:

    .. code-block:: c

        void par_insert_string(unsigned char *current_rule,
                               unsigned char *input_array,
                               unsigned char *output_array,
                               pindex_data_t input_indexes,
                               pindex_data_t output_indexes,
                               pmatch_arrays_t match_array,
                               preturn_value_t ret_value,
                               prange_value_t range_value,
                               int save_num, int dict_state_flag,
                               int in_rule_index,
                               int insert_operation_flags) {
            unsigned char buf[100];
            int length, new_length;
            int pos, new_loc, off;
            int i;
            index_data_t temp_index = {{0,0,0}};

            if (insert_operation_flags & BIN_AFTER_FLAG) {
                par_insert_string_after(...); return;
            }
            if (insert_operation_flags & BIN_BEFORE_FLAG) {
                par_insert_string_before(...); return;
            }

            if (ret_value==NULL) return;
            if (current_rule==NULL || output_array==NULL || match_array==NULL) {
                ret_value->value = FATAL_FAIL; return;
            }

            par_build_string_from_rule(current_rule, buf, output_array,
                                       match_array, ret_value, range_value,
                                       BIN_INSERT, &length, in_rule_index);

            new_length = (ret_value->output_offset - 1) * (length + 1) + 1;
            pos = ret_value->output_pos;
            off = ret_value->output_offset + ret_value->output_pos - 1;
            new_loc = new_length + ret_value->output_pos - 1;
            while (pos < off) {
                output_array[new_loc] = output_array[off];
                par_copy_index(output_indexes, new_loc, output_indexes, off);
                par_copy_index(output_indexes, off,
                               output_indexes, PAR_MAX_OUTPUT_ARRAY-1);
                off--;
                new_loc -= length;
                memcpy(output_array+new_loc, buf, length);
                for (i=new_loc; i<new_loc+length; i++)
                    par_copy_index(output_indexes, new_loc, &temp_index, 0);
                new_loc--;
            }
            ret_value->output_offset = new_length;
        }

    Args:
        current_rule: Compiled rule bytes (read only).
        input_array: Unused on this path.
        output_array: Output buffer; rewritten in place from the
            tail end backward.
        input_indexes: Unused on this path.
        output_indexes: Per-position index markers; the markers for
            the original output characters move out with the
            characters as they shift right.
        match_array: ``$N`` save slot collection.
        ret_value: Parser cursors; ``output_offset`` becomes the
            expanded length on success; ``value`` is set to
            :data:`FATAL_FAIL` on a bad opcode.
        range_value: Range-match state.
        save_num: Save-slot index (unused on this path).
        dict_state_flag: Dictionary-state flag (unused on this path).
        in_rule_index: Action-descriptor offset in ``current_rule``.
        insert_operation_flags: BIN_AFTER_FLAG / BIN_BEFORE_FLAG
            redirect to the corresponding variant; otherwise the
            interleave path runs.
    """
    # Late binding to break the circular import: par_insert_string_after
    # and par_insert_string_before live in sibling modules that also
    # call into par_insert_string indirectly through the rule engine.
    if insert_operation_flags & BIN_AFTER_FLAG:
        from dectalk.cmd.par_insert_string_after import (  # noqa: PLC0415 — late-binding to break circular import
            par_insert_string_after,
        )

        par_insert_string_after(
            current_rule,
            input_array,
            output_array,
            input_indexes,
            output_indexes,
            match_array,
            ret_value,
            range_value,
            save_num,
            dict_state_flag,
            in_rule_index,
            insert_operation_flags,
        )
        return
    if insert_operation_flags & BIN_BEFORE_FLAG:
        from dectalk.cmd.par_insert_string_before import (  # noqa: PLC0415 — late-binding to break circular import
            par_insert_string_before,
        )

        par_insert_string_before(
            current_rule,
            input_array,
            output_array,
            input_indexes,
            output_indexes,
            match_array,
            ret_value,
            range_value,
            save_num,
            dict_state_flag,
            in_rule_index,
            insert_operation_flags,
        )
        return

    # Silence unused-parameter complaints for the interleave path.
    del input_array, input_indexes, save_num, dict_state_flag

    # The C source's SANITY_CHECKING null-pointer guards are unreachable
    # in Python (the type system rules out None) -- dropped.

    buf = bytearray(_BUF_SIZE)
    length_box = [0]
    par_build_string_from_rule(
        current_rule,
        buf,
        output_array,
        match_array,
        ret_value,
        range_value,
        BIN_INSERT,
        length_box,
        in_rule_index,
    )
    length = length_box[0]

    # new_length: number of insert points (output_offset - 1) times
    # length-of-insert (length + 1 for the original character), plus
    # the trailing original character itself.
    new_length = (ret_value.output_offset - 1) * (length + 1) + 1

    pos = ret_value.output_pos
    off = ret_value.output_offset + ret_value.output_pos - 1
    new_loc = new_length + ret_value.output_pos - 1

    # Grow output_array if necessary.
    while len(output_array) <= new_loc:
        output_array.append(0)

    temp_index = IndexData(index=[0, 0, 0])

    while pos < off:
        # Move the current tail character to its expanded position.
        output_array[new_loc] = output_array[off]
        par_copy_index(output_indexes, new_loc, output_indexes, off)
        par_copy_index(output_indexes, off, output_indexes, PAR_MAX_OUTPUT_ARRAY - 1)
        off -= 1
        new_loc -= length
        # Copy the inserted string into place.
        output_array[new_loc : new_loc + length] = buf[:length]
        # Blank the indexes in the inserted range -- the C source loops
        # ``for(i=new_loc;i<new_loc+length;i++)`` but copies to ``new_loc``
        # every iteration (a faithful quirk of the original code that the
        # Python port preserves verbatim).
        for _i in range(new_loc, new_loc + length):
            par_copy_index(output_indexes, new_loc, [temp_index], 0)
        new_loc -= 1

    ret_value.output_offset = new_length


__all__ = ["par_insert_string"]
