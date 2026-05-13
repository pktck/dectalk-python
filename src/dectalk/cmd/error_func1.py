"""``ERROR_func1`` diagnostic helper from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 609-629.

A fallback entry in the ``perform_action_funcs[]`` rule-action
dispatch table that fires when the compiled rule references an
opcode whose slot points at this placeholder. The C source writes
the literal debug marker ``"I am a pud-fart. "`` (17 bytes) into
the output array at ``ret_value->output_pos`` and sets
``ret_value->output_offset`` to its length.

The Python port mirrors this byte-for-byte so the diagnostic
remains visible if the rule engine ever lands on the slot. The
C-style name ``ERROR_func1`` is re-exported alongside the
PEP8-friendly :func:`error_func1` to keep call-site parity with
the dispatch-table generator and the cmd-module inventory test.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

# The literal marker the C source writes. ``strcpy`` writes 17
# visible bytes plus an implicit trailing NUL; ``strlen`` therefore
# returns 17.
_PUD_FART_MARKER: bytes = b"I am a pud-fart. "


def error_func1(
    current_rule: bytes,
    input_array: bytes,
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
    r"""Write the ``"I am a pud-fart. "`` debug marker into the output.

    Faithful translation of:

    .. code-block:: c

        void ERROR_func1(unsigned char *current_rule,
                         unsigned char *input_array,
                         unsigned char *output_array,
                         pindex_data_t input_indexes,
                         pindex_data_t output_indexes,
                         pmatch_arrays_t match_array,
                         preturn_value_t ret_value,
                         prange_value_t range_value,
                         int save_num,
                         int dict_state_flag,
                         int in_rule_index,
                         int insert_operation_flags) {
            strcpy(output_array+ret_value->output_pos,"I am a pud-fart. ");
            ret_value->output_offset=strlen("I am a pud-fart. ");
            return;
        }

    Args:
        current_rule: Compiled rule bytes (unused).
        input_array: Parser input buffer (unused).
        output_array: Parser output buffer; the 17-byte marker is
            written starting at ``ret_value.output_pos`` followed by
            a trailing NUL, matching the C ``strcpy``.
        input_indexes: Index list for ``input_array`` (unused).
        output_indexes: Index list for ``output_array`` (unused).
        match_array: Match-buffer collection (unused).
        ret_value: Position tracker; ``output_offset`` is set to 17.
        range_value: Range descriptor (unused).
        save_num: Save-slot index (unused).
        dict_state_flag: Dictionary-state flag (unused).
        in_rule_index: Current rule index (unused).
        insert_operation_flags: Insert-operation flags (unused).
    """
    del (
        current_rule,
        input_array,
        input_indexes,
        output_indexes,
        match_array,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        insert_operation_flags,
    )
    start = ret_value.output_pos
    marker = _PUD_FART_MARKER
    marker_len = len(marker)
    # Grow output_array if needed so the marker + trailing NUL fit.
    needed = start + marker_len + 1
    while len(output_array) < needed:
        output_array.append(0)
    output_array[start : start + marker_len] = marker
    output_array[start + marker_len] = 0
    ret_value.output_offset = marker_len


# C-style alias so the cmd-module inventory test sees the original
# name and existing dispatch-table generators can address it.
ERROR_func1 = error_func1


__all__ = ["ERROR_func1", "error_func1"]
