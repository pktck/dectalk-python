"""``par_save_string`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 2572-2622.

Copies the current output span into ``match_array.array[num]`` so a
later ``$num`` reference in the rule can substitute the saved
chunk. The C source guards against running off the per-array
buffer (``PAR_MAX_MATCH_ARRAY = 30``) and skips the save entirely
when ``optional == -1`` (optional-failure recovery mode).
"""

from __future__ import annotations

from dectalk.cmd.par_structs import PAR_MAX_ARRAYS, PAR_MAX_MATCH_ARRAY, MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL


def par_save_string(
    output_array: bytes,
    num: int,
    match_array: MatchArrays,
    ret_value: ReturnValue,
) -> None:
    r"""Save the output span into ``match_array.array[num]``.

    Faithful translation of:

    .. code-block:: c

        void par_save_string(unsigned char *output_array, int num,
                             pmatch_arrays_t match_array,
                             preturn_value_t ret_value) {
            if (num < 0 || num > PAR_MAX_ARRAYS) {
                printf("$%d is out of range\n", num);
                ret_value->value = FATAL_FAIL;
                return;
            }
            if (ret_value->optional != -1) {
                if (ret_value->output_offset >= PAR_MAX_MATCH_ARRAY) {
                    ret_value->value = FAIL;
                    return;
                }
                memcpy(match_array->array[num],
                       output_array + ret_value->output_pos,
                       ret_value->output_offset);
                match_array->array[num][ret_value->output_offset] = '\0';
            }
        }

    Args:
        output_array: Source buffer; the span
            ``[output_pos : output_pos + output_offset]`` is saved.
        num: Slot index (0..PAR_MAX_ARRAYS).
        match_array: Destination match-array struct (mutated).
        ret_value: Position tracker; ``value`` is set to
            :data:`FATAL_FAIL` for out-of-range ``num`` or
            :data:`FAIL` if the span is too long.
    """
    if num < 0 or num > PAR_MAX_ARRAYS:
        ret_value.value = FATAL_FAIL
        return

    if ret_value.optional == -1:
        return

    if ret_value.output_offset >= PAR_MAX_MATCH_ARRAY:
        ret_value.value = FAIL
        return

    # Copy the span and NUL-terminate.
    dest = match_array.array[num]
    # Zero the destination buffer first (memcpy doesn't, but match_arrays
    # are initialised to zeros so the trailing bytes stay 0).
    for i in range(len(dest)):
        dest[i] = 0
    start = ret_value.output_pos
    span = output_array[start : start + ret_value.output_offset]
    for i, byte in enumerate(span):
        dest[i] = byte
    # The C source writes a NUL after the span; we already zeroed the
    # buffer, so this is implicit.


__all__ = ["par_save_string"]
