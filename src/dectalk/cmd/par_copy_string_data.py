"""``par_copy_string_data`` byte/index bulk-copy from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 4466-4490.

Bulk copies ``num_chars`` bytes from the parser's input array to
its output array, plus the corresponding ``index_data_t`` entries
from the input-index list to the output-index list. Used by the
rule-engine replacement helpers (``par_replace_string`` /
``par_insert_string`` and variants).

The C source uses ``memcpy`` for the byte copy and
``par_copy_index_list`` for the parallel index copy; this Python
port uses slice assignment plus the already-ported
``par_copy_index_list``.
"""

from __future__ import annotations

from dectalk.cmd.par_index import par_copy_index_list
from dectalk.cmd.par_structs import IndexData, ReturnValue


def par_copy_string_data(
    input_array: bytearray,
    input_indexes: list[IndexData],
    output_array: bytearray,
    output_indexes: list[IndexData],
    num_chars: int,
    ret_value: ReturnValue,
) -> None:
    """Bulk-copy bytes + parallel index entries between parser buffers.

    Faithful translation of:

    .. code-block:: c

        void par_copy_string_data(unsigned char *input_array,
                                  pindex_data_t input_indexes,
                                  unsigned char *output_array,
                                  pindex_data_t output_indexes,
                                  int num_chars,
                                  preturn_value_t ret_value) {
            memcpy(&output_array[ret_value->output_pos + ret_value->output_offset],
                   &input_array[ret_value->input_pos + ret_value->input_offset],
                   num_chars);

            par_copy_index_list(output_indexes,
                                ret_value->output_pos + ret_value->output_offset,
                                input_indexes,
                                ret_value->input_pos + ret_value->input_offset,
                                num_chars);
        }

    Args:
        input_array: Source byte buffer.
        input_indexes: Source index list (parallel to ``input_array``).
        output_array: Destination byte buffer (mutated in place).
        output_indexes: Destination index list (mutated in place).
        num_chars: Number of bytes (and index entries) to copy.
        ret_value: Parser cursors driving the in/out offsets.
    """
    out_pos = ret_value.output_pos + ret_value.output_offset
    in_pos = ret_value.input_pos + ret_value.input_offset

    # Byte copy: equivalent to memcpy(&output_array[out_pos],
    # &input_array[in_pos], num_chars).
    output_array[out_pos : out_pos + num_chars] = input_array[in_pos : in_pos + num_chars]

    # Parallel index-data copy.
    par_copy_index_list(output_indexes, out_pos, input_indexes, in_pos, num_chars)


__all__ = ["par_copy_string_data"]
