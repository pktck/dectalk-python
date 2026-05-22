"""``par_match_rule`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2016-2430.

The recursive driver at the heart of the LTS rule-matching engine.
Given a compiled rule and the current input window, it walks the
rule body byte-by-byte: dispatching to :func:`par_match_string` for
character-type operations and recursing into itself for nested
action / save / replace / dictionary / macro / optional sub-states.

Globals in C
------------
The C source references two file-scope globals for the macro path:

* ``rule_data_table`` -- raw bytes of compiled rules.
* ``rule_index_table`` -- per-rule byte offset into ``rule_data_table``.
* ``perform_action_funcs`` -- function dispatch table indexed by state.

The Linux ``_capi`` path provides the bit-identical output today.
When the data tables are not passed, the compiled rule bytecode
embedded in :mod:`dectalk.cmd.par_rule_data` and the dispatch
table in :mod:`dectalk.cmd.par_perform_action_funcs` are used as
defaults — extracted from ``par_rule2.h`` and the ``perform_action_funcs``
file-static, respectively.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from dectalk.cmd.par_bin_codes import (
    BIN_CONDITIONAL_REPLACE,
    BIN_COPY,
    BIN_COPY_HIT,
    BIN_DICTIONARY,
    BIN_END_OF_RULE,
    BIN_GORET_HIT,
    BIN_GORET_MISS,
    BIN_MACRO,
    BIN_NEXT_HIT,
    BIN_NEXT_MISS,
    BIN_OPERATION_MASK,
    BIN_OPTIONAL,
    BIN_REPLACE,
    BIN_SAVE,
    BIN_SETS,
    BIN_STATUS,
)
from dectalk.cmd.par_copy_string_data import par_copy_string_data
from dectalk.cmd.par_match_string import par_match_string
from dectalk.cmd.par_rule_data import (
    RULE_DATA_TABLE as _DEFAULT_RULE_DATA_TABLE,
)
from dectalk.cmd.par_rule_data import (
    RULE_INDEX_TABLE as _DEFAULT_RULE_INDEX_TABLE,
)
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import END_OF_STRING, FAIL, FATAL_FAIL, OPT_FAIL, SUCCESS

SHIM_DEFERRED: Final[int] = -1
"""Status code returned by helpers when the rule-engine driver is
deferred. Callers that detect this value should treat it as
"engine not wired in" rather than as a real match failure."""

_END_OF_MATCH_FOR_BIN_END_OF_RULE: Final[int] = 255
"""Value the C source stores in ``end_of_match`` when ``state ==
BIN_END_OF_RULE`` -- see par_pars1.c line 2089."""

# BIN_BEFORE (= 0x1C) is the upper bound for the conditional-replace / status
# extended header used in the non-GERMAN_COMPOUND_NOUNS build.
_BIN_BEFORE: Final[int] = 0x1C
"""Inclusive upper bound for state values that carry the conditional-replace
extended header bytes in the non-GERMAN_COMPOUND_NOUNS build path."""


# ---------------------------------------------------------------------------
# Public type alias for the perform_action_funcs entries
# ---------------------------------------------------------------------------

ActionFunc = Callable[
    [
        bytes,  # current_rule
        bytes,  # input_array
        bytearray,  # output_array
        list[IndexData],  # input_indexes
        list[IndexData],  # output_indexes
        MatchArrays,  # match_array
        ReturnValue,  # ret_value (new_ret in C)
        RangeValue,  # range_value
        int,  # save_num
        int,  # dict_state_flag
        int,  # rule_idx (in_rule_index)
    ],
    None,
]
"""Type alias for entries in the ``perform_action_funcs`` dispatch table.

Each entry is a callable matching the C signature::

    void (*perform_action_funcs[0x20])(
        unsigned char *current_rule,
        unsigned char *input_array,
        unsigned char *output_array,
        pindex_data_t  input_indexes,
        pindex_data_t  output_indexes,
        pmatch_arrays_t match_array,
        preturn_value_t ret_value,
        prange_value_t  range_value,
        int save_num,
        int dict_state_flag,
        int in_rule_index)
