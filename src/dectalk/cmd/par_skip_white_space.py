"""``par_skip_white_space`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 5349-5412.

Walks the input array starting from
``ret_value.input_pos + ret_value.input_offset``, copying whitespace
bytes (per the ``parser_char_types[c] & TYPE_white`` test) into the
output array and advancing both ``input_offset`` and
``output_offset`` on the way.

Special index-marker handling: indices on whitespace bytes are
carried over to the output positions; otherwise only the first
matched whitespace byte is copied (the C source's terse logic keeps
the leading whitespace and drops the run).

Returns ``-1`` when the scan hits a NUL terminator, ``0`` otherwise.
"""

from __future__ import annotations

from dectalk.cmd.par_index import par_copy_index, par_is_index_set
from dectalk.cmd.par_structs import IndexData, ReturnValue
from dectalk.cmd.parser_tables import TYPE_white, parser_char_types


def par_skip_white_space(
    input_array: bytes,
    input_indexes: list[IndexData],
    output_array: bytearray,
    output_indexes: list[IndexData],
    ret_value: ReturnValue,
) -> int:
    r"""Skip / copy whitespace bytes at the current input position.

    Faithful translation of:

    .. code-block:: c

        int par_skip_white_space(unsigned char *input_array,
                                 pindex_data_t input_indexes,
                                 unsigned char *output_array,
                                 pindex_data_t output_indexes,
                                 preturn_value_t ret_value) {
            if (ret_value == NULL || input_array == NULL ||
                output_array == NULL) return 0;
            ipos = ret_value->input_pos + ret_value->input_offset;
            opos = ret_value->output_pos + ret_value->output_offset;
            i = 0; j = 0;
            while ((parser_char_types[input_array[ipos + i]] & TYPE_white) != 0
                   && input_array[ipos + i] != '\\0') {
                if (i == 0 || par_is_index_set(input_indexes, ipos + i)) {
                    output_array[opos + j] = input_array[ipos + i];
                    if (par_is_index_set(input_indexes, ipos + i)) {
                        par_copy_index(output_indexes, opos + j,
                                       input_indexes, ipos + i);
                        j++;
                    } else { j++; }
                }
                i++;
            }
            ret_value->input_offset += i;
            if (i > 0) ret_value->output_offset += j;
            if (input_array[ipos + i] == '\\0') return -1;
            return 0;
        }

    Args:
        input_array: Source bytes.
        input_indexes: Per-position index markers on the input.
        output_array: Bytearray to write whitespace + markers into.
        output_indexes: Per-position index markers on the output.
        ret_value: Position tracker; mutated in place.

    Returns:
        ``-1`` if the scan terminated at a NUL byte; ``0`` otherwise.
        Returns ``0`` immediately on a NULL-array guard mismatch
        (the C source's defensive fail path).
    """
    ipos = ret_value.input_pos + ret_value.input_offset
    opos = ret_value.output_pos + ret_value.output_offset
    i = 0
    j = 0
    while ipos + i < len(input_array):
        byte = input_array[ipos + i]
        if byte == 0:
            break
        if (parser_char_types[byte] & TYPE_white) == 0:
            break
        if i == 0 or par_is_index_set(input_indexes, ipos + i):
            # Grow output as needed.
            while len(output_array) <= opos + j:
                output_array.append(0)
            output_array[opos + j] = byte
            if par_is_index_set(input_indexes, ipos + i):
                par_copy_index(output_indexes, opos + j, input_indexes, ipos + i)
            j += 1
        i += 1

    ret_value.input_offset += i
    if i > 0:
        ret_value.output_offset += j

    if ipos + i >= len(input_array) or input_array[ipos + i] == 0:
        return -1
    return 0


__all__ = ["par_skip_white_space"]
