"""``par_initialize_arrays`` and ``par_initialize_variables`` from par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 641-684.

Two small zeroing helpers the rule engine calls at startup:

- :func:`par_initialize_arrays` zeros each of the
  ``PAR_MAX_ARRAYS`` match-array buffers used by ``$N`` shuffle
  rules.
- :func:`par_initialize_variables` zeros the input/output/
  dict-hit arrays before a fresh parser run.
"""

from __future__ import annotations

from dectalk.cmd.par_limits import PAR_MAX_INPUT_ARRAY, PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import PAR_MAX_ARRAYS, PAR_MAX_MATCH_ARRAY, MatchArrays


def par_initialize_arrays(match_arrays: MatchArrays) -> None:
    """Zero every match-array buffer.

    Faithful translation of:

    .. code-block:: c

        void par_initialize_arrays(pmatch_arrays_t match_arrays) {
            for (i = 0; i < PAR_MAX_ARRAYS; i++)
                memset(match_arrays->array[i], 0, PAR_MAX_MATCH_ARRAY);
        }

    Args:
        match_arrays: Match-array struct to zero in place.
    """
    for i in range(PAR_MAX_ARRAYS):
        arr = match_arrays.array[i]
        for j in range(min(len(arr), PAR_MAX_MATCH_ARRAY)):
            arr[j] = 0


def par_initialize_variables(
    input_array: bytearray,
    output_array: bytearray,
    dict_hit_array: bytearray,
) -> None:
    """Zero the input / output / dict-hit arrays.

    Faithful translation of:

    .. code-block:: c

        void par_initialize_variables(unsigned char *input_array,
                                      unsigned char *output_array,
                                      unsigned char *dict_hit_array) {
            memset(input_array, 0, PAR_MAX_INPUT_ARRAY);
            memset(output_array, 0, PAR_MAX_OUTPUT_ARRAY);
            memset(dict_hit_array, 0, PAR_MAX_INPUT_ARRAY);
        }

    Args:
        input_array: Mutable input buffer.
        output_array: Mutable output buffer.
        dict_hit_array: Mutable dictionary-hit buffer.
    """
    for i in range(min(len(input_array), PAR_MAX_INPUT_ARRAY)):
        input_array[i] = 0
    for i in range(min(len(output_array), PAR_MAX_OUTPUT_ARRAY)):
        output_array[i] = 0
    for i in range(min(len(dict_hit_array), PAR_MAX_INPUT_ARRAY)):
        dict_hit_array[i] = 0


__all__ = ["par_initialize_arrays", "par_initialize_variables"]
