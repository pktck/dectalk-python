"""``par_process_input`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 1007-1730.

The top-level rule-tabling driver -- the outer loop of the LTS rule
engine. ``par_process_input`` walks the input string word by word,
skipping whitespace, picking up the rule-section's starting rule
number, and for each rule looks up the compiled bytes from
``rule_data_table`` (indexed via ``rule_index_table``) before
dispatching to :func:`par_match_rule`. After each match it
reconciles the new input / output windows, handles dictionary
hit / miss branches (``BIN_DICT_HIT`` / ``BIN_DICT_MISS``), follows
``NEXT_HIT`` / ``NEXT_MISS`` / ``GORET_HIT`` / ``GORET_MISS``
jumps, and emits the matched bytes to ``output_array``.

Globals in C
------------
The C source references five file-scope globals that must be provided
by the caller when the full rule-walking loop should execute:

* ``num_rule_sections`` -- number of rule sections in the rule table.
* ``rule_sections`` -- maps rule-section index to first rule number.
* ``num_rules`` -- total number of rules.
* ``rule_index_table`` -- per-rule byte offset into ``rule_data_table``.
* ``rule_data_table`` -- raw bytes of compiled rules.

The Linux ``_capi`` path provides the bit-identical output today.
When the tables are not provided, the compiled rule bytecode
embedded in :mod:`dectalk.cmd.par_rule_data` (extracted from
``par_rule2.h``) and the dispatch table in
:mod:`dectalk.cmd.par_perform_action_funcs` are used as defaults.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Final

from dectalk.cmd.par_bin_codes import (
    BIN_COPY_HIT,
    BIN_DICT_HIT,
    BIN_DICT_MISS,
    BIN_END_OF_RULE,
    BIN_GORET,
    BIN_GORET_HIT,
    BIN_GORET_MISS,
    BIN_GOTO,
    BIN_NEXT_HIT,
    BIN_NEXT_MISS,
    BIN_RETURN,
    BIN_SPECIAL_RULE_MASK,
    BIN_STOP,
)
from dectalk.cmd.par_copy_return_value import par_copy_return_value
from dectalk.cmd.par_copy_word_to_output import par_copy_word_to_output
from dectalk.cmd.par_index import par_copy_index, par_copy_index_list
from dectalk.cmd.par_limits import PAR_MAX_RETURN_LEVEL
from dectalk.cmd.par_match_rule import ActionFunc, par_match_rule
from dectalk.cmd.par_perform_action_funcs import PERFORM_ACTION_FUNCS
from dectalk.cmd.par_return_stack import par_get_return_level, par_set_return_level
from dectalk.cmd.par_rule_data import (
    NUM_RULE_SECTIONS,
    NUM_RULES,
    RULE_DATA_TABLE,
    RULE_INDEX_TABLE,
    RULE_SECTIONS,
)
from dectalk.cmd.par_skip_white_space import par_skip_white_space
from dectalk.cmd.par_structs import IndexData, MatchArrays, ReturnValue
from dectalk.cmd.parser_tables import TYPE_clause, TYPE_white, parser_char_types
from dectalk.cmd.rule_states import DICT_MISS_VALUE, FAIL, SUCCESS

SHIM_DEFERRED: Final[int] = -1
"""Status code returned by helpers when the rule-engine driver is
deferred. Callers that detect this value should treat it as
"engine not wired in" rather than as a real failure."""

INVALID_RULE_SECTION_MESSAGE: Final[bytes] = b"Invalid rule section. "
"""Bytes the C source writes into ``output_array`` when the requested
rule section is out of range -- see par_pars1.c line 1094."""

_DICT_ABBREV_VALUE: Final[int] = 2
"""Sentinel for a word that matched both BIN_DICT_HIT and BIN_DICT_MISS
conditions (abbreviation). DICT_ABBREV_VALUE is not in any parseable
header; 2 is the only value distinct from DICT_HIT_VALUE=1 / DICT_MISS_VALUE=0."""

_MODE_FLAG_WILDCARD: Final[int] = 0xFFFF_FFFF
"""Wildcard mode value meaning 'match any mode'; used in rule headers."""


@dataclass(slots=True)
class ProcessInputState:
    r"""Captured deterministic state for one ``par_process_input`` call.

    Mirrors the locals the C function initialises before the
    ``while (new_input[...]!='\0')`` loop at par_pars1.c line 1109.
    Useful for tests that want to inspect the pre-loop snapshot
    without driving the rule walk.

    Attributes:
        input_length: ``(strlen(input_array) * 2) / 3`` -- see line 1106.
        return_rule: ``PAR_MAX_RETURN_LEVEL`` slots, memset to ``-1``.
            Used as the GORET return-stack (lines 1097 / 1055).
        return_level: Current depth into ``return_rule`` (line 1056).
        done: Outer-loop termination flag (line 1049).
        last_rule_was_hit: Tracks whether the previous rule hit, for
            chained next-hit logic (line 1053).
        current_rule_number: Index into ``rule_index_table`` for the
            rule about to be processed (line 1054).
        new_input_diff: Cumulative diff between ``new_input`` and
            ``input_array`` sizes (line 1058). Used to convert the
            new-input cursor back to the caller's frame at exit.
        do_not_copy_next_word: Set to ``1`` when an action wrote
            whitespace into the output so the next word should be
            kept (line 1061).
    """

    input_length: int
    return_rule: list[int]
    return_level: int
    done: int
    last_rule_was_hit: int
    current_rule_number: int
    new_input_diff: int
    do_not_copy_next_word: int


def _init_state(input_length: int) -> ProcessInputState:
    """Build the deterministic pre-loop state.

    Faithful translation of par_pars1.c lines 1031-1106:

    * ``return_rule`` is memset to ``-1`` (line 1097).
    * ``input_length = (strlen(input_array) * 2) / 3`` (line 1106).
    * All other ints start at the defaults shown in the dataclass.
    """
    return ProcessInputState(
        input_length=(input_length * 2) // 3,
        return_rule=[-1] * PAR_MAX_RETURN_LEVEL,
        return_level=0,
        done=0,
        last_rule_was_hit=0,
        current_rule_number=0,
        new_input_diff=0,
        do_not_copy_next_word=0,
    )


def par_process_input(  # noqa: PLR0912, PLR0915
    input_array: bytearray | None,
    new_input: bytearray | None,
    output_array: bytearray | None,
    dict_hit_array: bytearray | None,
    input_indexes: list[IndexData],
    new_input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    in_lang_flag: int,
    in_mode_flag: int,
    rule: int,
    go_until: int,
    match_array: MatchArrays | None,
    ret_value: ReturnValue,
    *,
    num_rule_sections: int | None = None,
    rule_sections: list[int] | tuple[int, ...] | None = None,
    num_rules: int | None = None,
    rule_index_table: list[int] | tuple[int, ...] | None = None,
    rule_data_table: bytes | None = None,
    perform_action_funcs: list[ActionFunc] | tuple[ActionFunc, ...] | None = None,
) -> ReturnValue:
    r"""Drive the rule-table parser over ``input_array``.

    Faithful translation of the C function at par_pars1.c lines 1007-1730.
    Executes the full rule-tabling loop. When the data tables are not
    passed, the embedded defaults from :mod:`dectalk.cmd.par_rule_data`
    and :mod:`dectalk.cmd.par_perform_action_funcs` are used.

    Args:
        input_array: Original input bytes.
        new_input: Scratch input buffer.
        output_array: Output buffer to write into.
        dict_hit_array: Per-position dictionary-hit flags.
        input_indexes: Per-byte pipeline-index data for input_array.
        new_input_indexes: Per-byte pipeline-index data for new_input.
        output_indexes: Per-byte pipeline-index data for output_array.
        in_lang_flag: 32-bit language flag.
        in_mode_flag: 32-bit mode flag.
        rule: Rule-section index.
        go_until: 0 -> drive until NUL; 1 -> drive until input_length.
        match_array: Saved-string buffers.
        ret_value: Caller ReturnValue; updated on exit.
        num_rule_sections: Number of rule sections available. Defaults
            to :data:`par_rule_data.NUM_RULE_SECTIONS`.
        rule_sections: Array mapping rule-section index to first rule
            number. Defaults to :data:`par_rule_data.RULE_SECTIONS`.
        num_rules: Total number of rules. Defaults to
            :data:`par_rule_data.NUM_RULES`.
        rule_index_table: Per-rule byte offsets into rule_data_table.
            Defaults to :data:`par_rule_data.RULE_INDEX_TABLE`.
        rule_data_table: Raw compiled-rule bytes. Defaults to
            :data:`par_rule_data.RULE_DATA_TABLE`.
        perform_action_funcs: Action-function dispatch table.
            Defaults to :data:`par_perform_action_funcs.PERFORM_ACTION_FUNCS`.

    Returns:
        ret_value. When rule index is out of range, writes
        "Invalid rule section. " into output_array and returns.
    """
    # Fall back to embedded compiled rule tables (par_rule2.h) when the
    # caller did not pass overrides. Mirrors the C build's use of the
    # module-static globals at file scope.
    if rule_sections is None:
        rule_sections = RULE_SECTIONS
    if rule_index_table is None:
        rule_index_table = RULE_INDEX_TABLE
    if rule_data_table is None:
        rule_data_table = RULE_DATA_TABLE
    if perform_action_funcs is None:
        perform_action_funcs = PERFORM_ACTION_FUNCS
    if num_rule_sections is None:
        num_rule_sections = NUM_RULE_SECTIONS
    if num_rules is None:
        num_rules = NUM_RULES

    # Initialise new_ret from caller (par_pars1.c lines 1067-1086).
    new_ret = ReturnValue(
        input_pos=ret_value.input_pos + ret_value.input_offset,
        input_offset=0,
        output_pos=ret_value.output_pos + ret_value.output_offset,
        output_offset=0,
        value=0,
        parser_flag=ret_value.parser_flag,
        optional=0,
        rule=0,
        state=0,
        prev=None,
    )

    # Out-of-range rule index, par_pars1.c lines 1089-1096.
    if rule > num_rule_sections:
        if output_array is not None:
            payload = INVALID_RULE_SECTION_MESSAGE + b"\x00"
            length = min(len(payload), len(output_array))
            output_array[:length] = payload[:length]
        return ret_value

    if input_array is None or new_input is None or output_array is None or match_array is None:
        ret_value.value = FAIL
        return ret_value

    if dict_hit_array is None:
        dict_hit_array = bytearray(len(input_array))

    nul_pos = input_array.find(0)
    input_length = nul_pos if nul_pos >= 0 else len(input_array)

    copy_len = min(input_length + 1, len(new_input))
    new_input[:copy_len] = input_array[:copy_len]
    if copy_len < len(new_input):
        new_input[copy_len] = 0

    par_copy_index_list(new_input_indexes, 0, input_indexes, 0, input_length)

    state = _init_state(input_length)

    # -----------------------------------------------------------------------
    # Full rule-driving loop (par_pars1.c lines 1109-1721).
    # -----------------------------------------------------------------------
    # These are guaranteed non-None now: the preamble above falls back to
    # the module-level defaults from ``par_rule_data`` /
    # ``par_perform_action_funcs`` when the caller does not supply them.
    assert rule_sections is not None
    assert rule_index_table is not None
    assert rule_data_table is not None
    assert perform_action_funcs is not None

    return_rule: list[int] = [-1] * PAR_MAX_RETURN_LEVEL
    return_level: list[int] = [0]
    done: int = 0
    last_rule_was_hit: int = 0
    new_input_diff: int = 0
    do_not_copy_next_word: int = 0
    hit_ret = ReturnValue(
        input_pos=0,
        input_offset=0,
        output_pos=0,
        output_offset=0,
        value=0,
        parser_flag=0,
        optional=0,
        rule=0,
        state=0,
        prev=None,
    )
    save_ret = ReturnValue(
        input_pos=0,
        input_offset=0,
        output_pos=0,
        output_offset=0,
        value=0,
        parser_flag=0,
        optional=0,
        rule=0,
        state=0,
        prev=None,
    )
    # scaled input_length from _init_state
    scaled_input_length = state.input_length

    # Outer word loop.
    while (new_input[new_ret.input_pos + new_ret.input_offset] != 0 and go_until == 0) or (
        (new_ret.input_pos + new_ret.input_offset - new_input_diff) < scaled_input_length
        and go_until == 1
    ):
        if (
            par_skip_white_space(
                bytes(new_input),
                new_input_indexes,
                output_array,
                output_indexes,
                new_ret,
            )
            == -1
        ):
            done = 1

        par_copy_return_value(save_ret, new_ret)
        current_rule_number = rule_sections[rule]
        last_rule_was_hit = 0

        while not done:
            current_rule = bytes(rule_data_table[rule_index_table[current_rule_number] :])
            rule_p = 0

            # Special rule check (BIN_STOP / BIN_RETURN / BIN_GOTO / BIN_GORET).
            rule_flags_val = struct.unpack_from("<H", current_rule, 0)[0]
            current_value = rule_flags_val

            if current_value & BIN_SPECIAL_RULE_MASK:
                special = current_value & BIN_SPECIAL_RULE_MASK
                if special == BIN_STOP:
                    done = 1
                    return_level[0] = 0
                    if last_rule_was_hit > 0:
                        par_copy_return_value(new_ret, hit_ret)
                    continue
                elif special == BIN_RETURN:
                    current_rule_number = par_get_return_level(
                        return_rule, return_level, current_rule_number
                    )
                    continue
                elif special == BIN_GOTO:
                    current_rule_number = struct.unpack_from("<H", current_rule, 2)[0]
                    continue
                elif special == BIN_GORET:
                    par_set_return_level(return_rule, return_level, current_rule_number + 1)
                    current_rule_number = struct.unpack_from("<H", current_rule, 2)[0]
                    continue
                else:
                    break

            # Advance past rule flags (4 bytes: 2 for flags, 2 for rule number).
            rule_p += 4

            new_ret.value = FAIL

            # Check language flag (par_pars1.c lines 1230-1241).
            rule_modes_lang = struct.unpack_from("<I", current_rule, rule_p)[0]
            if last_rule_was_hit == 0 and (rule_modes_lang & in_lang_flag) == 0:
                current_rule_number += 1
                if current_rule_number >= num_rules:
                    done = 1
                continue

            # Check mode flag (par_pars1.c lines 1244-1256).
            rule_modes_mode = struct.unpack_from("<I", current_rule, rule_p + 4)[0]
            if (
                last_rule_was_hit == 0
                and rule_modes_mode != _MODE_FLAG_WILDCARD
                and (rule_modes_mode & in_mode_flag) == 0
            ):
                current_rule_number += 1
                if current_rule_number >= num_rules:
                    done = 1
                continue

            rule_p += 8

            # Dict hit/miss filter (par_pars1.c lines 1258-1300).
            if current_value & (BIN_DICT_HIT | BIN_DICT_MISS):
                pos = new_ret.input_pos + new_ret.input_offset
                dict_val = dict_hit_array[pos] if pos < len(dict_hit_array) else DICT_MISS_VALUE
                if (
                    (current_value & BIN_DICT_HIT)
                    and (current_value & BIN_DICT_MISS)
                    and dict_val == _DICT_ABBREV_VALUE
                ):
                    pass  # abbrev: process this rule
                elif (current_value & BIN_DICT_HIT) and dict_val != DICT_MISS_VALUE:
                    pass  # dict hit: process this rule
                elif (current_value & BIN_DICT_MISS) and dict_val == DICT_MISS_VALUE:
                    pass  # dict miss: process this rule
                else:
                    current_rule_number += 1
                    done = 1 if current_rule_number >= num_rules else -1

            if done:
                done = max(done, 0)
                continue

            # Extract next_hit / next_miss / goret_hit / goret_miss / copy_hit.
            cur_rule_next_hit = -1
            cur_rule_next_miss = -1
            cur_rule_next_go_hit = -1
            cur_rule_next_go_miss = -1
            cur_rule_copy_hit = -1

            if current_value & BIN_NEXT_HIT:
                cur_rule_next_hit = struct.unpack_from("<H", current_rule, rule_p)[0]
                rule_p += 2
            if current_value & BIN_NEXT_MISS:
                cur_rule_next_miss = struct.unpack_from("<H", current_rule, rule_p)[0]
                rule_p += 2
            if current_value & BIN_GORET_HIT:
                cur_rule_next_go_hit = struct.unpack_from("<H", current_rule, rule_p)[0]
                rule_p += 2
            if current_value & BIN_GORET_MISS:
                cur_rule_next_go_miss = struct.unpack_from("<H", current_rule, rule_p)[0]
                rule_p += 2
            if current_value & BIN_COPY_HIT:
                cur_rule_copy_hit = struct.unpack_from("<H", current_rule, rule_p)[0]
                rule_p += 2

            # Invoke the rule matcher.
            new_ret.rule = rule_p
            par_match_rule(
                current_rule,
                BIN_END_OF_RULE,
                new_input,
                output_array,
                new_input_indexes,
                output_indexes,
                match_array,
                new_ret,
                0,
                rule_data_table=rule_data_table,
                rule_index_table=rule_index_table,
                perform_action_funcs=perform_action_funcs,
            )

            ret_value.parser_flag = new_ret.parser_flag

            if new_ret.value == SUCCESS:
                temp = new_ret.input_pos + new_ret.input_offset
                # Check if match left off at end of word.
                at_word_boundary = (
                    new_input[temp] == 0
                    or (parser_char_types[new_input[temp]] & TYPE_white) != 0
                    or (
                        (parser_char_types[new_input[temp]] & TYPE_clause) != 0
                        and (
                            new_input[temp + 1] == 0
                            or (parser_char_types[new_input[temp + 1]] & TYPE_white) != 0
                        )
                    )
                    or (
                        (
                            parser_char_types[
                                output_array[new_ret.output_pos + new_ret.output_offset - 1]
                            ]
                            & TYPE_white
                        )
                        != 0
                        and bool(do_not_copy_next_word := 1)
                    )
                )

                if not at_word_boundary:
                    # Miss: restore save_ret and follow next_miss rules.
                    par_copy_return_value(new_ret, save_ret)
                    if cur_rule_next_go_miss != -1:
                        if cur_rule_next_miss != -1:
                            par_set_return_level(return_rule, return_level, cur_rule_next_miss)
                        else:
                            par_set_return_level(return_rule, return_level, current_rule_number + 1)
                        current_rule_number = cur_rule_next_go_miss
                        last_rule_was_hit = -1
                    elif cur_rule_next_miss != -1:
                        current_rule_number = cur_rule_next_miss
                        last_rule_was_hit = -1
                    else:
                        current_rule_number += 1
                        last_rule_was_hit = 0
                # Hit.
                elif cur_rule_copy_hit != -1:
                    last_rule_was_hit = 1
                    current_rule_number = cur_rule_copy_hit
                    par_copy_return_value(save_ret, new_ret)
                elif cur_rule_next_hit != -1 or cur_rule_next_go_hit != -1:
                    par_copy_return_value(hit_ret, new_ret)
                    input_size = new_ret.input_offset - save_ret.input_offset
                    output_size = new_ret.output_offset - save_ret.output_offset

                    if output_size > input_size:
                        size_diff = output_size - input_size
                        if save_ret.input_offset > size_diff:
                            dest = save_ret.input_pos + save_ret.input_offset - size_diff
                            src_out = save_ret.output_offset + save_ret.output_pos
                            new_input[dest : dest + output_size] = output_array[
                                src_out : src_out + output_size
                            ]
                            par_copy_index_list(
                                new_input_indexes, dest, output_indexes, src_out, output_size
                            )
                            new_ret.input_offset = save_ret.input_offset - size_diff
                            new_ret.output_offset = save_ret.output_offset
                            save_ret.input_offset -= size_diff
                        else:
                            j = new_ret.input_offset + new_ret.input_pos
                            cur_nul = new_input.find(0)
                            cur_len = cur_nul if cur_nul >= 0 else len(new_input)
                            for i in range(cur_len + size_diff, j, -1):
                                k = i - size_diff
                                new_input[i] = new_input[k]
                                par_copy_index(new_input_indexes, i, new_input_indexes, k)
                                dict_hit_array[i] = dict_hit_array[k]
                            new_input_diff += size_diff
                            dest2 = save_ret.input_offset + save_ret.input_pos
                            src_out2 = save_ret.output_offset + save_ret.output_pos
                            new_input[dest2 : dest2 + output_size] = output_array[
                                src_out2 : src_out2 + output_size
                            ]
                            par_copy_index_list(
                                new_input_indexes, dest2, output_indexes, src_out2, output_size
                            )
                            hit_ret.input_offset += size_diff
                            new_ret.input_offset = save_ret.input_offset
                            new_ret.output_offset = save_ret.output_offset
                    elif input_size == output_size:
                        dest3 = save_ret.input_offset + save_ret.input_pos
                        src_out3 = save_ret.output_offset + save_ret.output_pos
                        new_input[dest3 : dest3 + input_size] = output_array[
                            src_out3 : src_out3 + input_size
                        ]
                        par_copy_index_list(
                            new_input_indexes, dest3, output_indexes, src_out3, input_size
                        )
                        new_ret.input_offset = save_ret.input_offset
                        new_ret.output_offset = save_ret.output_offset
                    else:
                        size_diff2 = input_size - output_size
                        dest4 = save_ret.input_offset + save_ret.input_pos + size_diff2
                        src_out4 = save_ret.output_offset + save_ret.output_pos
                        new_input[dest4 : dest4 + output_size] = output_array[
                            src_out4 : src_out4 + output_size
                        ]
                        par_copy_index_list(
                            new_input_indexes, dest4, output_indexes, src_out4, output_size
                        )
                        new_ret.input_offset = save_ret.input_offset + size_diff2
                        new_ret.output_offset = save_ret.output_offset

                    if cur_rule_next_go_hit != -1:
                        if cur_rule_next_hit != -1:
                            par_set_return_level(return_rule, return_level, cur_rule_next_hit)
                        else:
                            par_set_return_level(return_rule, return_level, current_rule_number + 1)
                        current_rule_number = cur_rule_next_go_hit
                    else:
                        current_rule_number = cur_rule_next_hit

                    par_copy_return_value(save_ret, new_ret)
                    last_rule_was_hit = 1
                else:
                    done = 1
                    last_rule_was_hit = 0
            # Miss: follow next_miss rules.
            elif cur_rule_next_go_miss != -1:
                if cur_rule_next_miss != -1:
                    par_set_return_level(return_rule, return_level, cur_rule_next_miss)
                else:
                    par_set_return_level(return_rule, return_level, current_rule_number + 1)
                current_rule_number = cur_rule_next_go_miss
                last_rule_was_hit = -1
            elif cur_rule_next_miss != -1:
                current_rule_number = cur_rule_next_miss
                last_rule_was_hit = -1
            else:
                current_rule_number += 1
                last_rule_was_hit = 0

            if current_rule_number >= num_rules or current_rule_number < 0:
                done = 1

        # Copy the current word to output.
        if do_not_copy_next_word == 1:
            do_not_copy_next_word = 0
            done = 0
        elif (
            par_copy_word_to_output(
                bytes(new_input),
                output_array,
                new_input_indexes,
                output_indexes,
                new_ret,
            )
            == -1
        ):
            done = 1
        else:
            done = 0

    # NUL-terminate output (par_pars1.c line 1722).
    out_pos = new_ret.output_pos + new_ret.output_offset
    if out_pos < len(output_array):
        output_array[out_pos] = 0

    # Update caller ret_value (par_pars1.c lines 1724-1725).
    ret_value.input_offset = new_ret.input_offset - new_input_diff
    ret_value.output_offset = new_ret.output_offset

    return ret_value


__all__ = [
    "INVALID_RULE_SECTION_MESSAGE",
    "SHIM_DEFERRED",
    "ProcessInputState",
    "par_process_input",
]
