"""``par_insert_string_before`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3296-3361.

Inserts the materialised string in front of the matched span
(``output_pos``). The current contents of the matched span are
shifted right by ``length`` bytes (in reverse to avoid clobbering),
their index markers travel with them, and the new string is
written into the freed prefix. The index markers for the inserted
range are zeroed out (the C source copies from
``PAR_MAX_OUTPUT_ARRAY - 1`` -- a permanently-empty slot at the
tail of the index buffer).

On the GERMAN_COMPOUND_NOUNS build (active on Linux) the call into
:func:`par_build_string_from_rule` uses the combined opcode
``BIN_INSERT | BIN_BEFORE_FLAG`` so the builder's conditional-
replace path treats the operation as a BIN_INSERT variant whose
anchor is the *first* character of the matched range.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_BEFORE_FLAG, BIN_INSERT
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_index import par_copy_index
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_BUF_SIZE = 100
"""Stack-allocated ``buf[100]`` from the C source."""


def par_insert_string_before(
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
    r"""Insert the materialised string before the matched span.

    Faithful translation of:

    .. code-block:: c

        void par_insert_string_before(unsigned char *current_rule,
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
            int i, j;
            unsigned char buf[100];

            if (ret_value==NULL) return;
            if (current_rule==NULL || output_array==NULL || match_array==NULL) {
                ret_value->value = FATAL_FAIL; return;
            }

            par_build_string_from_rule(current_rule, buf, output_array,
                                       match_array, ret_value, range_value,
                                       BIN_INSERT | BIN_BEFORE_FLAG,
                                       &length, in_rule_index);

            j = ret_value->output_pos + ret_value->output_offset;
            for (i = j-1; i >= ret_value->output_pos; i--) {
                output_array[i+length] = output_array[i];
                par_copy_index(output_indexes, i+length, output_indexes, i);
            }
            memcpy((output_array + (ret_value->output_pos)), buf, length);
            for (i=0; i<length; i++) {
                par_copy_index(output_indexes, ret_value->output_pos+i,
                               output_indexes, PAR_MAX_OUTPUT_ARRAY-1);
            }
            ret_value->output_offset += length;
        }

    Args:
        current_rule: Compiled rule bytes (read only).
        input_array: Unused on this path.
        output_array: Output buffer; the matched span shifts right
            by ``length`` and the materialised string slots into the
            now-freed prefix.
        input_indexes: Unused on this path.
        output_indexes: Per-position index markers; markers for the
            matched span travel with the bytes, and markers for the
            inserted range are cleared.
        match_array: ``$N`` save slot collection.
        ret_value: Parser cursors; ``output_offset`` grows by
            ``length`` on success; ``value`` is set to
            :data:`FATAL_FAIL` on a bad opcode.
        range_value: Range-match state.
        save_num: Save-slot index (unused on this path).
        dict_state_flag: Dictionary-state flag (unused on this path).
        in_rule_index: Action-descriptor offset in ``current_rule``.
        insert_operation_flags: Forwarded; not directly consulted
            here (only as part of the build-state ``BIN_INSERT |
            BIN_BEFORE_FLAG`` passed to
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
        BIN_INSERT | BIN_BEFORE_FLAG,
        length_box,
        in_rule_index,
    )
    length = length_box[0]

    # Move the current span `length` bytes to the right (iterate in
    # reverse so the copy doesn't clobber unread positions).
    j = ret_value.output_pos + ret_value.output_offset
    # Grow output_array if necessary.
    while len(output_array) < j + length + 1:
        output_array.append(0)
    for i in range(j - 1, ret_value.output_pos - 1, -1):
        output_array[i + length] = output_array[i]
        par_copy_index(output_indexes, i + length, output_indexes, i)

    # Drop the new string into the freed prefix.
    output_array[ret_value.output_pos : ret_value.output_pos + length] = buf[:length]
    # Clear the index markers in the inserted range by copying from the
    # permanently-empty slot at PAR_MAX_OUTPUT_ARRAY - 1.
    for i in range(length):
        par_copy_index(
            output_indexes,
            ret_value.output_pos + i,
            output_indexes,
            PAR_MAX_OUTPUT_ARRAY - 1,
        )

    ret_value.output_offset += length


__all__ = ["par_insert_string_before"]
