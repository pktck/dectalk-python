"""``par_compound_break`` German compound-noun splitter from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2801-2868.

The function attempts to split a German compound noun into its
constituent parts using a loaded compound-mapping table. On the
US-English build the compound table is never loaded
(``noun_num_character_in_mapping`` stays 0), so the function
takes the early-return path and the Python port is effectively a
no-op that leaves the input unchanged.

The full splitter chain (``par_break_down_word`` /
``par_find_word_in_dict`` plus the compound-mapping data) remains
deferred — it only activates for German input which the US-only
build never produces.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

# Mirrors the C source's `noun_num_character_in_mapping` global.
# Stays 0 on the US build because the German compound-mapping
# table is never loaded.
_NOUN_NUM_CHARACTER_IN_MAPPING: int = 0


def par_compound_break(
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
    """German compound-noun splitter (no-op on US English).

    Faithful translation of the C source's early-return path —
    when ``noun_num_character_in_mapping == 0`` (the US build's
    permanent state, since no compound dictionary is loaded),
    the function returns immediately. The Python port mirrors
    that: the input and output arrays are unchanged.

    Args:
        current_rule: Rule bytes (unused on the US path).
        input_array: Parser input buffer.
        output_array: Parser output buffer.
        input_indexes: Index list for ``input_array``.
        output_indexes: Index list for ``output_array``.
        match_array: Match-buffer collection.
        ret_value: Parser cursors (unchanged on the early-return).
        range_value: Range descriptor (unused on the US path).
        save_num: Save-slot index (unused on the US path).
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
    if _NOUN_NUM_CHARACTER_IN_MAPPING == 0:
        # The early-return path on the US English build.
        return
    # Full splitter (par_break_down_word + par_find_word_in_dict +
    # the compound-mapping table) is deferred — only relevant for
    # German input which the US-only build never produces.


__all__ = ["par_compound_break"]
