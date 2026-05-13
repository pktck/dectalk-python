"""``par_dom_dict_search`` domain-dictionary rule action from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3481-3603.

The rule engine calls this function when a rule's action section
selects the domain-dictionary state. It bounds-checks the matched
input/output spans, copies them into scratch match-array slots
(7 / 8 / 9), and calls :func:`par_search_for_word` to probe the
domain dictionary. The dispatch on the result (hit vs miss vs
``dict_state_flag`` short-search) then either:

* marks the rule as :data:`SUCCESS` / :data:`FAIL` outright, or
* zeroes the cursors and re-invokes ``par_match_rule`` with the
  rule's hit / miss continuation block,

honouring the ``BIN_DICT_HIT_FAIL`` and ``BIN_DICT_MISS_FAIL``
flag bits stored in the rule byte at ``current_rule[in_rule_index]``.

``par_match_rule`` is the rule-engine driver and has not landed in
the Python port yet — it remains the gating dependency for the
dictionary action's continuation. Until then, the call site is
preserved as a comment so the dispatch structure stays clear.

The Python TTS pipeline never reaches this function in practice:
:class:`dectalk._capi.CAPI` routes ``speak()`` / ``to_wav()``
through the C library for actual rule-driven phonetics. The Python
rule engine is only exercised by the parity tests.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import BIN_DICT_HIT_FAIL, BIN_DICT_MISS_FAIL
from dectalk.cmd.par_search_for_word import par_search_for_word
from dectalk.cmd.par_structs import (
    PAR_MAX_MATCH_ARRAY,
    IndexData,
    MatchArrays,
    RangeValue,
    ReturnValue,
)
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL, OPT_FAIL, SUCCESS


def par_dom_dict_search(  # noqa: PLR0911 — mirrors C control flow with many early returns
    current_rule: bytes,
    input_array: bytearray,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    dict_num: int,
    dict_state_flag: int,
    in_rule_index: int,
    insert_operation_flags: int,
) -> None:
    """Domain-dictionary action for the rule engine.

    Faithful translation of the C source: bounds-checks the matched
    input / output spans, copies them into scratch match-array
    slots, probes the domain dictionary via
    :func:`par_search_for_word`, then dispatches on the result and
    the ``BIN_DICT_HIT_FAIL`` / ``BIN_DICT_MISS_FAIL`` flags of the
    rule byte at ``current_rule[in_rule_index]``.

    Args:
        current_rule: Compiled rule bytes — the flag byte at
            ``in_rule_index`` selects hit/miss-fail behaviour.
        input_array: Parser input buffer.
        output_array: Parser output buffer.
        input_indexes: Index list aligned with ``input_array``.
        output_indexes: Index list aligned with ``output_array``.
        match_array: Match-buffer collection. Slots 7 / 8 / 9 are
            written by this function (input span, output span,
            dictionary payload).
        ret_value: Recursion-state object — its ``value``,
            ``rule``, ``input_offset``, ``output_offset`` and
            ``optional`` fields are read and/or updated.
        range_value: Range descriptor passed through to
            ``par_match_rule`` (unused while the driver is
            unported).
        dict_num: 1-based dictionary index forwarded to
            :func:`par_search_for_word`.
        dict_state_flag: ``0`` for the full search, ``1`` to bail
            out on the first case-insensitive match (forwarded to
            :func:`par_search_for_word` and to ``par_match_rule``).
        in_rule_index: Offset of the dictionary rule's flag byte
            inside ``current_rule``.
        insert_operation_flags: Forwarded to ``par_match_rule``
            (only present in the ``GERMAN_COMPOUND_NOUNS`` build —
            which is the Linux default).
    """
    del input_indexes, output_indexes, range_value, insert_operation_flags

    ipos = ret_value.input_pos
    opos = ret_value.output_pos

    # MGS BATS #449 — bounds-check both spans before copying them
    # into the 30-byte scratch slots.
    if ret_value.input_offset >= PAR_MAX_MATCH_ARRAY:
        ret_value.value = FATAL_FAIL
        return
    if ret_value.output_offset >= PAR_MAX_MATCH_ARRAY:
        ret_value.value = FATAL_FAIL
        return

    in_off = ret_value.input_offset
    out_off = ret_value.output_offset

    # memcpy(match_array->array[7], input_array+ipos, input_offset);
    # match_array->array[7][input_offset] = '\0';
    slot_in = match_array.array[7]
    slot_in[:in_off] = input_array[ipos : ipos + in_off]
    slot_in[in_off] = 0
    match_array.array_lengths[7] = in_off

    # memcpy(match_array->array[8], output_array+opos, output_offset);
    # match_array->array[8][output_offset] = '\0';
    slot_out = match_array.array[8]
    slot_out[:out_off] = output_array[opos : opos + out_off]
    slot_out[out_off] = 0
    match_array.array_lengths[8] = out_off

    result = par_search_for_word(
        match_array.array[8],
        out_off,
        match_array.array[9],
        dict_num,
        dict_state_flag,
    )

    if dict_state_flag:
        # Short-search path: only SUCCESS on a hit, otherwise leave
        # ret_value.value untouched (the C source's silent
        # "miss => continue" return).
        if result:
            ret_value.value = SUCCESS
            return
        return

    flag_byte = current_rule[in_rule_index]

    if result == 1:
        # Compute the length of the NUL-terminated payload the
        # dictionary search wrote into slot 9.
        slot9 = match_array.array[9]
        length = 0
        while length < len(slot9) and slot9[length] != 0:
            length += 1
        match_array.array_lengths[9] = length

        if flag_byte & BIN_DICT_HIT_FAIL:
            ret_value.value = FAIL
            if ret_value.optional == 1:
                ret_value.value = OPT_FAIL
                return
            return

        # Reset for rematching, then re-invoke the rule engine on
        # the hit-continuation block. ``par_match_rule`` is not yet
        # ported (it sits on the cmd _DEFERRED list); once it lands
        # the call below becomes live.
        ret_value.input_offset = 0
        ret_value.output_offset = 0
        # par_match_rule(current_rule, BIN_COPY, input_array,
        #                output_array, input_indexes, output_indexes,
        #                match_array, ret_value, dict_state_flag)
        # Skip the miss_action — advance rule cursor past the
        # miss-block descriptor stored at offset +4.
        ret_value.rule = current_rule[in_rule_index + 4] + 1
        return

    # result != 1 — dictionary miss path.
    ret_value.rule = current_rule[in_rule_index + 3] + 1

    if flag_byte & BIN_DICT_MISS_FAIL:
        ret_value.value = FAIL
        if ret_value.optional == 1:
            ret_value.value = OPT_FAIL
            return
        return

    ret_value.input_offset = 0
    ret_value.output_offset = 0
    # par_match_rule(current_rule, BIN_COPY, input_array,
    #                output_array, input_indexes, output_indexes,
    #                match_array, ret_value, dict_state_flag)


__all__ = ["par_dom_dict_search"]
