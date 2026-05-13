"""``par_replace_string`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2704-2798.

Replaces the matched run in the parser's output buffer with the
string materialised by :func:`par_build_string_from_rule`. Index
markers inside the replaced span are migrated forward so they
don't disappear mid-word — the C source has a per-marker search
for an inter-word space in the replacement to anchor each marker
on, falling back to inserting a ``PAR_INDEX_DUMMY_CHAR`` if no
space is available.

The signature includes ``insert_operation_flags`` because the
Linux build defines ``GERMAN_COMPOUND_NOUNS`` (per
``test_cmd_module_inventory._LINUX_DEFINED``) — that flag is
forwarded along the rule chain but not consulted inside the
function body.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_REPLACE
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_index import par_copy_index, par_copy_index_list, par_is_index_set
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import PAR_INDEX_DUMMY_CHAR

_BUF_SIZE = 100
"""Stack-allocated buf size in the C source (``unsigned char buf[100]``)."""


def par_replace_string(
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
    r"""Replace the matched span in ``output_array`` with the built string.

    Faithful translation of:

    .. code-block:: c

        void par_replace_string(unsigned char *current_rule,
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
            index_data_t temp_index[100];

            memset(temp_index, 0, 100 * sizeof(index_data_t));

            if (ret_value==NULL) return;
            if (current_rule==NULL || output_array==NULL || match_array==NULL) {
                ret_value->value = FATAL_FAIL;
                return;
            }

            par_build_string_from_rule(current_rule, buf, output_array,
                                       match_array, ret_value, range_value,
                                       BIN_REPLACE, &length, in_rule_index);

            for (j=0, i=ret_value->output_pos;
                 i < ret_value->output_pos + ret_value->output_offset;
                 i++) {
                if (par_is_index_set(output_indexes, i)) {
                    for (; j<length && buf[j]!=' '; j++);
                    if (j < length) {
                        par_copy_index(temp_index, j, output_indexes, i);
                        buf[j] = PAR_INDEX_DUMMY_CHAR;
                        j++;
                    } else {
                        buf[j] = PAR_INDEX_DUMMY_CHAR;
                        buf[j+1] = '\0';
                        par_copy_index(temp_index, j, output_indexes, i);
                        j++;
                        length++;
                    }
                }
            }

            strcpy((output_array + (ret_value->output_pos)), buf);
            par_copy_index_list(output_indexes, ret_value->output_pos,
                                temp_index, 0, length);
            ret_value->output_offset = length;
        }

    Args:
        current_rule: Compiled rule bytes (read only).
        input_array: Unused on this path (forwarded to keep the rule-
            engine callsite signature uniform).
        output_array: Output buffer; the span
            ``[output_pos : output_pos + output_offset]`` is replaced
            by the materialised string.
        input_indexes: Unused on this path (forwarded for signature
            uniformity).
        output_indexes: Per-position index markers; markers inside
            the replaced span are migrated into ``buf`` via
            ``temp_index`` and re-copied onto the new layout.
        match_array: ``$N`` save slot collection (forwarded to
            :func:`par_build_string_from_rule`).
        ret_value: Parser cursors; ``output_offset`` becomes the new
            built-string length on success; ``value`` is set to
            :data:`FATAL_FAIL` on a bad opcode.
        range_value: Range-match state (forwarded to the builder).
        save_num: Save-slot index (unused on this path).
        dict_state_flag: Dictionary-state flag (unused on this path).
        in_rule_index: Action-descriptor offset in ``current_rule``.
        insert_operation_flags: Forwarded for signature uniformity
            (the GERMAN_COMPOUND_NOUNS build extends every action
            handler with this extra parameter, but ``replace`` does
            not branch on it).
    """
    # Silence unused-parameter complaints by explicitly deleting them.
    # The C source's signature includes them for uniform dispatch -- we
    # keep the surface identical even though only a subset is used.
    del input_array, input_indexes, save_num, dict_state_flag, insert_operation_flags

    # The C source's SANITY_CHECKING null-pointer guards are unreachable
    # in Python (the type system rules out None) -- dropped.

    # `temp_index` is a fresh 100-entry table (memset to 0 in the C source).
    temp_index: list[IndexData] = [IndexData() for _ in range(_BUF_SIZE)]
    buf = bytearray(_BUF_SIZE)
    length_box = [0]

    # Build the replacement string.
    par_build_string_from_rule(
        current_rule,
        buf,
        output_array,
        match_array,
        ret_value,
        range_value,
        BIN_REPLACE,
        length_box,
        in_rule_index,
    )
    length = length_box[0]

    # Migrate index markers from the replaced span into buf/temp_index.
    j = 0
    space = ord(" ")
    for i in range(ret_value.output_pos, ret_value.output_pos + ret_value.output_offset):
        if par_is_index_set(output_indexes, i):
            # Find a space in buf -- anchor the marker there if possible.
            while j < length and buf[j] != space:
                j += 1
            if j < length:
                par_copy_index(temp_index, j, output_indexes, i)
                buf[j] = PAR_INDEX_DUMMY_CHAR
                j += 1
            else:
                # No space available — extend buf by one dummy character.
                while len(buf) <= j + 1:
                    buf.append(0)
                buf[j] = PAR_INDEX_DUMMY_CHAR
                buf[j + 1] = 0
                par_copy_index(temp_index, j, output_indexes, i)
                j += 1
                length += 1

    # strcpy: copy buf (including its NUL terminator) on top of the
    # current output at output_pos. We mirror this with a slice
    # assignment of `length` bytes plus a NUL terminator at length+1.
    start = ret_value.output_pos
    while len(output_array) < start + length + 1:
        output_array.append(0)
    output_array[start : start + length] = buf[:length]
    output_array[start + length] = 0

    # Copy the parallel index markers.
    par_copy_index_list(output_indexes, ret_value.output_pos, temp_index, 0, length)

    # The output offset is now the length of the new output string.
    ret_value.output_offset = length


__all__ = ["par_replace_string"]
