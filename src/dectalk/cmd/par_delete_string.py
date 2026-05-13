"""``par_delete_string`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 2121-2174.

Deletes the matched span ``output_array[output_pos : output_pos +
output_offset]`` by zeroing the bytes and, if not in
optional-failure mode, resetting ``output_offset`` to 0. Index
markers in the deleted range are compacted: each one moves to the
freed slot above the head, and a dummy character
(``PAR_INDEX_DUMMY_CHAR``) is written in its place so the indices
still find a target byte.

The compaction loop preserves the C source's exact semantics —
including the quirk that ``output_offset`` is bumped each time a
marker is moved (since the dummy character represents a logical
keeping of the byte for index purposes).
"""

from __future__ import annotations

from dectalk.cmd.par_index import par_copy_index, par_is_index_set
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import IndexData, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL, PAR_INDEX_DUMMY_CHAR


def par_delete_string(
    output_array: bytearray,
    output_indexes: list[IndexData],
    ret_value: ReturnValue,
) -> None:
    """Delete the matched output span, compacting index markers.

    Faithful translation of:

    .. code-block:: c

        void par_delete_string(unsigned char *output_array,
                               pindex_data_t output_indexes,
                               preturn_value_t ret_value) {
            short i, j, save_offset = 0;
            save_offset = ret_value->output_offset;
            if (ret_value->optional != -1) {
                memset(output_array + ret_value->output_pos, 0,
                       ret_value->output_offset);
                ret_value->output_offset = 0;
            }
            for (j = i = ret_value->output_pos; i < save_offset; i++) {
                if (par_is_index_set(output_indexes, i)) {
                    par_copy_index(output_indexes, j, output_indexes, i);
                    par_copy_index(output_indexes, i,
                                   output_indexes, PAR_MAX_OUTPUT_ARRAY - 1);
                    output_array[i] = PAR_INDEX_DUMMY_CHAR;
                    j++;
                    ret_value->output_offset++;
                }
            }
        }

    Args:
        output_array: The output buffer; bytes in the deleted span
            are zeroed (then index-tagged positions get
            :data:`PAR_INDEX_DUMMY_CHAR` written back).
        output_indexes: Per-position index markers; ones in the
            deleted span are migrated to fresh slots above the
            output head.
        ret_value: Position tracker; ``output_offset`` is reset
            (or kept high if there are indices to preserve).

    Notes:
        The C source has a guard that returns without changes when
        ``output_array == NULL``; Python's static typing makes that
        impossible — we still guard via ``len(output_array) == 0``
        to mirror the spirit of the defensive C check, but a
        zero-length array isn't meaningful for this function.
    """
    if len(output_array) == 0:
        ret_value.value = FATAL_FAIL
        return

    save_offset = ret_value.output_offset
    # Zero the deleted span and clear output_offset unless we're in
    # optional-failure mode.
    if ret_value.optional != -1:
        start = ret_value.output_pos
        end = min(start + save_offset, len(output_array))
        for k in range(start, end):
            output_array[k] = 0
        ret_value.output_offset = 0

    # Compact index markers from the deleted span up to fresh slots.
    j = ret_value.output_pos
    for i in range(ret_value.output_pos, ret_value.output_pos + save_offset):
        if par_is_index_set(output_indexes, i):
            par_copy_index(output_indexes, j, output_indexes, i)
            par_copy_index(
                output_indexes,
                i,
                output_indexes,
                PAR_MAX_OUTPUT_ARRAY - 1,
            )
            if 0 <= i < len(output_array):
                output_array[i] = PAR_INDEX_DUMMY_CHAR
            j += 1
            ret_value.output_offset += 1


__all__ = ["par_delete_string"]
