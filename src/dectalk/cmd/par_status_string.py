"""``par_status_string`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3929-3950.

Thin wrapper around :func:`par_build_string_from_rule`: builds the
``BIN_STATUS`` string from the current rule into a 10-byte stack
buffer, then converts the ASCII-decimal contents to an integer
and stores it in ``ret_value.parser_flag``. This is how rules
forward a small numeric status code (``parser_status`` kernel
variable) out of the parser.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_STATUS
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_number import par_convert_number_new2
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_BUF_SIZE = 10
"""Stack-allocated ``buf[10]`` from the C source."""


def par_status_string(
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
    r"""Read a BIN_STATUS string and stash it as ``ret_value.parser_flag``.

    Faithful translation of:

    .. code-block:: c

        void par_status_string(unsigned char *current_rule,
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
            int length = 0;
            unsigned char buf[10];

            par_build_string_from_rule(current_rule, buf, output_array,
                                       match_array, ret_value, range_value,
                                       BIN_STATUS, &length, in_rule_index);
            ret_value->parser_flag = atoi(buf);
        }

    Args:
        current_rule: Compiled rule bytes (read only).
        input_array: Unused on this path.
        output_array: Forwarded to
            :func:`par_build_string_from_rule` (read for
            conditional-digit sniffing).
        input_indexes: Unused on this path.
        output_indexes: Unused on this path.
        match_array: ``$N`` save slot collection.
        ret_value: Parser cursors; ``parser_flag`` becomes the
            integer value of the built string on success.
        range_value: Range-match state.
        save_num: Save-slot index (unused on this path).
        dict_state_flag: Dictionary-state flag (unused on this path).
        in_rule_index: Action-descriptor offset in ``current_rule``.
        insert_operation_flags: Unused on this path.

    Notes:
        The C source uses :c:func:`atoi` which converts a decimal
        string ignoring leading whitespace and stopping at the first
        non-digit. The Python port uses
        :func:`par_convert_number_new2` (already ported and equivalent
        for the rule-engine inputs the C source produces — purely
        decimal digit runs ending at NUL).
    """
    # Silence unused-parameter complaints.
    del input_array, input_indexes, output_indexes, save_num, dict_state_flag
    del insert_operation_flags

    buf = bytearray(_BUF_SIZE)
    length_box = [0]

    par_build_string_from_rule(
        current_rule,
        buf,
        output_array,
        match_array,
        ret_value,
        range_value,
        BIN_STATUS,
        length_box,
        in_rule_index,
    )

    # atoi(buf) -- convert the leading decimal run to an integer.
    ret_value.parser_flag = par_convert_number_new2(bytes(buf))


__all__ = ["par_status_string"]
