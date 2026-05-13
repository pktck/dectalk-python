"""``par_copy_word_to_output`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 4626-4671.

Copies the next non-whitespace word from the input array to the
output array, propagating index markers and advancing both
``input_offset`` and ``output_offset`` on the way.

Returns ``-1`` on NUL terminator, ``0`` otherwise — matching the
C source's end-of-input sentinel.
"""

from __future__ import annotations

from dectalk.cmd.par_index import par_copy_index
from dectalk.cmd.par_structs import IndexData, ReturnValue
from dectalk.cmd.parser_tables import TYPE_white, parser_char_types


def par_copy_word_to_output(
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    ret_value: ReturnValue,
) -> int:
    r"""Copy non-whitespace bytes from input to output until a delimiter.

    Faithful translation of:

    .. code-block:: c

        int par_copy_word_to_output(unsigned char *input_array,
                                    unsigned char *output_array,
                                    pindex_data_t input_indexes,
                                    pindex_data_t output_indexes,
                                    preturn_value_t ret_value) {
            ipos = ret_value->input_pos + ret_value->input_offset;
            opos = ret_value->output_pos + ret_value->output_offset;
            i = 0;
            while ((parser_char_types[input_array[ipos+i]] & TYPE_white) == 0
                   && input_array[ipos+i] != '\0') {
                output_array[opos+i] = input_array[ipos+i];
                par_copy_index(output_indexes, opos+i, input_indexes, ipos+i);
                i++;
            }
            ret_value->input_offset += i;
            ret_value->output_offset += i;
            if (input_array[ipos+i] == '\0') return -1;
            return 0;
        }

    Args:
        input_array: Source bytes.
        output_array: Bytearray to write copied chars + markers into.
        input_indexes: Per-position index markers on the input.
        output_indexes: Per-position index markers on the output.
        ret_value: Position tracker; mutated in place.

    Returns:
        ``-1`` if the scan terminated at a NUL byte;
        ``0`` if it stopped at a whitespace delimiter.
    """
    ipos = ret_value.input_pos + ret_value.input_offset
    opos = ret_value.output_pos + ret_value.output_offset
    i = 0
    while ipos + i < len(input_array):
        byte = input_array[ipos + i]
        if byte == 0:
            break
        if (parser_char_types[byte] & TYPE_white) != 0:
            break
        # Grow output buffer if needed.
        while len(output_array) <= opos + i:
            output_array.append(0)
        output_array[opos + i] = byte
        par_copy_index(output_indexes, opos + i, input_indexes, ipos + i)
        i += 1

    ret_value.input_offset += i
    ret_value.output_offset += i

    if ipos + i >= len(input_array) or input_array[ipos + i] == 0:
        return -1
    return 0


__all__ = ["par_copy_word_to_output"]
