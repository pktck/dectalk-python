"""``ERROR_func2`` empty-body fallback from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 631-649.

The slot-0 entry in the ``perform_action_funcs[]`` rule-action
dispatch table. Its body is just ``return;`` in the C source --
the engine reaches it when the compiled rule asks for action
opcode 0x00, which is the "do nothing" placeholder.

The Python port is a no-op for parity. The C-style name
``ERROR_func2`` is re-exported alongside the PEP8 :func:`error_func2`
so the cmd-module inventory and any dispatch-table generator can
address the function by its original identifier.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue


def error_func2(
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
    r"""Empty-body no-op (slot-0 dispatch placeholder).

    Faithful translation of:

    .. code-block:: c

        void ERROR_func2(unsigned char *current_rule,
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
            return;
        }

    Args:
        current_rule: Compiled rule bytes (unused).
        input_array: Parser input buffer (unused).
        output_array: Parser output buffer (unused).
        input_indexes: Index list for ``input_array`` (unused).
        output_indexes: Index list for ``output_array`` (unused).
        match_array: Match-buffer collection (unused).
        ret_value: Position tracker (unused).
        range_value: Range descriptor (unused).
        save_num: Save-slot index (unused).
        dict_state_flag: Dictionary-state flag (unused).
        in_rule_index: Current rule index (unused).
        insert_operation_flags: Insert-operation flags (unused).
    """
    del (
        current_rule,
        input_array,
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        insert_operation_flags,
    )


# C-style alias for parity with the inventory and dispatch tables.
ERROR_func2 = error_func2


__all__ = ["ERROR_func2", "error_func2"]
