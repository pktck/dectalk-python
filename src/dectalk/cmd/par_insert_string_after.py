"""``par_insert_string_after`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3209-3264.

Appends the materialised insert string to the output buffer right
after the matched span (``output_pos + output_offset``). The
GERMAN_COMPOUND_NOUNS build (active on Linux) calls
:func:`par_build_string_from_rule` with the combined opcode
``BIN_INSERT | BIN_AFTER_FLAG`` so the builder's conditional-replace
path treats the operation as a BIN_INSERT variant whose anchor is
the *last* character of the matched range.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_AFTER_FLAG, BIN_INSERT
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_BUF_SIZE = 100
"""Stack-allocated ``buf[100]`` from the C source."""


def par_insert_string_after(
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
    r"""Append the materialised insert string after the matched span.

    Faithful translation of:

    .. code-block:: c

        void par_insert_string_after(unsigned char *current_rule,
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
            int length;
            unsigned char buf[100];

            if (ret_value==NULL) return;
            if (current_rule==NULL || output_array==NULL || match_array==NULL) {
                ret_value->value = FATAL_FAIL; return;
            }

            par_build_string_from_rule(current_rule, buf, output_array,
                                       match_array, ret_value, range_value,
                                       BIN_INSERT | BIN_AFTER_FLAG,
                                       &length, in_rule_index);

            strcpy((output_array + (ret_value->output_pos
                                    + ret_value->output_offset)), buf);
            memcpy((output_array + (ret_value->output_pos
                                    + ret_value->output_offset)), buf, length);
            ret_value->output_offset += length;
        }

    Args:
        current_rule: Compiled rule bytes (read only).
        input_array: Unused on this path.
        output_array: Output buffer; the materialised insert string
            is appended directly after the matched span.
        input_indexes: Unused on this path.
        output_indexes: Per-position index markers; the C source
            comments note ``the indexes will have been copied by
            copy_string_data`` -- no additional index work here.
        match_array: ``$N`` save slot collection.
        ret_value: Parser cursors; ``output_offset`` grows by
            ``length`` on success; ``value`` is set to
            :data:`FATAL_FAIL` on a bad opcode.
        range_value: Range-match state.
        save_num: Save-slot index (unused on this path).
        dict_state_flag: Dictionary-state flag (unused on this path).
        in_rule_index: Action-descriptor offset in ``current_rule``.
        insert_operation_flags: Forwarded; not directly consulted
            in the function body (only as part of the build-state
            ``BIN_INSERT | BIN_AFTER_FLAG`` constant passed to
            :func:`par_build_string_from_rule`).
    """
    # Silence unused-parameter complaints.
    del input_array, input_indexes, save_num, dict_state_flag, insert_operation_flags

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
        BIN_INSERT | BIN_AFTER_FLAG,
        length_box,
        in_rule_index,
    )
    length = length_box[0]

    # The C source does:
    #   strcpy(output_array + (output_pos + output_offset), buf);
    #   memcpy(output_array + (output_pos + output_offset), buf, length);
    # The strcpy writes the NUL-terminated buf; the memcpy then re-copies
    # exactly `length` bytes (which is redundant after strcpy, but
    # mirrors the original code faithfully). We emit the bytes plus the
    # NUL terminator for parity.
    dest = ret_value.output_pos + ret_value.output_offset
    while len(output_array) < dest + length + 1:
        output_array.append(0)
    output_array[dest : dest + length] = buf[:length]
    # NUL terminator as strcpy would write.
    output_array[dest + length] = 0

    # Grow output_offset by the inserted length.
    ret_value.output_offset += length


__all__ = ["par_insert_string_after"]