"""

# Private alias kept for backwards compatibility.
_ActionFunc = ActionFunc


@dataclass(slots=True)
class MatchRuleInputs:
    """Captured inputs for one ``par_match_rule`` invocation.

    Mirrors the C signature::

        void par_match_rule(unsigned char *current_rule, int state,
                            unsigned char *input_array,
                            unsigned char *output_array,
                            pindex_data_t input_indexes,
                            pindex_data_t output_indexes,
                            pmatch_arrays_t match_array,
                            preturn_value_t ret_value,
                            int dict_state_flag);

    Useful for tests / future structural ports that want to thread
    the same nine values without restating them at every call site.

    Attributes:
        current_rule: Compiled rule bytes.
        state: Action / sub-state opcode (``BIN_END_OF_RULE``,
            ``BIN_SAVE``, ``BIN_OPTIONAL``, ``BIN_DICTIONARY`` etc.).
        input_array: Current input text window.
        output_array: Output buffer being built.
        input_indexes: Per-byte pipeline-index data for the input.
        output_indexes: Per-byte pipeline-index data for the output.
        match_array: Saved-string buffers (:class:`MatchArrays`).
        ret_value: Recursion-state object (:class:`ReturnValue`).
        dict_state_flag: ``1`` when invoked from the dictionary-lookup
            path (``par_look_ahead_dictionary``), ``0`` otherwise.
    """

    current_rule: bytes
    state: int
    input_array: bytearray
    output_array: bytearray
    input_indexes: IndexData
    output_indexes: IndexData
    match_array: MatchArrays
    ret_value: ReturnValue
    dict_state_flag: int


def _get_short(data: bytes, pos: int) -> int:
    """Decode a little-endian 16-bit unsigned int from *data[pos:pos+2]*.

    Mirrors the ``get_short()`` C macro used in the BIN_MACRO branch.
    """
    return struct.unpack_from("<H", data, pos)[0]


def par_match_rule(  # noqa: PLR0911, PLR0912, PLR0915
    current_rule: bytes | None,
    state: int,
    input_array: bytearray | None,
    output_array: bytearray | None,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays | None,
    ret_value: ReturnValue | None,
    dict_state_flag: int,
    *,
    rule_data_table: bytes | None = None,
    rule_index_table: list[int] | tuple[int, ...] | None = None,
    perform_action_funcs: list[ActionFunc] | tuple[ActionFunc, ...] | None = None,
) -> int:
    r"""Match one compiled rule against the current input window.

    Faithful translation of the C function at par_pars1.c lines 2016-2430.
    Executes the full rule-walking loop. When ``rule_data_table`` /
    ``rule_index_table`` / ``perform_action_funcs`` are not passed, the
    embedded defaults from :mod:`dectalk.cmd.par_rule_data` and
    :mod:`dectalk.cmd.par_perform_action_funcs` are used.

    Args:
        current_rule: Compiled rule bytes. ``None`` short-circuits
            to ``FATAL_FAIL`` per the C ``SANITY_CHECKING`` block.
        state: Action / sub-state opcode (e.g. ``BIN_END_OF_RULE``,
            ``BIN_SAVE``, ``BIN_OPTIONAL``, ``BIN_DICTIONARY``,
            ``BIN_MACRO``).
        input_array: Input text window. ``None`` -> ``FATAL_FAIL``.
        output_array: Output buffer. ``None`` -> ``FATAL_FAIL``.
        input_indexes: Per-byte pipeline-index data for the input.
        output_indexes: Per-byte pipeline-index data for the output.
        match_array: Saved-string buffers. ``None`` -> ``FATAL_FAIL``.
        ret_value: Recursion-state object. ``None`` -> early return
            (no-op), matching the ``SANITY_CHECKING`` guard.
        dict_state_flag: ``1`` when called from the dictionary path.
        rule_data_table: Raw compiled-rule bytes (file-scope global in C).
            Defaults to :data:`par_rule_data.RULE_DATA_TABLE`.
        rule_index_table: Per-rule byte offsets (file-scope global in C).
            Defaults to :data:`par_rule_data.RULE_INDEX_TABLE`.
        perform_action_funcs: Action-function dispatch table (file-scope
            in C). Defaults to :data:`par_perform_action_funcs.PERFORM_ACTION_FUNCS`.

    Returns:
        The resulting ``value`` field of ``ret_value`` (or ``SUCCESS``
        when ``ret_value`` is ``None``).
    """
    # SANITY_CHECKING block: par_pars1.c lines 2048-2066.
    if ret_value is None:
        return SUCCESS

    if current_rule is None or input_array is None or output_array is None or match_array is None:
        ret_value.value = FATAL_FAIL
        return FATAL_FAIL

    # Fall back to the embedded compiled tables (par_rule2.h) and the
    # dispatch table (par_perform_action_funcs) when the caller did
    # not pass explicit overrides. Mirrors the C globals at par_pars1.c
    # file scope. ``par_perform_action_funcs`` is imported lazily to
    # avoid an import cycle (it depends on ``ActionFunc`` from this
    # module).
    if rule_data_table is None:
        rule_data_table = _DEFAULT_RULE_DATA_TABLE
    if rule_index_table is None:
        rule_index_table = _DEFAULT_RULE_INDEX_TABLE
    if perform_action_funcs is None:
        from dectalk.cmd.par_perform_action_funcs import (  # noqa: PLC0415
            PERFORM_ACTION_FUNCS,
        )

        perform_action_funcs = PERFORM_ACTION_FUNCS

    # Local variables (par_pars1.c lines 2024-2041).
    new_operation: int = BIN_END_OF_RULE
    num_chars_matched: int = 0
    save_state_num: int = 0
    range_value: RangeValue = RangeValue(start=0, end=0, min=0, range_set=0)
    in_rule_index: int
    end_of_match: int = 0

    # length_of_input = strlen(input_array)
    nul_pos = input_array.find(0)
    length_of_input = nul_pos if nul_pos >= 0 else len(input_array)

    # Build new_ret from ret_value (par_pars1.c lines 2068-2083).
    new_ret = ReturnValue(
        input_pos=ret_value.input_pos + ret_value.input_offset,
        input_offset=0,
        output_pos=ret_value.output_pos + ret_value.output_offset,
        output_offset=0,
        value=SUCCESS,
        parser_flag=ret_value.parser_flag,
        optional=0,
        rule=ret_value.rule,
        state=0,
        prev=None,
    )
    in_rule_index = new_ret.rule

    # end_of_match = 255 when state == BIN_END_OF_RULE (par_pars1.c line 2089).
    if state == BIN_END_OF_RULE:
        end_of_match = 255

    # Optional flag (par_pars1.c lines 2092-2100).
    if state == BIN_OPTIONAL:
        new_ret.optional = 1
    else:
        new_ret.optional = ret_value.optional

    # -----------------------------------------------------------------------
    # BIN_MACRO branch (par_pars1.c lines 2112-2171)
    # -----------------------------------------------------------------------
    if state == BIN_MACRO:
        # rule_data_table / rule_index_table are guaranteed non-None
        # here: the preamble falls back to the embedded compiled tables
        # from ``par_rule_data`` when the caller does not supply them.
        rule_p = new_ret.rule
        rule_p += 1  # skip state identifier
        next_rule_number = _get_short(current_rule, rule_p)
        rule_p += 2
        new_rule = rule_data_table[rule_index_table[next_rule_number] :]
        new_ret.rule = 0
        if new_rule[0] & BIN_NEXT_HIT:
            new_ret.rule += 2
        if new_rule[0] & BIN_NEXT_MISS:
            new_ret.rule += 2
        if new_rule[0] & BIN_GORET_HIT:
            new_ret.rule += 2
        if new_rule[0] & BIN_GORET_MISS:
            new_ret.rule += 2
        if new_rule[0] & BIN_COPY_HIT:
            new_ret.rule += 2
        new_ret.rule += 12

        par_match_rule(
            bytes(new_rule),
            BIN_END_OF_RULE,
            input_array,
            output_array,
            input_indexes,
            output_indexes,
            match_array,
            new_ret,
            0,
            rule_data_table=rule_data_table,
            rule_index_table=rule_index_table,
            perform_action_funcs=perform_action_funcs,
        )
        # fixed macro state
        new_ret.rule = rule_p
        if new_ret.input_pos + new_ret.input_offset > length_of_input:
            if new_ret.optional == 1:
                ret_value.value = OPT_FAIL
                return OPT_FAIL
            else:
                ret_value.value = END_OF_STRING
                return END_OF_STRING
        if new_ret.value == FAIL and new_ret.optional:
            ret_value.value = OPT_FAIL
            return OPT_FAIL
    else:
        # -----------------------------------------------------------------------
        # Non-MACRO: save/dictionary pre-processing (par_pars1.c lines 2101-2111).
        # This runs BEFORE the BIN_COPY-range check below.
        # -----------------------------------------------------------------------
        if state == BIN_SAVE:
            new_ret.rule += 1  # skip the operation opcode
            save_state_num = current_rule[new_ret.rule]
        elif state == BIN_DICTIONARY:
            new_ret.rule += 1
            save_state_num = current_rule[new_ret.rule]

        # -----------------------------------------------------------------------
        # State data extraction (par_pars1.c lines 2175-2210).
        # BIN_COPY = 0x14; this block applies to BIN_COPY and all states above.
        # -----------------------------------------------------------------------
        if state >= BIN_COPY:  # BIN_COPY = 0x14
            new_ret.rule += 1  # skip the operation byte
            end_of_match = current_rule[new_ret.rule]
            new_ret.rule += 1
            if BIN_REPLACE <= state <= _BIN_BEFORE:
                new_ret.rule += 1
                if current_rule[in_rule_index] & BIN_CONDITIONAL_REPLACE:
                    new_ret.rule += current_rule[new_ret.rule]
                    new_ret.rule += 1  # add 1 for the conditional number
            elif state == BIN_DICTIONARY:
                new_ret.rule += 2
            elif state == BIN_STATUS:
                new_ret.rule += 1

        # -----------------------------------------------------------------------
        # Main walk loop (par_pars1.c lines 2214-2299).
        # -----------------------------------------------------------------------
        while (
            new_ret.rule <= end_of_match
            and (temp := current_rule[new_ret.rule]) != 0
            and new_ret.value == SUCCESS
        ):
            new_operation = temp & BIN_OPERATION_MASK

            if new_operation <= BIN_SETS:
                # Dispatch to par_match_string.
                num_chars_matched = par_match_string(
                    current_rule,
                    new_operation,
                    bytes(input_array),
                    match_array,
                    new_ret,
                    range_value,
                    1,
                    0,
                )

                if num_chars_matched == -1:
                    # End of string reached inside string match.
                    if new_ret.optional == 1:
                        new_ret.value = OPT_FAIL
                        break
                    else:
                        ret_value.value = END_OF_STRING
                        return END_OF_STRING

                if num_chars_matched == 0 and new_ret.optional:
                    new_ret.value = OPT_FAIL
                    break

                par_copy_string_data(
                    input_array,
                    input_indexes,
                    output_array,
                    output_indexes,
                    num_chars_matched,
                    new_ret,
                )
                new_ret.output_offset += num_chars_matched
                new_ret.input_offset += num_chars_matched
            else:
                # Recursively call par_match_rule with the new action state.
                # perform_action_funcs is guaranteed non-None here (falls
                # back to the module default in the preamble above).
                par_match_rule(
                    current_rule,
                    new_operation,
                    input_array,
                    output_array,
                    input_indexes,
                    output_indexes,
                    match_array,
                    new_ret,
                    0,
                    rule_data_table=rule_data_table,
                    rule_index_table=rule_index_table,
                    perform_action_funcs=perform_action_funcs,
                )

                if new_ret.value == END_OF_STRING:
                    if new_ret.optional == 1:
                        new_ret.value = OPT_FAIL
                        break
                    else:
                        ret_value.value = END_OF_STRING
                        return END_OF_STRING

            # Check for end of input after either path.
            if new_ret.input_pos + new_ret.input_offset > length_of_input:
                if new_ret.optional == 1:
                    new_ret.value = OPT_FAIL
                    break
                else:
                    new_ret.value = END_OF_STRING

    # -----------------------------------------------------------------------
    # Post-loop: handle the walk result (par_pars1.c lines 2302-2430).
    # -----------------------------------------------------------------------
    if new_ret.value == FAIL:
        ret_value.value = FAIL
        # Clear output indexes for failed match (memset in C).
        for i in range(new_ret.output_offset):
            idx = new_ret.output_pos + i
            if idx < len(output_indexes):
                output_indexes[idx] = IndexData()
        return FAIL

    if new_ret.value == END_OF_STRING:
        for i in range(new_ret.output_offset):
            idx = new_ret.output_pos + i
            if idx < len(output_indexes):
                output_indexes[idx] = IndexData()
        ret_value.value = END_OF_STRING
        return END_OF_STRING

    if new_ret.value != OPT_FAIL:
        # Verify end-of-state slash was found (par_pars1.c lines 2318-2326).
        if state not in (BIN_END_OF_RULE, BIN_MACRO) and new_ret.rule != end_of_match + 1:
            ret_value.value = FATAL_FAIL
            return FATAL_FAIL

        # Perform the action for this state (par_pars1.c lines 2331-2341).
        # perform_action_funcs is guaranteed non-None here (falls back
        # to the module default in the preamble above).
        if state != BIN_END_OF_RULE:
            perform_action_funcs[state](
                current_rule,
                bytes(input_array),
                output_array,
                input_indexes,
                output_indexes,
                match_array,
                new_ret,
                range_value,
                save_state_num,
                dict_state_flag,
                in_rule_index,
            )

        # Propagate parser_flag.
        ret_value.parser_flag = new_ret.parser_flag

        if new_ret.value == FATAL_FAIL:
            ret_value.value = FATAL_FAIL
            return FATAL_FAIL

        if new_ret.value == FAIL:
            for i in range(new_ret.output_offset):
                idx = new_ret.output_pos + i
                if idx < len(output_indexes):
                    output_indexes[idx] = IndexData()
            ret_value.value = FAIL
            return FAIL

        ret_value.value = SUCCESS
        ret_value.input_offset += new_ret.input_offset
        ret_value.output_offset += new_ret.output_offset
    else:
        # OPT_FAIL path.
        for i in range(new_ret.output_offset):
            idx = new_ret.output_pos + i
            if idx < len(output_indexes):
                output_indexes[idx] = IndexData()

        if state == BIN_OPTIONAL:
            ret_value.rule = end_of_match + 1
            ret_value.value = SUCCESS
            return SUCCESS

        ret_value.value = OPT_FAIL

    ret_value.rule = new_ret.rule
    return ret_value.value


def par_match_rule_validate(
    current_rule: bytes | None,
    input_array: bytearray | None,
    output_array: bytearray | None,
    match_array: MatchArrays | None,
    ret_value: ReturnValue | None,
) -> int:
    """Run *only* the SANITY_CHECKING block from ``par_match_rule``.

    Faithful translation of par_pars1.c lines 2049-2066. Useful for
    tests that want to exercise the deterministic validation logic
    without driving the full rule-walk in :func:`par_match_rule`.

    Args:
        current_rule: Compiled rule bytes (``None`` triggers FATAL).
        input_array: Input window (``None`` triggers FATAL).
        output_array: Output buffer (``None`` triggers FATAL).
        match_array: Saved-string buffers (``None`` triggers FATAL).
        ret_value: Recursion-state object (``None`` -> no-op).

    Returns:
        :data:`SUCCESS` if all pointers are non-None.
        :data:`FATAL_FAIL` if any of the four mandatory pointers is
        None (writes ``ret_value.value = FATAL_FAIL`` first).
        :data:`SUCCESS` (no-op) if ``ret_value is None``.
    """
    if ret_value is None:
        return SUCCESS
    if current_rule is None or input_array is None or output_array is None or match_array is None:
        ret_value.value = FATAL_FAIL
        return FATAL_FAIL
    return SUCCESS


# Re-export so callers can mention the macro/dictionary opcodes the
# real driver branches on, without re-importing par_bin_codes.
_RECURSIVE_SUB_STATES: Final[tuple[int, ...]] = (
    BIN_OPTIONAL,
    BIN_SAVE,
    BIN_MACRO,
    BIN_DICTIONARY,
)
"""Sub-state opcodes par_match_rule recurses into; surfaced here so
parity tests can pin the list against par_pars1.c lines 2112-2171."""


__all__ = [
    "SHIM_DEFERRED",
    "ActionFunc",
    "MatchRuleInputs",
    "par_match_rule",
    "par_match_rule_validate",
]
